package com.artcraft.vectorcraft;

import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;
import android.provider.Settings;
import android.net.Uri;
import android.util.Log;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.ZipFile;

/**
 * Opt-in release updater for the production VectorCraft package only.
 * A candidate comes exclusively from the existing official GitHub releases
 * query, with an exact asset name/URL, published SHA-256 digest and byte count.
 * This does not install without Android's own approval screen, nor can
 * disposable-key, separately packaged TEST builds update the production app.
 */
final class VectorCraftUpdateInstaller {
    private static final String TAG = "VectorCraftUpdate";
    private static final String PACKAGE = "com.artcraft.vectorcraft";
    private static final String RELEASE_ASSET_BASE =
        "https://github.com/KosmosSG/artcraft-android/releases/download/";
    static final String INSTALL_ACTION = "com.artcraft.vectorcraft.UPDATE_INSTALL_STATUS";
    private static final long MAX_BYTES = 400L * 1024L * 1024L;
    private static final String CALLBACK_PREFS = "vectorcraft.android.updater.pending";
    private static final String TOKEN_KEY = "installer_callback_token";

    private final VectorCraftActivity activity;
    private final ConcurrentLinkedQueue<String> updates;
    private final AtomicBoolean busy = new AtomicBoolean(false);
    private volatile Candidate candidate;

    private static final class Candidate {
        final String version, url, sha256;
        final long bytes;
        Candidate(String version, String url, String sha256, long bytes) {
            this.version = version; this.url = url; this.sha256 = sha256; this.bytes = bytes;
        }
    }

    VectorCraftUpdateInstaller(VectorCraftActivity activity, ConcurrentLinkedQueue<String> updates) {
        this.activity = activity;
        this.updates = updates;
    }

    boolean isProductionInstall() {
        // The separate disposable test application must never even begin
        // downloading a production-package replacement.
        return PACKAGE.equals(activity.getPackageName());
    }

    void remember(String version, String url, String digest, long size) {
        candidate = null;
        if (version == null || url == null || digest == null
                || !version.matches("[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[1-9][0-9]*")
                || !digest.matches("sha256:[0-9a-fA-F]{64}")
                || size < 1024 * 1024 || size > MAX_BYTES) return;
        String expected = RELEASE_ASSET_BASE + "vectorcraft-v" + version + "/"
            + "VectorCraft-v" + version + "-arm64-v8a.apk";
        if (!expected.equals(url)) return;
        candidate = new Candidate(version, url, digest.substring(7).toLowerCase(Locale.ROOT), size);
    }

    boolean canDownload(String version) {
        Candidate c = candidate;
        return isProductionInstall() && c != null && c.version.equals(version);
    }

    void start(String version, java.util.concurrent.ExecutorService executor) {
        final Candidate c = candidate;
        if (!isProductionInstall()) {
            status("unavailable", "Test builds cannot replace the production VectorCraft app.", -1);
            return;
        }
        if (c == null || version == null || !c.version.equals(version)) {
            status("error", "Recheck GitHub releases before downloading an update.", -1);
            return;
        }
        if (!busy.compareAndSet(false, true)) {
            status("downloading", "An update download is already in progress.", -1);
            return;
        }
        executor.execute(() -> {
            File target = null;
            File partial = null;
            try {
                PackageManager manager = activity.getPackageManager();
                if (Build.VERSION.SDK_INT >= 26 && !manager.canRequestPackageInstalls()) {
                    status("permission_required", "Allow VectorCraft to install updates, then tap Download again.", -1);
                    activity.runOnUiThread(() -> {
                        try {
                            Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.parse("package:" + activity.getPackageName()));
                            activity.startActivity(settings);
                        } catch (Exception error) {
                            Log.w(TAG, "Unknown-app-source settings unavailable", error);
                        }
                    });
                    return;
                }
                File dir = new File(activity.getCacheDir(), "vectorcraft-update");
                if (!dir.exists() && !dir.mkdirs())
                    throw new java.io.IOException("Unable to prepare private update cache");
                // Never reuse a preexisting APK, partial or downloaded file.
                partial = new File(dir, "download.part");
                target = new File(dir, "candidate.apk");
                if (partial.exists() && !partial.delete()) throw new java.io.IOException("Old partial file blocked");
                if (target.exists() && !target.delete()) throw new java.io.IOException("Old candidate file blocked");

                status("downloading", "Downloading verified VectorCraft APK…", 0);
                download(c, partial);
                if (!partial.renameTo(target)) throw new java.io.IOException("Could not finalize downloaded APK");
                verifyArchive(c, target, manager);
                status("verified", "SHA-256, package, version and signing certificate verified.", 100);
                install(c, target);
            } catch (Exception error) {
                Log.e(TAG, "Update download or verification failed", error);
                status("error", "Update refused: " + error.getMessage(), -1);
            } finally {
                if (partial != null && partial.exists()) partial.delete();
                if (target != null && target.exists()) target.delete();
                busy.set(false);
            }
        });
    }

    private static boolean trustedRedirect(URL url) {
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getUserInfo() != null
                || (url.getPort() != -1 && url.getPort() != 443)) return false;
        String host = url.getHost().toLowerCase(Locale.ROOT);
        return "github.com".equals(host) || "release-assets.githubusercontent.com".equals(host)
            || "objects.githubusercontent.com".equals(host)
            || host.endsWith(".githubusercontent.com");
    }

    private void download(Candidate c, File partial) throws Exception {
        URL current = new URL(c.url);
        HttpURLConnection connection = null;
        try {
            for (int hop = 0; hop < 6; hop++) {
                if (!trustedRedirect(current)) throw new java.io.IOException("Untrusted release host");
                connection = (HttpURLConnection) current.openConnection();
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(12000);
                connection.setReadTimeout(25000);
                connection.setRequestProperty("User-Agent", "VectorCraft-Android-VerifiedUpdater");
                int code = connection.getResponseCode();
                if (code == 301 || code == 302 || code == 303 || code == 307 || code == 308) {
                    String redirect = connection.getHeaderField("Location");
                    if (redirect == null) throw new java.io.IOException("Release redirect missing");
                    URL next = new URL(current, redirect);
                    connection.disconnect();
                    connection = null;
                    current = next;
                    continue;
                }
                if (code != 200) throw new java.io.IOException("Download HTTP " + code);
                long length = connection.getContentLengthLong();
                if (length > 0 && length != c.bytes)
                    throw new java.io.IOException("APK length differs from published release");
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                long written = 0;
                int lastProgress = -1;
                try (InputStream in = connection.getInputStream();
                     FileOutputStream out = new FileOutputStream(partial)) {
                    byte[] buffer = new byte[64 * 1024];
                    int count;
                    while ((count = in.read(buffer)) != -1) {
                        written += count;
                        if (written > MAX_BYTES || written > c.bytes)
                            throw new java.io.IOException("APK exceeded declared release size");
                        digest.update(buffer, 0, count);
                        out.write(buffer, 0, count);
                        int progress = (int) (100 * written / c.bytes);
                        if (progress / 5 != lastProgress / 5) {
                            lastProgress = progress;
                            status("downloading", "Downloading " + progress + "%", progress);
                        }
                    }
                    out.getFD().sync();
                }
                if (written != c.bytes) throw new java.io.IOException("APK download incomplete");
                StringBuilder got = new StringBuilder(64);
                for (byte value : digest.digest()) got.append(String.format(Locale.ROOT, "%02x", value & 0xff));
                if (!MessageDigest.isEqual(got.toString().getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                      c.sha256.getBytes(java.nio.charset.StandardCharsets.US_ASCII)))
                    throw new java.io.IOException("SHA-256 digest mismatch");
                return;
            }
            throw new java.io.IOException("Too many release redirects");
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static boolean sameSigningIdentity(Signature[] a, Signature[] b) {
        if (a == null || b == null || a.length != b.length || a.length == 0) return false;
        boolean[] matched = new boolean[b.length];
        for (Signature signature : a) {
            boolean found = false;
            for (int i = 0; i < b.length; i++) {
                if (!matched[i] && signature.equals(b[i])) { matched[i] = true; found = true; break; }
            }
            if (!found) return false;
        }
        return true;
    }

    private void verifyArchive(Candidate c, File file, PackageManager pm) throws Exception {
        PackageInfo current = pm.getPackageInfo(activity.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
        PackageInfo target = pm.getPackageArchiveInfo(file.getAbsolutePath(), PackageManager.GET_SIGNING_CERTIFICATES);
        if (target == null || !PACKAGE.equals(target.packageName))
            throw new SecurityException("APK package does not match installed VectorCraft");
        if (!c.version.equals(target.versionName) || target.getLongVersionCode() <= current.getLongVersionCode())
            throw new SecurityException("APK version is not a newer matching VectorCraft version");
        if (current.signingInfo == null || target.signingInfo == null ||
                !sameSigningIdentity(current.signingInfo.getApkContentsSigners(),
                    target.signingInfo.getApkContentsSigners()))
            throw new SecurityException("APK signer differs from installed VectorCraft");
        try (ZipFile zip = new ZipFile(file)) {
            if (zip.getEntry("lib/arm64-v8a/libvectorcraft_android.so") == null)
                throw new SecurityException("APK has no VectorCraft ARM64 native library");
            if (zip.getEntry("lib/armeabi-v7a/libvectorcraft_android.so") != null ||
                zip.getEntry("lib/x86/libvectorcraft_android.so") != null)
                throw new SecurityException("Unexpected APK native ABI");
        }
    }

    private void install(Candidate c, File file) throws Exception {
        PackageInstaller installer = activity.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams params =
            new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(PACKAGE);
        params.setSize(file.length());
        if (Build.VERSION.SDK_INT >= 31)
            params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED);
        int sessionId = installer.createSession(params);
        PackageInstaller.Session session = null;
        boolean committed = false;
        try {
            session = installer.openSession(sessionId);
            try (FileInputStream input = new FileInputStream(file);
                 OutputStream output = session.openWrite("base.apk", 0, file.length())) {
                byte[] bytes = new byte[64 * 1024];
                int n;
                while ((n = input.read(bytes)) != -1) output.write(bytes, 0, n);
                session.fsync(output);
            }
            byte[] secret = new byte[20];
            new SecureRandom().nextBytes(secret);
            StringBuilder token = new StringBuilder(40);
            for (byte b : secret) token.append(String.format(Locale.ROOT, "%02x", b & 0xff));
            activity.getSharedPreferences(CALLBACK_PREFS, 0).edit()
                .putString(TOKEN_KEY, token.toString()).apply();
            Intent callback = new Intent(activity, VectorCraftActivity.class)
                .setAction(INSTALL_ACTION)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            callback.putExtra("vc_install_token", token.toString());
            PendingIntent sender = PendingIntent.getActivity(activity, sessionId, callback,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE);
            session.commit(sender.getIntentSender());
            committed = true;
            status("install_pending", "Android installer confirmation requested.", 100);
        } finally {
            if (session != null) session.close();
            if (!committed) installer.abandonSession(sessionId);
        }
    }

    void onInstallStatus(Intent intent) {
        if (intent == null || !INSTALL_ACTION.equals(intent.getAction())) return;
        String pending = activity.getSharedPreferences(CALLBACK_PREFS, 0)
            .getString(TOKEN_KEY, "");
        String received = intent.getStringExtra("vc_install_token");
        if (pending.isEmpty() || received == null || !pending.equals(received)) {
            Log.w(TAG, "Ignored unauthenticated installer callback");
            return;
        }
        int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            android.os.Parcelable action = intent.getParcelableExtra(Intent.EXTRA_INTENT);
            if (action instanceof Intent) {
                status("install_pending", "Waiting for your Android installation approval.", 100);
                Intent confirm = (Intent) action;
                confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                activity.startActivity(confirm);
            } else {
                status("error", "Android did not return a confirmation screen.", -1);
            }
            return;
        }
        activity.getSharedPreferences(CALLBACK_PREFS, 0).edit().remove(TOKEN_KEY).apply();
        if (status == PackageInstaller.STATUS_SUCCESS) {
            status("installed", "Android confirmed the VectorCraft update installation.", 100);
        } else {
            // Do not include arbitrary system Intent extras in the UI.
            status("error", "Android declined or could not install the verified update ("
                + status + ").", -1);
        }
    }

    private void status(String state, String message, int percent) {
        try {
            JSONObject result = new JSONObject();
            result.put("status", "ok");
            result.put("state", state);
            result.put("message", message);
            if (percent >= 0) result.put("progress", percent);
            updates.offer(result.toString());
        } catch (Exception error) {
            Log.w(TAG, "Updater status queue unavailable", error);
        }
    }
}
