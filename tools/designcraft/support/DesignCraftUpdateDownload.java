package com.artcraft.designcraft;

/**
 * User-initiated Android updater. Only permanently signed production packages
 * are eligible. DownloadManager handles the transfer; verification occurs
 * before the app offers Android's normal, user-confirmed installer.
 *
 * This is intentionally not a silent installer and is never used by the
 * separately signed *.candidate / *.test packages.
 */
final class DesignCraftUpdateDownload {
    private static final String PACKAGE = "com.artcraft.designcraft";
    private static final String SHA256_CERT =
        "c45236b436cbfbfbeade716b11cb24a50a795a6af3f147132ce6f19753fea394";
    private static final long MAX_BYTES = 1024L * 1024L * 1024L;
    private static final java.util.concurrent.atomic.AtomicBoolean BUSY =
        new java.util.concurrent.atomic.AtomicBoolean(false);

    private DesignCraftUpdateDownload() {}

    static void start(android.app.Activity activity, String apkUrl, String checksum,
                      long versionCode, String versionName) {
        if (!PACKAGE.equals(activity.getPackageName()) || !SHA256_CERT.equals(DesignCraftUpdatePolicy.CERT)) {
            error(activity, "This test package cannot install production DesignCraft updates.");
            return;
        }
        if (versionName == null || !versionName.matches("[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[1-9][0-9]*")
                || checksum == null || !checksum.matches("[0-9a-f]{64}")
                || versionCode < 1 || versionCode > 2100000000L) {
            error(activity, "Invalid update metadata.");
            return;
        }
        String tag = "designcraft-v" + versionName;
        String prefix = DesignCraftUpdatePolicy.REPOSITORY + "/releases/download/" + tag + "/";
        if (!apkUrl.equals(prefix + "DesignCraft-v" + versionName + "-arm64-v8a.apk")
                && !apkUrl.equals(prefix + "DesignCraft-" + versionName + "-arm64-v8a.apk")) {
            error(activity, "Update download URL does not match this release.");
            return;
        }
        if (android.os.Build.VERSION.SDK_INT >= 26
                && !activity.getPackageManager().canRequestPackageInstalls()) {
            new android.app.AlertDialog.Builder(activity)
                .setTitle("Allow DesignCraft updates")
                .setMessage("Android requires permission to install APKs from DesignCraft. Enable Allow from this source, return here, then tap Download again. Installation will still need your confirmation.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Open settings", (dialog, which) -> {
                    try {
                        activity.startActivity(new android.content.Intent(
                            android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            android.net.Uri.parse("package:" + PACKAGE)));
                    } catch (Exception e) {
                        error(activity, "Unable to open Android installation settings: " + e.getMessage());
                    }
                }).show();
            return;
        }
        if (!BUSY.compareAndSet(false, true)) {
            error(activity, "A DesignCraft update download is already running.");
            return;
        }
        try {
            android.content.pm.PackageInfo installed = activity.getPackageManager()
                .getPackageInfo(PACKAGE, 0);
            if (versionCode <= installed.getLongVersionCode()) {
                BUSY.set(false);
                error(activity, "The selected release is not newer than the installed version.");
                return;
            }
            java.io.File root = activity.getExternalFilesDir(null);
            if (root == null) throw new java.io.IOException("App download storage is unavailable.");
            java.io.File directory = new java.io.File(root, "verified-updates");
            if (!directory.isDirectory() && !directory.mkdirs())
                throw new java.io.IOException("Cannot create update download directory.");
            java.io.File output = new java.io.File(directory,
                "DesignCraft-v" + versionName + "-arm64-v8a.apk");
            if (output.exists() && !output.delete())
                throw new java.io.IOException("Cannot replace the previous update download.");

            android.app.DownloadManager manager = (android.app.DownloadManager)
                activity.getSystemService(android.content.Context.DOWNLOAD_SERVICE);
            if (manager == null) throw new java.io.IOException("Android DownloadManager is unavailable.");
            android.app.DownloadManager.Request request =
                new android.app.DownloadManager.Request(android.net.Uri.parse(apkUrl));
            request.setTitle("DesignCraft " + versionName);
            request.setDescription("Downloading a verified Android update");
            request.setMimeType("application/vnd.android.package-archive");
            request.setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE);
            request.setDestinationInExternalFilesDir(activity, null,
                "verified-updates/" + output.getName());
            long downloadId = manager.enqueue(request);

            final java.util.concurrent.atomic.AtomicBoolean cancelled =
                new java.util.concurrent.atomic.AtomicBoolean(false);
            android.app.ProgressDialog progress = new android.app.ProgressDialog(activity);
            progress.setTitle("Downloading DesignCraft");
            progress.setMessage("Downloading inside the app. The APK will be verified before installation.");
            progress.setProgressStyle(android.app.ProgressDialog.STYLE_HORIZONTAL);
            progress.setIndeterminate(true);
            progress.setCancelable(false);
            progress.setButton(android.content.DialogInterface.BUTTON_NEGATIVE, "Cancel",
                (dialog, which) -> {
                    cancelled.set(true);
                    manager.remove(downloadId);
                });
            progress.show();
            Thread worker = new Thread(() -> {
                try {
                    waitForDownload(activity, manager, downloadId, progress, cancelled);
                    if (cancelled.get()) return;
                    verifyApk(activity, output, checksum, versionCode, versionName);
                    android.net.Uri uri = manager.getUriForDownloadedFile(downloadId);
                    if (uri == null || !"content".equals(uri.getScheme()))
                        throw new java.io.IOException("Android did not provide a shareable download URI.");
                    activity.runOnUiThread(() -> {
                        if (activity.isFinishing() || activity.isDestroyed()) return;
                        progress.dismiss();
                        new android.app.AlertDialog.Builder(activity)
                            .setTitle("DesignCraft update verified")
                            .setMessage("The SHA-256 checksum, original signing certificate, package ID and newer version were verified. Install " + versionName + " using Android's confirmation screen?")
                            .setNegativeButton("Later", null)
                            .setPositiveButton("Install", (dialog, which) -> {
                                try {
                                    android.content.Intent install = new android.content.Intent(
                                        android.content.Intent.ACTION_VIEW);
                                    install.setDataAndType(uri, "application/vnd.android.package-archive");
                                    install.addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION);
                                    activity.startActivity(install);
                                } catch (Exception e) {
                                    error(activity, "Android installer could not open the verified APK: " + e.getMessage());
                                }
                            }).show();
                    });
                } catch (Exception e) {
                    if (!cancelled.get()) {
                        android.util.Log.w("DesignCraftUpdater", "Update download/verification failed", e);
                        manager.remove(downloadId);
                        activity.runOnUiThread(() -> {
                            if (!activity.isFinishing() && !activity.isDestroyed()) {
                                progress.dismiss();
                                error(activity, "Download or verification failed: " + e.getMessage());
                            }
                        });
                    }
                } finally {
                    BUSY.set(false);
                    if (cancelled.get()) activity.runOnUiThread(progress::dismiss);
                }
            }, "designcraft-verified-apk-download");
            worker.start();
        } catch (Exception e) {
            BUSY.set(false);
            error(activity, "Cannot start update download: " + e.getMessage());
        }
    }

    private static void waitForDownload(android.app.Activity activity,
                                        android.app.DownloadManager manager, long downloadId,
                                        android.app.ProgressDialog progress,
                                        java.util.concurrent.atomic.AtomicBoolean cancelled) throws Exception {
        long deadline = android.os.SystemClock.elapsedRealtime() + 20L * 60L * 1000L;
        while (!cancelled.get()) {
            if (android.os.SystemClock.elapsedRealtime() > deadline)
                throw new java.io.IOException("Download took longer than 20 minutes. Retry when the network is stable.");
            android.app.DownloadManager.Query query =
                new android.app.DownloadManager.Query().setFilterById(downloadId);
            try (android.database.Cursor cursor = manager.query(query)) {
                if (cursor == null || !cursor.moveToFirst())
                    throw new java.io.IOException("Android lost the update download.");
                int status = cursor.getInt(cursor.getColumnIndexOrThrow(
                    android.app.DownloadManager.COLUMN_STATUS));
                long total = cursor.getLong(cursor.getColumnIndexOrThrow(
                    android.app.DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
                long received = cursor.getLong(cursor.getColumnIndexOrThrow(
                    android.app.DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                if (total > MAX_BYTES || received > MAX_BYTES)
                    throw new java.io.IOException("Update exceeds the 1 GiB safety limit.");
                if (status == android.app.DownloadManager.STATUS_SUCCESSFUL) return;
                if (status == android.app.DownloadManager.STATUS_FAILED) {
                    int reason = cursor.getInt(cursor.getColumnIndexOrThrow(
                        android.app.DownloadManager.COLUMN_REASON));
                    throw new java.io.IOException("Android download failed (reason " + reason + ").");
                }
                activity.runOnUiThread(() -> {
                    if (!activity.isFinishing() && !activity.isDestroyed()) {
                        progress.setIndeterminate(total <= 0);
                        if (total > 0) {
                            progress.setMax(100);
                            progress.setProgress((int) Math.min(100, received * 100 / total));
                        }
                    }
                });
            }
            Thread.sleep(650);
        }
    }

    private static void verifyApk(android.app.Activity activity, java.io.File file,
                                  String expectedSha, long expectedCode,
                                  String expectedVersion) throws Exception {
        if (!file.isFile() || file.length() <= 0 || file.length() > MAX_BYTES)
            throw new java.io.IOException("Downloaded APK is missing or has an invalid size.");

        java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
        try (java.io.InputStream input = new java.io.BufferedInputStream(
                new java.io.FileInputStream(file))) {
            byte[] buffer = new byte[131072];
            int count;
            while ((count = input.read(buffer)) != -1)
                digest.update(buffer, 0, count);
        }
        String actualSha = hex(digest.digest());
        if (!actualSha.equals(expectedSha))
            throw new java.io.IOException("APK checksum mismatch; download will not be installed.");

        android.content.pm.PackageInfo archive = activity.getPackageManager()
            .getPackageArchiveInfo(file.getAbsolutePath(),
                android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES);
        if (archive == null || !PACKAGE.equals(archive.packageName)
                || archive.getLongVersionCode() != expectedCode
                || !expectedVersion.equals(archive.versionName))
            throw new java.io.IOException("APK identity or version mismatch.");
        if (archive.signingInfo == null)
            throw new java.io.IOException("APK does not expose a signing certificate.");
        android.content.pm.Signature[] signatures = archive.signingInfo.getApkContentsSigners();
        if (signatures == null || signatures.length != 1)
            throw new java.io.IOException("Unexpected APK signing certificate count.");
        String actualCert = hex(java.security.MessageDigest.getInstance("SHA-256")
            .digest(signatures[0].toByteArray()));
        if (!SHA256_CERT.equals(actualCert))
            throw new java.io.IOException("APK is not signed by the original DesignCraft key.");

        try (java.util.zip.ZipFile zip = new java.util.zip.ZipFile(file)) {
            if (zip.getEntry("lib/arm64-v8a/libdesigncraft_android.so") == null)
                throw new java.io.IOException("APK is missing the ARM64 DesignCraft engine.");
        }
        android.content.pm.PackageInfo installed = activity.getPackageManager()
            .getPackageInfo(PACKAGE, 0);
        if (expectedCode <= installed.getLongVersionCode())
            throw new java.io.IOException("APK is no longer newer than the installed version.");
    }

    private static String hex(byte[] bytes) {
        char[] digits = "0123456789abcdef".toCharArray();
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            result.append(digits[(b & 255) >>> 4]);
            result.append(digits[b & 15]);
        }
        return result.toString();
    }

    private static void error(android.app.Activity activity, String message) {
        if (!activity.isFinishing() && !activity.isDestroyed())
            new android.app.AlertDialog.Builder(activity).setTitle("DesignCraft updates")
                .setMessage(message).setPositiveButton("Close", null).show();
    }
}
