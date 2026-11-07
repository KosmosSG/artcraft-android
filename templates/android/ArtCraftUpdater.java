package __PACKAGE__;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.app.ProgressDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Opt-in, GitHub-Releases-only updater. No production keys or silent installation. */
public final class ArtCraftUpdater {
    private static final String TAG = "ArtCraftUpdater";
    private static final String PREFS = "artcraft_update_preferences";
    private static final String CALLBACK = "__PACKAGE__.ARTCRAFT_INSTALL_CALLBACK";
    private static final Handler UI = new Handler(Looper.getMainLooper());
    private static final ExecutorService IO = Executors.newSingleThreadExecutor();
    private static final String RELEASES =
            "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100";
    private static volatile Release cachedUpdate;
    private static volatile String menuStatus = "Check GitHub Releases for updates.";
    private ArtCraftUpdater() {}

    /** Read-only UI state for the Wc/Gc top-left icon menus. */
    public static String menuState(Activity activity, String app, String installedTag,
                                   String targetPackage) {
        try {
            boolean startupEnabled = activity.getSharedPreferences(PREFS, Activity.MODE_PRIVATE)
                    .getBoolean("startup_" + app, false);
            Release ready = cachedUpdate;
            boolean available = ready != null && compareTags(ready.tag, installedTag, app) > 0;
            return new JSONObject()
                    .put("startup", startupEnabled)
                    .put("installed", installedTag)
                    .put("available", available)
                    .put("diagnostics", !activity.getPackageName().equals(targetPackage))
                    .put("status", menuStatus).toString();
        } catch (Exception ex) {
            Log.w(TAG, "Cannot read updater menu status", ex);
            return "{}";
        }
    }

    /** Offer only the verified release found by the previous user-initiated check. */
    public static void downloadAvailable(Activity activity, String app, String installedTag,
                                         String targetPackage) {
        UI.post(() -> {
            Release release = cachedUpdate;
            if (release == null || compareTags(release.tag, installedTag, app) <= 0) {
                message(activity, "Check for updates first.");
                return;
            }
            download(activity, release, targetPackage);
        });
    }

    /** Called from the app's lightweight egui menu. */
    public static void check(Activity activity, String app, String installedTag, String targetPackage) {
        UI.post(() -> checkInternal(activity, app, installedTag, targetPackage, false));
    }

    /** Automatic checks are OFF until explicitly enabled; never downloads automatically. */
    public static void startup(Activity activity, String app, String installedTag, String targetPackage) {
        if (activity.getSharedPreferences(PREFS, Activity.MODE_PRIVATE)
                .getBoolean("startup_" + app, false)) {
            UI.post(() -> checkInternal(activity, app, installedTag, targetPackage, true));
        }
    }

    public static void toggleStartup(Activity activity, String app, String installedTag, String targetPackage) {
        UI.post(() -> {
            SharedPreferences prefs = activity.getSharedPreferences(PREFS, Activity.MODE_PRIVATE);
            boolean enabled = !prefs.getBoolean("startup_" + app, false);
            prefs.edit().putBoolean("startup_" + app, enabled).apply();
            message(activity, "Check at startup " + (enabled ? "enabled" : "disabled")
                    + ". Downloads and installation always require confirmation.");
        });
    }

    /** Read-only release-notes shortcut for the currently validated published update. */
    public static void viewAvailable(Activity activity, String app, String installedTag,
                                     String targetPackage) {
        UI.post(() -> {
            Release release = cachedUpdate;
            if (release == null || compareTags(release.tag, installedTag, app) <= 0) {
                message(activity, "Check for updates first.");
                return;
            }
            Intent intent = new Intent(Intent.ACTION_VIEW,
                    Uri.parse("https://github.com/KosmosSG/artcraft-android/releases/tag/" + release.tag));
            activity.startActivity(intent);
        });
    }

    /** End-to-end download/checksum test: never invokes Android's installer. */
    public static void testDownload(Activity activity, String app, String installedTag, String targetPackage) {
        IO.execute(() -> {
            try {
                Release release = latestRelease(app);
                if (release == null) throw new IllegalStateException("No published ARM64 asset found");
                UI.post(() -> download(activity, release, targetPackage, true));
            } catch (Exception ex) {
                UI.post(() -> error(activity, "Updater test failed: " + ex.getMessage()));
            }
        });
    }

    private static void checkInternal(Activity activity, String app, String installedTag,
                                      String targetPackage, boolean quiet) {
        menuStatus = "Checking published GitHub Releases…";
        cachedUpdate = null;
        final java.util.concurrent.atomic.AtomicBoolean checkCancelled = new java.util.concurrent.atomic.AtomicBoolean(false);
        final ProgressDialog checking = quiet ? null : new ProgressDialog(activity);
        if (checking != null) {
            checking.setMessage("Checking published GitHub Releases…");
            checking.setIndeterminate(true);
            checking.setCancelable(true);
            checking.setOnCancelListener(dialog -> checkCancelled.set(true));
            checking.show();
        }
        IO.execute(() -> {
            try {
                Release release = latestRelease(app);
                UI.post(() -> {
                    if (checking != null && checking.isShowing()) checking.dismiss();
                    if (checkCancelled.get()) {
                        menuStatus = "Update check cancelled.";
                        return;
                    }
                    if (release == null || compareTags(release.tag, installedTag, app) <= 0) {
                        menuStatus = "Up to date: " + installedTag;
                        if (!quiet) message(activity, "No newer published " + app + " release.");
                        return;
                    }
                    cachedUpdate = release;
                    menuStatus = "New version available: " + release.tag;
                    new AlertDialog.Builder(activity)
                        .setTitle("Update " + app)
                        .setMessage("Installed: " + installedTag + "\nPublished: " + release.tag
                            + "\n\nDownload the original-package ARM64 APK from GitHub?"
                            + "\nAndroid will ask you to confirm installation.")
                        .setNegativeButton("Later", null)
                        .setPositiveButton("Download", (d, w) ->
                            download(activity, release, targetPackage))
                        .show();
                });
            } catch (Exception error) {
                Log.e(TAG, "Release check failed", error);
                menuStatus = "Update check failed; retry when connected.";
                UI.post(() -> {
                    if (checking != null && checking.isShowing()) checking.dismiss();
                    if (!quiet) error(activity, "Update check failed: " + error.getMessage());
                });
            }
        });
    }

    private static final class Release {
        final String tag, apkName, apkUrl, digest, checksumUrl;
        final long bytes;
        Release(String t, String n, String u, String d, String c, long b) {
            tag = t; apkName = n; apkUrl = u; digest = d; checksumUrl = c; bytes = b;
        }
    }

    private static Release latestRelease(String app) throws Exception {
        JSONArray releases = new JSONArray(getText(RELEASES, 8 * 1024 * 1024));
        Release newest = null;
        for (int i = 0; i < releases.length(); i++) {
            JSONObject r = releases.getJSONObject(i);
            if (r.optBoolean("draft", true) || r.optBoolean("prerelease", false)) continue;
            String tag = r.optString("tag_name", "");
            if (!tag.startsWith(app + "-v") || parseVersion(tag, app) == null) continue;
            JSONArray assets = r.optJSONArray("assets");
            if (assets == null) continue;
            String checksum = "";
            for (int j = 0; j < assets.length(); j++) {
                JSONObject a = assets.getJSONObject(j);
                if ("SHA256SUMS.txt".equalsIgnoreCase(a.optString("name"))) {
                    checksum = a.optString("browser_download_url", "");
                }
            }
            for (int j = 0; j < assets.length(); j++) {
                JSONObject a = assets.getJSONObject(j);
                String name = a.optString("name", "");
                String lower = name.toLowerCase(Locale.ROOT);
                if (!lower.startsWith(app) || !lower.endsWith("arm64-v8a.apk")) continue;
                String url = a.optString("browser_download_url", "");
                if (!url.startsWith("https://github.com/KosmosSG/artcraft-android/releases/download/")) continue;
                Release candidate = new Release(tag, name, url,
                        a.optString("digest", ""), checksum, a.optLong("size"));
                if (newest == null || compareTags(tag, newest.tag, app) > 0) newest = candidate;
            }
        }
        return newest;
    }

    private static int[] parseVersion(String tag, String app) {
        String prefix = app + "-v";
        if (!tag.startsWith(prefix)) return null;
        String[] parts = tag.substring(prefix.length()).split("-android\\.");
        if (parts.length != 2) return null;
        String[] number = parts[0].split("\\.");
        if (number.length != 3) return null;
        try {
            return new int[]{Integer.parseInt(number[0]), Integer.parseInt(number[1]),
                    Integer.parseInt(number[2]), Integer.parseInt(parts[1])};
        } catch (NumberFormatException ex) { return null; }
    }

    private static int compareTags(String a, String b, String app) {
        int[] av = parseVersion(a, app), bv = parseVersion(b, app);
        if (av == null) return -1;
        if (bv == null) return 1;
        for (int i = 0; i < av.length; i++) {
            if (av[i] != bv[i]) return Integer.compare(av[i], bv[i]);
        }
        return 0;
    }

    private static void download(Activity activity, Release release, String targetPackage) {
        download(activity, release, targetPackage, false);
    }

    private static void download(Activity activity, Release release, String targetPackage,
                                 boolean verificationOnly) {
        ProgressDialog progress = new ProgressDialog(activity);
        progress.setTitle("Downloading " + release.tag);
        progress.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);
        progress.setMax(100);
        progress.setCancelable(true);
        final java.util.concurrent.atomic.AtomicBoolean downloadCancelled = new java.util.concurrent.atomic.AtomicBoolean(false);
        progress.setOnCancelListener(dialog -> downloadCancelled.set(true));
        progress.show();
        IO.execute(() -> {
            File apk = new File(activity.getCacheDir(), "artcraft-update-" + targetPackage + ".apk");
            try {
                String expected = expectedDigest(release);
                if (expected == null) throw new SecurityException("GitHub SHA-256 checksum unavailable");
                MessageDigest sha = MessageDigest.getInstance("SHA-256");
                HttpURLConnection conn = connect(release.apkUrl);
                long total = conn.getContentLengthLong();
                if (release.bytes > 0 && total > 0 && release.bytes != total)
                    throw new SecurityException("GitHub asset size does not match");
                long count = 0;
                try (InputStream in = conn.getInputStream(); OutputStream out = new FileOutputStream(apk)) {
                    byte[] buffer = new byte[64 * 1024];
                    int n;
                    while ((n = in.read(buffer)) != -1) {
                        if (downloadCancelled.get()) throw new InterruptedException("Download cancelled");
                        out.write(buffer, 0, n);
                        sha.update(buffer, 0, n);
                        count += n;
                        if (total > 0) {
                            final int percent = (int)Math.min(100, 100 * count / total);
                            UI.post(() -> progress.setProgress(percent));
                        }
                    }
                } finally { conn.disconnect(); }
                if (release.bytes > 0 && count != release.bytes)
                    throw new SecurityException("Downloaded size does not match GitHub asset");
                if (!hex(sha.digest()).equalsIgnoreCase(expected))
                    throw new SecurityException("APK SHA-256 verification failed");
                verifyPackageAndSigner(activity, apk, targetPackage);
                if (verificationOnly) {
                    if (!apk.delete()) Log.w(TAG, "Could not remove test APK");
                    UI.post(() -> {
                        progress.dismiss();
                        new AlertDialog.Builder(activity)
                            .setTitle("Updater test passed")
                            .setMessage("GitHub download, APK identity, signing certificate and SHA-256 verified. No app was installed.")
                            .setPositiveButton("OK", null).show();
                    });
                    return;
                }
                UI.post(() -> {
                    progress.dismiss();
                    new AlertDialog.Builder(activity)
                        .setTitle("Verified APK")
                        .setMessage("SHA-256 and package identity verified. Install " + release.tag
                            + "? Android will show the normal installation confirmation.")
                        .setNegativeButton("Not now", null)
                        .setPositiveButton("Install", (d, w) ->
                            IO.execute(() -> install(activity, apk, targetPackage)))
                        .show();
                });
            } catch (Exception ex) {
                if (!apk.delete()) Log.w(TAG, "Could not delete failed download");
                Log.e(TAG, "Update download/verification failed", ex);
                UI.post(() -> {
                    progress.dismiss();
                    if (!(ex instanceof InterruptedException)) error(activity, ex.getMessage());
                });
            }
        });
    }

    private static String expectedDigest(Release release) throws Exception {
        if (release.digest.startsWith("sha256:")
                && release.digest.substring(7).matches("(?i)[0-9a-f]{64}")) {
            return release.digest.substring(7);
        }
        if (release.checksumUrl.isEmpty()) return null;
        for (String line : getText(release.checksumUrl, 1024 * 1024).split("\\r?\\n")) {
            String[] parts = line.trim().split("\\s+", 2);
            if (parts.length == 2 && parts[0].matches("(?i)[0-9a-f]{64}")
                    && parts[1].trim().replaceFirst("^\\*", "").equals(release.apkName))
                return parts[0];
        }
        return null;
    }

    private static void verifyPackageAndSigner(Activity activity, File apk, String targetPackage)
            throws Exception {
        PackageManager pm = activity.getPackageManager();
        PackageInfo archive = pm.getPackageArchiveInfo(apk.getAbsolutePath(),
                PackageManager.GET_SIGNING_CERTIFICATES);
        if (archive == null || !targetPackage.equals(archive.packageName)
                || archive.signingInfo == null)
            throw new SecurityException("Unexpected or unsigned Android package");
        Signature[] signers = archive.signingInfo.getApkContentsSigners();
        if (signers == null || signers.length == 0)
            throw new SecurityException("APK has no signing certificate");
        try {
            pm.getPackageInfo(targetPackage, PackageManager.GET_SIGNING_CERTIFICATES);
            for (Signature signer : signers) {
                byte[] sha = MessageDigest.getInstance("SHA-256").digest(signer.toByteArray());
                if (!pm.hasSigningCertificate(targetPackage, sha, PackageManager.CERT_INPUT_SHA256))
                    throw new SecurityException("Update signing certificate differs from installed app");
            }
        } catch (PackageManager.NameNotFoundException notInstalled) {
            // A separately-installed test candidate can offer the original package for installation.
            Log.i(TAG, "Original app not installed; Android installer will ask for confirmation");
        }
    }

    private static void install(Activity activity, File apk, String targetPackage) {
        PackageInstaller.Session session = null;
        try {
            if (Build.VERSION.SDK_INT >= 26 && !activity.getPackageManager().canRequestPackageInstalls()) {
                UI.post(() -> {
                    error(activity, "Allow installs from this app in Android Settings, then try again.");
                    Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            Uri.parse("package:" + activity.getPackageName()));
                    activity.startActivity(settings);
                });
                return;
            }
            PackageInstaller installer = activity.getPackageManager().getPackageInstaller();
            PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(
                    PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            params.setAppPackageName(targetPackage);
            if (Build.VERSION.SDK_INT >= 31)
                params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED);
            int id = installer.createSession(params);
            session = installer.openSession(id);
            try (InputStream in = new FileInputStream(apk);
                 OutputStream out = session.openWrite("base.apk", 0, apk.length())) {
                byte[] buffer = new byte[64 * 1024];
                int n;
                while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
                session.fsync(out);
            }
            Intent callback = new Intent(activity, activity.getClass());
            callback.setAction(CALLBACK);
            callback.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            PendingIntent pending = PendingIntent.getActivity(activity, id, callback,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE);
            session.commit(pending.getIntentSender());
        } catch (Exception ex) {
            if (session != null) try { session.abandon(); } catch (Exception ignored) {}
            Log.e(TAG, "Installation request failed", ex);
            UI.post(() -> error(activity, "Could not request installation: " + ex.getMessage()));
        } finally {
            if (session != null) session.close();
        }
    }

    /** The generated SAF Activity calls this BEFORE passing intents to the document-open bridge. */
    public static boolean handleInstallCallback(Activity activity, Intent intent) {
        if (intent == null || !CALLBACK.equals(intent.getAction())) return false;
        final int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, Integer.MIN_VALUE);
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirmation != null) activity.startActivity(confirmation);
            else error(activity, "Android did not provide an installation confirmation.");
        } else if (status == PackageInstaller.STATUS_SUCCESS) {
            message(activity, "Update installed successfully.");
        } else {
            String detail = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
            error(activity, "Installation not completed: " + (detail == null ? status : detail));
        }
        return true;
    }

    private static HttpURLConnection connect(String address) throws Exception {
        URL url = new URL(address);
        if (!"https".equalsIgnoreCase(url.getProtocol()))
            throw new SecurityException("Update URL must use HTTPS");
        HttpURLConnection c = (HttpURLConnection)url.openConnection();
        c.setInstanceFollowRedirects(true);
        c.setConnectTimeout(15000);
        c.setReadTimeout(30000);
        c.setRequestProperty("Accept", "application/vnd.github+json");
        c.setRequestProperty("User-Agent", "ArtCraft-Android-Updater");
        if (c.getResponseCode() != HttpURLConnection.HTTP_OK) {
            int status = c.getResponseCode();
            c.disconnect();
            throw new IllegalStateException("GitHub returned HTTP " + status);
        }
        return c;
    }

    private static String getText(String url, int limit) throws Exception {
        HttpURLConnection c = connect(url);
        try (InputStream in = c.getInputStream()) {
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int count, total = 0;
            while ((count = in.read(buffer)) != -1) {
                total += count;
                if (total > limit) throw new IllegalStateException("GitHub response too large");
                out.write(buffer, 0, count);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        } finally { c.disconnect(); }
    }

    private static String hex(byte[] bytes) {
        StringBuilder b = new StringBuilder(bytes.length * 2);
        for (byte x : bytes) b.append(String.format(Locale.ROOT, "%02x", x & 255));
        return b.toString();
    }

    private static void message(Activity a, String text) {
        UI.post(() -> Toast.makeText(a, text, Toast.LENGTH_LONG).show());
    }

    private static void error(Activity a, String text) {
        UI.post(() -> new AlertDialog.Builder(a).setTitle("App update")
                .setMessage(text).setPositiveButton("OK", null).show());
    }
}
