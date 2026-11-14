package com.artcraft.updater;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * CADCraft-only Android updater. Nothing from the reference Android builder's
 * release feed can reach this class. Only published, non-draft CADCraft Android
 * APK assets in KosmosSG/artcraft-android are candidates.
 *
 * The APK is downloaded WITHIN CADCraft using Android DownloadManager; the
 * system package installer still requires explicit user approval.
 */
public final class UpdateCheck {
    private static final String RELEASES =
        "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100";
    private static final String CURRENT = "cadcraft-v0.19.0-android.9";
    private static final Pattern CAD_TAG = Pattern.compile(
        "^cadcraft-v([0-9]+)\\.([0-9]+)\\.([0-9]+)-android\\.([0-9]+)$",
        Pattern.CASE_INSENSITIVE);
    private static final ExecutorService WORK = Executors.newSingleThreadExecutor();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private UpdateCheck() {}

    // No unsolicited update modal in this temporary test package. Future
    // production releases can enable an unobtrusive startup check separately.
    public static void start(Activity activity) {}

    /** Entry point called from the top-left Cc menu over the app's JNI context. */
    public static void checkNow(final Activity activity) {
        if (activity == null || activity.isFinishing()) return;
        activity.runOnUiThread(() -> {
            final AlertDialog waiting = new AlertDialog.Builder(activity)
                .setTitle("CADCraft updates")
                .setMessage("Checking published CADCraft Android releases…")
                .setNegativeButton("Cancel", (d, w) -> d.dismiss())
                .create();
            waiting.show();
            WORK.execute(() -> {
                final Release latest;
                String error = null;
                Release result = null;
                try { result = newestPublished(); }
                catch (Exception e) { error = e.getMessage(); }
                latest = result;
                final String failure = error;
                MAIN.post(() -> {
                    if (activity.isFinishing() || activity.isDestroyed()) return;
                    waiting.dismiss();
                    if (failure != null) {
                        message(activity, "Update check unavailable",
                            "Unable to reach GitHub: " + failure + "\nTry again later.");
                    } else if (latest == null) {
                        message(activity, "CADCraft updates",
                            "No published CADCraft Android APK is available yet.");
                    } else if (compare(latest.tag, CURRENT) <= 0) {
                        message(activity, "CADCraft is up to date",
                            "Latest published CADCraft Android: " + latest.tag);
                    } else {
                        offerDownload(activity, latest);
                    }
                });
            });
        });
    }

    private static void message(Activity activity, String title, String message) {
        new AlertDialog.Builder(activity).setTitle(title)
            .setMessage(message).setPositiveButton("OK", null).show();
    }

    private static final class Release {
        final String tag, name, url;
        final long size;
        Release(String tag, String name, String url, long size) {
            this.tag = tag; this.name = name; this.url = url; this.size = size;
        }
    }

    private static int[] numbers(String tag) {
        Matcher m = CAD_TAG.matcher(tag == null ? "" : tag);
        if (!m.matches()) return null;
        try {
            return new int[]{Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2)),
                Integer.parseInt(m.group(3)), Integer.parseInt(m.group(4))};
        } catch (NumberFormatException error) {
            return null;
        }
    }

    private static int compare(String one, String two) {
        int[] a = numbers(one), b = numbers(two);
        if (a == null || b == null) return -1;
        for (int i = 0; i < 4; i++) {
            if (a[i] != b[i]) return Integer.compare(a[i], b[i]);
        }
        return 0;
    }

    private static Release newestPublished() throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(RELEASES).openConnection();
        try {
            c.setConnectTimeout(9000);
            c.setReadTimeout(12000);
            c.setRequestProperty("Accept", "application/vnd.github+json");
            c.setRequestProperty("User-Agent", "CADCraft-Android-Updater");
            if (c.getResponseCode() != 200) throw new Exception("GitHub API HTTP " + c.getResponseCode());
            StringBuilder body = new StringBuilder();
            try (InputStream input = c.getInputStream();
                BufferedReader reader = new BufferedReader(new InputStreamReader(input, "UTF-8"))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    body.append(line);
                    if (body.length() > 2000000) throw new Exception("Release response exceeded size limit");
                }
            }
            JSONArray releases = new JSONArray(body.toString());
            Release best = null;
            for (int i = 0; i < releases.length(); i++) {
                JSONObject release = releases.optJSONObject(i);
                if (release == null || release.optBoolean("draft") || release.optBoolean("prerelease")) continue;
                String tag = release.optString("tag_name", "");
                if (numbers(tag) == null) continue;
                JSONArray assets = release.optJSONArray("assets");
                if (assets == null) continue;
                for (int j = 0; j < assets.length(); j++) {
                    JSONObject asset = assets.optJSONObject(j);
                    if (asset == null) continue;
                    String name = asset.optString("name", "");
                    String low = name.toLowerCase(Locale.ROOT);
                    String url = asset.optString("browser_download_url", "");
                    // Do not install a ZIP, an unrelated suite app or a test-signed artifact.
                    if (!low.startsWith("cadcraft") || !low.endsWith(".apk") ||
                        low.contains("test") || !url.startsWith(
                        "https://github.com/KosmosSG/artcraft-android/releases/download/")) continue;
                    if (best == null || compare(tag, best.tag) > 0)
                        best = new Release(tag, name, url, asset.optLong("size", 0L));
                }
            }
            return best;
        } finally {
            c.disconnect();
        }
    }

    private static void offerDownload(Activity activity, Release release) {
        final boolean isTest = activity.getPackageName().endsWith(".test");
        String note = "Published version: " + release.tag + "\n" +
            "Official source: KosmosSG/artcraft-android\n\n" +
            "Download the APK inside CADCraft, then confirm installation in Android.";
        if (isTest) note += "\n\nThis is an isolated disposable-signed TEST app. " +
            "The published package may install separately and cannot automatically " +
            "replace this test package.";
        new AlertDialog.Builder(activity).setTitle("CADCraft update available")
            .setMessage(note)
            .setPositiveButton("Download in app", (dialog, which) -> startDownload(activity, release))
            .setNegativeButton("Later", null).show();
    }

    private static void startDownload(Activity activity, Release release) {
        final DownloadManager dm =
            (DownloadManager) activity.getSystemService(Context.DOWNLOAD_SERVICE);
        if (dm == null) {
            message(activity, "Download unavailable", "Android DownloadManager is not available.");
            return;
        }
        try {
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(release.url));
            request.setTitle("CADCraft " + release.tag);
            request.setDescription("Official CADCraft Android APK");
            request.setMimeType("application/vnd.android.package-archive");
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            // App-specific storage is writable without broad filesystem privileges.
            request.setDestinationInExternalFilesDir(activity, Environment.DIRECTORY_DOWNLOADS,
                release.name.replaceAll("[^a-zA-Z0-9._-]", "_"));
            long id = dm.enqueue(request);
            showProgress(activity, dm, id);
        } catch (Exception e) {
            message(activity, "Download failed", String.valueOf(e.getMessage()));
        }
    }

    private static void showProgress(Activity activity, DownloadManager dm, long id) {
        LinearLayout layout = new LinearLayout(activity);
        layout.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (activity.getResources().getDisplayMetrics().density * 20);
        layout.setPadding(pad, pad / 2, pad, pad / 2);
        ProgressBar bar = new ProgressBar(activity, null, android.R.attr.progressBarStyleHorizontal);
        bar.setIndeterminate(true);
        bar.setMax(100);
        TextView info = new TextView(activity);
        info.setText("Downloading APK in CADCraft…");
        layout.addView(bar);
        layout.addView(info);
        final AlertDialog dialog = new AlertDialog.Builder(activity)
            .setTitle("CADCraft download").setView(layout)
            .setNegativeButton("Hide", null).create();
        dialog.show();
        Runnable polling = new Runnable() {
            private int ticks;
            @Override public void run() {
                if (activity.isFinishing() || activity.isDestroyed()) return;
                try (Cursor c = dm.query(new DownloadManager.Query().setFilterById(id))) {
                    if (c == null || !c.moveToFirst()) {
                        dialog.dismiss();
                        message(activity, "Download unavailable", "Android could not find the download.");
                        return;
                    }
                    int state = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                    if (state == DownloadManager.STATUS_SUCCESSFUL) {
                        dialog.dismiss();
                        Uri uri = dm.getUriForDownloadedFile(id);
                        if (uri == null) message(activity, "Download complete",
                            "Open the downloaded CADCraft APK from Android Downloads to install.");
                        else offerInstall(activity, uri);
                        return;
                    }
                    if (state == DownloadManager.STATUS_FAILED) {
                        dialog.dismiss();
                        message(activity, "Download failed",
                            "Check your connection or the Downloads notification and try again.");
                        return;
                    }
                    long total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
                    long got = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                    if (total > 0) {
                        int pct = (int) Math.min(100L, (got * 100L) / total);
                        bar.setIndeterminate(false);
                        bar.setProgress(pct);
                        info.setText(pct + "% downloaded");
                    }
                    // DownloadManager continues safely if the progress dialog is hidden.
                    if (++ticks <= 1800) MAIN.postDelayed(this, 1000L);
                    else {
                        dialog.dismiss();
                        message(activity, "Download continues",
                            "The APK is still downloading. Check Android Downloads.");
                    }
                } catch (Exception e) {
                    dialog.dismiss();
                    message(activity, "Download status unavailable", String.valueOf(e.getMessage()));
                }
            }
        };
        MAIN.postDelayed(polling, 600L);
    }

    private static void offerInstall(Activity activity, Uri uri) {
        new AlertDialog.Builder(activity)
            .setTitle("CADCraft APK downloaded")
            .setMessage("The APK is ready. Android will ask you to approve installation. " +
                "A different package or signing certificate cannot silently replace this build.")
            .setPositiveButton("Install", (d, w) -> install(activity, uri))
            .setNegativeButton("Later", null).show();
    }

    private static void install(Activity activity, Uri uri) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                !activity.getPackageManager().canRequestPackageInstalls()) {
                message(activity, "Allow installation",
                    "Enable 'Install unknown apps' for CADCraft in Android Settings, then " +
                    "open the downloaded APK from Downloads.");
                Intent setting = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + activity.getPackageName()));
                activity.startActivity(setting);
                return;
            }
            Intent installer = new Intent(Intent.ACTION_VIEW);
            installer.setDataAndType(uri, "application/vnd.android.package-archive");
            installer.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION |
                Intent.FLAG_ACTIVITY_NEW_TASK);
            activity.startActivity(installer);
        } catch (Exception error) {
            message(activity, "Open from Downloads",
                "Android could not launch the installer. Find the APK in Downloads: " +
                    error.getMessage());
        }
    }
}
