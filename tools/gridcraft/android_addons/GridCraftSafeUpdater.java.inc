// GRIDCRAFT_ANDROID_SAFE_INSTALL_V1 — only attached to GridCraft v0.15+.
// Download an explicitly selected official published release APK, verify the
// package AND original signing certificate, then invoke Android's normal
// installer confirmation UI. Never grant silent installation rights.
private volatile String gcEligibleUpdateApkUrl;
private volatile String gcEligibleUpdateDigest;
private final java.util.concurrent.atomic.AtomicBoolean gcUpdateDownloading = new java.util.concurrent.atomic.AtomicBoolean(false);

public void gcDownloadAndInstallUpdate() {
    final String url = gcEligibleUpdateApkUrl;
    final String digest = gcEligibleUpdateDigest;
    if (getPackageName().endsWith(".candidate")) {
        gcSend("update", "error", "Testing APK uses a separate signature/package. Public GridCraft updates cannot replace it.");
        return;
    }
    if (url == null || !url.matches("https://github\\.com/KosmosSG/artcraft-android/releases/download/gridcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+/[A-Za-z0-9._%-]+\\.apk")) {
        gcSend("update", "error", "Update APK must come from a verified GridCraft GitHub Release.");
        return;
    }
    if (!gcUpdateDownloading.compareAndSet(false, true)) return;
    gcWorker.execute(() -> {
        android.app.DownloadManager manager = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        long downloadId = -1;
        java.io.File verificationFile = null;
        try {
            if (manager == null) throw new java.io.IOException("Android Download Manager unavailable");
            android.app.DownloadManager.Request request = new android.app.DownloadManager.Request(android.net.Uri.parse(url));
            request.setTitle("GridCraft verified Android update");
            request.setDescription("Downloading official GridCraft APK. Android will ask before installing.");
            request.setMimeType("application/vnd.android.package-archive");
            request.setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setAllowedOverMetered(true);
            downloadId = manager.enqueue(request);
            gcSend("update", "downloading", "Downloading GridCraft APK in Android Download Manager…");
            long deadline = android.os.SystemClock.elapsedRealtime() + 20L * 60L * 1000L;
            boolean complete = false;
            while (android.os.SystemClock.elapsedRealtime() < deadline) {
                android.app.DownloadManager.Query query = new android.app.DownloadManager.Query().setFilterById(downloadId);
                try (android.database.Cursor c = manager.query(query)) {
                    if (c == null || !c.moveToFirst()) throw new java.io.IOException("Download was removed");
                    int status = c.getInt(c.getColumnIndexOrThrow(android.app.DownloadManager.COLUMN_STATUS));
                    if (status == android.app.DownloadManager.STATUS_SUCCESSFUL) { complete = true; break; }
                    if (status == android.app.DownloadManager.STATUS_FAILED) {
                        throw new java.io.IOException("Download Manager rejected the GridCraft APK");
                    }
                }
                Thread.sleep(800);
            }
            if (!complete) throw new java.io.IOException("APK download timed out; check Android Downloads");
            android.net.Uri downloaded = manager.getUriForDownloadedFile(downloadId);
            if (downloaded == null) throw new java.io.IOException("Download URI unavailable");
            verificationFile = java.io.File.createTempFile("gridcraft-verified-update-", ".apk", getCacheDir());
            java.security.MessageDigest sha = java.security.MessageDigest.getInstance("SHA-256");
            long count = 0;
            try (java.io.InputStream input = getContentResolver().openInputStream(downloaded);
                 java.io.OutputStream output = new java.io.FileOutputStream(verificationFile)) {
                if (input == null) throw new java.io.IOException("Android cannot open downloaded APK");
                byte[] buffer = new byte[64 * 1024];
                int size;
                while ((size = input.read(buffer)) >= 0) {
                    if (size == 0) continue;
                    count += size;
                    if (count > 512L * 1024 * 1024) throw new java.io.IOException("APK exceeds 512 MiB safety limit");
                    sha.update(buffer, 0, size);
                    output.write(buffer, 0, size);
                }
            }
            if (count < 1024 * 1024) throw new java.io.IOException("Downloaded APK unexpectedly small");
            String actual = gcDigestHex(sha.digest());
            if (digest != null && digest.matches("sha256:[0-9a-fA-F]{64}") &&
                    !actual.equalsIgnoreCase(digest.substring(7))) {
                throw new java.io.IOException("GitHub release SHA-256 mismatch: download rejected");
            }
            android.content.pm.PackageManager pm = getPackageManager();
            int signFlag = android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES;
            android.content.pm.PackageInfo archive = pm.getPackageArchiveInfo(verificationFile.getAbsolutePath(), signFlag);
            android.content.pm.PackageInfo installed = pm.getPackageInfo(getPackageName(), signFlag);
            if (archive == null || !getPackageName().equals(archive.packageName) ||
                    archive.signingInfo == null || installed.signingInfo == null) {
                throw new java.io.IOException("APK package or signing information mismatch");
            }
            android.content.pm.Signature[] incoming = archive.signingInfo.getApkContentsSigners();
            android.content.pm.Signature[] current = installed.signingInfo.getApkContentsSigners();
            if (incoming == null || current == null || incoming.length != current.length ||
                    !java.util.Arrays.equals(incoming, current)) {
                throw new java.io.IOException("Downloaded APK is not signed by this GridCraft installation's original certificate");
            }
            if (archive.getLongVersionCode() <= installed.getLongVersionCode()) {
                throw new java.io.IOException("Downloaded APK is not newer than installed version");
            }
            gcSend("update", "verified", "APK downloaded and original signature verified. Confirm installation in Android.");
            final android.net.Uri contentUri = downloaded;
            runOnUiThread(() -> {
                try {
                    android.content.Intent installer = new android.content.Intent(android.content.Intent.ACTION_VIEW);
                    installer.setDataAndType(contentUri, "application/vnd.android.package-archive");
                    installer.addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION |
                            android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
                    installer.setClipData(android.content.ClipData.newUri(getContentResolver(), "GridCraft update", contentUri));
                    startActivity(installer); // OS confirmation; NEVER a silent installation.
                } catch (Exception error) {
                    gcSend("update", "error", "Cannot launch Android installer: " + error.getMessage());
                }
            });
        } catch (Exception error) {
            gcSend("update", "error", "Verified APK update stopped: " + error.getMessage());
        } finally {
            if (verificationFile != null && verificationFile.exists() && !verificationFile.delete()) {
                android.util.Log.w(TAG, "GridCraft update temporary verification file will be removed by cache cleanup");
            }
            gcUpdateDownloading.set(false);
        }
    });
}

private static String gcDigestHex(byte[] bytes) {
    final char[] abc = "0123456789abcdef".toCharArray();
    char[] out = new char[bytes.length * 2];
    for (int i = 0; i < bytes.length; i++) {
        out[2 * i] = abc[(bytes[i] >>> 4) & 0xf];
        out[2 * i + 1] = abc[bytes[i] & 0xf];
    }
    return new String(out);
}
