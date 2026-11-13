    private final java.util.concurrent.atomic.AtomicBoolean dcChecking = new java.util.concurrent.atomic.AtomicBoolean();
    private final ExecutorService dcUpdateIo = Executors.newSingleThreadExecutor();

    public void dcAction(long action) {
        if (action == 1) dcRequestFontFolder(0);
        else if (action == 2) dcRefreshFontFolder(0);
        else if (action == 3) dcCheckUpdates(true);
        else if (action == 4) runOnUiThread(() -> {
            boolean enabled = getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean("dc_startup_check", false);
            new android.app.AlertDialog.Builder(this).setTitle("Update checks")
                .setMultiChoiceItems(new String[]{"Check GitHub at startup"}, new boolean[]{enabled},
                    (dialog, which, checked) -> getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean("dc_startup_check", checked).apply())
                .setPositiveButton("Done", null).show();
        });
    }

    // Explicit user-confirmed update download. The APK is validated before
    // handing it to Android's installer; never silently install anything.
    private final java.util.concurrent.atomic.AtomicBoolean dcDownloading =
        new java.util.concurrent.atomic.AtomicBoolean(false);
    private final android.os.Handler dcUpdateHandler =
        new android.os.Handler(android.os.Looper.getMainLooper());

    // The production updater still refuses disposable-key test package IDs.
    private void dcCheckUpdates(boolean manual) {
        // The disposable-key candidate is a different Android package and cannot update
        // over the permanent production certificate. Never present it as compatible.
        if (!"com.artcraft.designcraft".equals(getPackageName())) {
            if (manual) runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                new android.app.AlertDialog.Builder(this)
                    .setTitle("DesignCraft updates")
                    .setMessage("This is a separately signed DesignCraft test build. Production updates require the permanent production package and certificate.")
                    .setPositiveButton("Close", null).show();
            });
            return;
        }
        if (!dcChecking.compareAndSet(false, true)) return;
        if (manual) runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed())
                android.widget.Toast.makeText(this, "Checking DesignCraft releases…",
                    android.widget.Toast.LENGTH_SHORT).show();
        });
        dcUpdateIo.execute(() -> {
            try {
                android.content.pm.PackageInfo installedInfo = getPackageManager().getPackageInfo(getPackageName(), 0);
                String installed = installedInfo.versionName == null ? "unknown" : installedInfo.versionName;
                long installedCode = installedInfo.getLongVersionCode();
                long bestCode = installedCode;
                String bestTag = null, bestUrl = null, bestApkUrl = null, bestApkSha = null;
                int metadataRequests = 0;
                boolean exhausted = false;
                long deadline = android.os.SystemClock.elapsedRealtime() + 120000;
                for (int page = 1; page <= 5; page++) {
                    JSONArray releases = new JSONArray(new String(dcUpdateBytes(
                        "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100&page=" + page,
                        1024 * 1024), java.nio.charset.StandardCharsets.UTF_8));
                    for (int i = 0; i < releases.length(); i++) {
                        if (android.os.SystemClock.elapsedRealtime() > deadline)
                            throw new java.io.IOException("Update check exceeded its time budget");
                        JSONObject release = releases.optJSONObject(i);
                        if (release == null || release.optBoolean("draft") || release.optBoolean("prerelease")) continue;
                        String tag = release.optString("tag_name", "");
                        if (!tag.matches("designcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[1-9][0-9]*")) continue;
                        JSONArray assets = release.optJSONArray("assets");
                        if (assets == null) continue;
                        JSONObject metadata = null;
                        for (int j = 0; j < assets.length(); j++) {
                            JSONObject asset = assets.optJSONObject(j);
                            if (asset == null || !"designcraft-update.json".equals(asset.optString("name"))) continue;
                            if (metadata != null) throw new java.io.IOException("Duplicate update metadata");
                            metadata = asset;
                        }
                        if (metadata == null) continue;
                        if (++metadataRequests > 20) throw new java.io.IOException("Too many update metadata assets");
                        String expected = DesignCraftUpdatePolicy.REPOSITORY + "/releases/download/" + tag + "/designcraft-update.json";
                        if (!expected.equals(metadata.optString("browser_download_url")))
                            throw new java.io.IOException("Unexpected update metadata destination");
                        JSONObject manifest = new JSONObject(new String(dcUpdateBytes(expected, 65536), java.nio.charset.StandardCharsets.UTF_8));
                        long code = DesignCraftUpdatePolicy.validate(tag, manifest.get("schema"),
                            manifest.getString("package"), manifest.getString("version_name"), manifest.get("version_code"),
                            manifest.getString("certificate_sha256"), manifest.getString("apk_sha256"), manifest.getString("apk_url"),
                            manifest.getString("upstream_commit"), manifest.getString("builder_commit"), manifest.getString("automation_commit"));
                        boolean hasApk = false;
                        for (int j = 0; j < assets.length(); j++) {
                            JSONObject asset = assets.optJSONObject(j);
                            if (asset != null && manifest.getString("apk_url").equals(asset.optString("browser_download_url"))) hasApk = true;
                        }
                        if (hasApk && DesignCraftUpdatePolicy.newer(bestCode, code)) {
                            bestCode = code; bestTag = tag;
                            bestUrl = DesignCraftUpdatePolicy.REPOSITORY + "/releases/tag/" + tag;
                            bestApkUrl = manifest.getString("apk_url");
                            bestApkSha = manifest.getString("apk_sha256");
                        }
                    }
                    if (releases.length() < 100) { exhausted = true; break; }
                }
                if (!exhausted) throw new java.io.IOException("Release inventory exceeds the supported bound");
                final String tag = bestTag, url = bestUrl;
                final String apkUrl = bestApkUrl, apkSha = bestApkSha;
                final long apkCode = bestCode;
                if (manual || tag != null) runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    android.app.AlertDialog.Builder dialog =
                        new android.app.AlertDialog.Builder(this)
                            .setTitle("DesignCraft updates")
                            .setMessage(tag == null
                                ? "Installed: " + installed
                                    + "\\nNo newer published DesignCraft ARM64 release was found."
                                : "Installed: " + installed
                                    + "\\nAvailable: " + tag
                                    + "\\nDownload and verify the APK inside DesignCraft. "
                                    + "Android will request permission before installation.")
                            .setNegativeButton("Close", null);
                    if (url != null) {
                        dialog.setNeutralButton("View release", (d, w) -> {
                            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
                            catch (Exception error) { Log.w(TAG, "Cannot open release page", error); }
                        });
                    }
                    if (apkUrl != null && apkSha != null) {
                        dialog.setPositiveButton("Download APK", (d, w) ->
                            dcDownloadVerifiedApk(tag, apkUrl, apkSha, apkCode));
                    }
                    dialog.show();
                });
            } catch (Exception error) {
                Log.w(TAG, "DesignCraft update check failed", error);
                if (manual) runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) new android.app.AlertDialog.Builder(this).setTitle("Update check unavailable")
                        .setMessage(error.getMessage()).setPositiveButton("Close", null).show();
                });
            } finally {
                dcChecking.set(false);
            }
        });
    }


    /** Download an explicitly selected, public, release-pinned production APK. */
    private void dcDownloadVerifiedApk(String tag, String apkUrl,
                                      String expectedSha, long expectedCode) {
        if (!"com.artcraft.designcraft".equals(getPackageName())) {
            dcUpdateMessage("The separately signed test app cannot install production updates.");
            return;
        }
        if (tag == null || !tag.matches(
                "designcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[1-9][0-9]*")) {
            dcUpdateMessage("Invalid DesignCraft release tag.");
            return;
        }
        String canonical = DesignCraftUpdatePolicy.REPOSITORY
            + "/releases/download/" + tag + "/DesignCraft-v"
            + tag.substring("designcraft-v".length()) + "-arm64-v8a.apk";
        String legacy = DesignCraftUpdatePolicy.REPOSITORY
            + "/releases/download/" + tag + "/DesignCraft-"
            + tag.substring("designcraft-v".length()) + "-arm64-v8a.apk";
        if ((!apkUrl.equals(canonical) && !apkUrl.equals(legacy))
                || !expectedSha.matches("[0-9a-f]{64}")
                || expectedCode <= 0) {
            dcUpdateMessage("Update metadata did not match the approved release.");
            return;
        }
        if (!dcDownloading.compareAndSet(false, true)) {
            dcUpdateMessage("An APK download is already in progress.");
            return;
        }
        try {
            java.io.File folder = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS);
            if (folder == null || (!folder.isDirectory() && !folder.mkdirs()))
                throw new java.io.IOException("App download directory unavailable");
            String fileName = "DesignCraft-" + tag + "-arm64-v8a.apk";
            java.io.File apk = new java.io.File(folder, fileName);
            if (apk.exists() && !apk.delete())
                throw new java.io.IOException("Cannot replace a previous update download");
            android.app.DownloadManager manager =
                (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            if (manager == null) throw new java.io.IOException("Android Download Manager unavailable");
            android.app.DownloadManager.Request request =
                new android.app.DownloadManager.Request(Uri.parse(apkUrl));
            request.setTitle("DesignCraft update " + tag);
            request.setDescription("Secure GitHub release APK download");
            request.setMimeType("application/vnd.android.package-archive");
            request.setNotificationVisibility(
                android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setAllowedOverMetered(true);
            request.setAllowedOverRoaming(false);
            request.setDestinationInExternalFilesDir(this,
                android.os.Environment.DIRECTORY_DOWNLOADS, fileName);
            long id = manager.enqueue(request);
            android.widget.ProgressBar bar = new android.widget.ProgressBar(
                this, null, android.R.attr.progressBarStyleHorizontal);
            bar.setMax(100);
            bar.setProgress(0);
            android.app.AlertDialog progress = new android.app.AlertDialog.Builder(this)
                .setTitle("Downloading DesignCraft")
                .setMessage("Downloading from the verified GitHub release…")
                .setView(bar)
                .setNegativeButton("Cancel", (dialog, which) -> {
                    dcDownloading.set(false);
                    manager.remove(id);
                })
                .create();
            progress.setCancelable(false);
            progress.show();
            long deadline = android.os.SystemClock.elapsedRealtime() + 600000L;
            dcUpdateHandler.post(new Runnable() {
                @Override public void run() {
                    if (!dcDownloading.get() || isFinishing() || isDestroyed()) {
                        progress.dismiss();
                        return;
                    }
                    if (android.os.SystemClock.elapsedRealtime() > deadline) {
                        manager.remove(id);
                        dcDownloading.set(false);
                        progress.dismiss();
                        dcUpdateMessage("APK download timed out.");
                        return;
                    }
                    try (android.database.Cursor cursor = manager.query(
                            new android.app.DownloadManager.Query().setFilterById(id))) {
                        if (cursor == null || !cursor.moveToFirst())
                            throw new java.io.IOException("Android lost the update download");
                        int status = cursor.getInt(cursor.getColumnIndexOrThrow(
                            android.app.DownloadManager.COLUMN_STATUS));
                        if (status == android.app.DownloadManager.STATUS_SUCCESSFUL) {
                            progress.dismiss();
                            // Verify on the existing background I/O executor, not the UI thread.
                            dcUpdateIo.execute(() -> {
                                try {
                                    dcVerifyDownloadedApk(apk, expectedSha, expectedCode);
                                    Uri verified = manager.getUriForDownloadedFile(id);
                                    if (verified == null)
                                        throw new java.io.IOException("Downloaded APK cannot be shared with Android installer");
                                    runOnUiThread(() -> {
                                        dcDownloading.set(false);
                                        dcOfferInstallVerifiedApk(verified);
                                    });
                                } catch (Exception error) {
                                    Log.w(TAG, "Downloaded APK failed verification", error);
                                    apk.delete();
                                    runOnUiThread(() -> {
                                        dcDownloading.set(false);
                                        dcUpdateMessage("APK verification failed: " + error.getMessage());
                                    });
                                }
                            });
                            return;
                        }
                        if (status == android.app.DownloadManager.STATUS_FAILED) {
                            throw new java.io.IOException("Android download error "
                                + cursor.getInt(cursor.getColumnIndexOrThrow(
                                    android.app.DownloadManager.COLUMN_REASON)));
                        }
                        long total = cursor.getLong(cursor.getColumnIndexOrThrow(
                            android.app.DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
                        long bytes = cursor.getLong(cursor.getColumnIndexOrThrow(
                            android.app.DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                        if (total > 0)
                            bar.setProgress((int) Math.min(100L, bytes * 100L / total));
                        dcUpdateHandler.postDelayed(this, 700L);
                    } catch (Exception error) {
                        manager.remove(id);
                        dcDownloading.set(false);
                        progress.dismiss();
                        dcUpdateMessage("Download failed: " + error.getMessage());
                    }
                }
            });
        } catch (Exception error) {
            dcDownloading.set(false);
            dcUpdateMessage("Unable to start APK download: " + error.getMessage());
        }
    }

    /** Check both the published SHA-256 and the actual package/signing identity. */
    private void dcVerifyDownloadedApk(java.io.File apk, String expectedSha,
                                       long expectedCode) throws Exception {
        if (!apk.isFile() || apk.length() < 1024)
            throw new java.io.IOException("Downloaded APK is missing or empty");
        java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
        try (java.io.InputStream in = new java.io.BufferedInputStream(
                new java.io.FileInputStream(apk))) {
            byte[] chunk = new byte[65536];
            int n;
            while ((n = in.read(chunk)) != -1) digest.update(chunk, 0, n);
        }
        StringBuilder hex = new StringBuilder();
        for (byte b : digest.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        if (!expectedSha.equals(hex.toString()))
            throw new java.io.IOException("APK SHA-256 differs from verified update metadata");
        android.content.pm.PackageInfo downloaded = getPackageManager()
            .getPackageArchiveInfo(apk.getAbsolutePath(), android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES);
        if (downloaded == null || !"com.artcraft.designcraft".equals(downloaded.packageName)
                || downloaded.getLongVersionCode() != expectedCode
                || downloaded.signingInfo == null)
            throw new java.io.IOException("Downloaded APK package/version is incompatible");
        android.content.pm.Signature[] certs = downloaded.signingInfo.getApkContentsSigners();
        if (certs == null || certs.length != 1)
            throw new java.io.IOException("Unexpected APK certificate count");
        byte[] certHash = java.security.MessageDigest.getInstance("SHA-256")
            .digest(certs[0].toByteArray());
        StringBuilder certHex = new StringBuilder();
        for (byte b : certHash)
            certHex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        if (!DesignCraftUpdatePolicy.CERT.equals(certHex.toString()))
            throw new java.io.IOException("APK signature differs from production DesignCraft");
        android.content.pm.PackageInfo installed =
            getPackageManager().getPackageInfo(getPackageName(), 0);
        if (downloaded.getLongVersionCode() <= installed.getLongVersionCode())
            throw new java.io.IOException("APK is not newer than installed DesignCraft");
    }

    private void dcOfferInstallVerifiedApk(Uri uri) {
        if (isFinishing() || isDestroyed()) return;
        new android.app.AlertDialog.Builder(this)
            .setTitle("DesignCraft APK verified")
            .setMessage("The downloaded APK matches the release SHA-256 and DesignCraft's "
                + "production certificate. Open Android's package installer?")
            .setNegativeButton("Not now", null)
            .setPositiveButton("Install", (dialog, which) -> {
                try {
                    Intent intent = new Intent(Intent.ACTION_VIEW);
                    intent.setDataAndType(uri, "application/vnd.android.package-archive");
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(intent);
                } catch (Exception error) {
                    dcUpdateMessage("Android installer unavailable: " + error.getMessage());
                }
            }).show();
    }

    private void dcUpdateMessage(String message) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            new android.app.AlertDialog.Builder(this).setTitle("DesignCraft updates")
                .setMessage(message).setPositiveButton("Close", null).show();
        });
    }

    /** Public, read-only metadata requests. Redirects never carry credentials. */
    private byte[] dcUpdateBytes(String address, int limit) throws Exception {
        java.net.URL url = new java.net.URL(address);
        for (int redirects = 0; redirects <= 3; redirects++) {
            String host = url.getHost();
            if (!"https".equals(url.getProtocol()) || url.getUserInfo() != null
                    || (url.getPort() != -1 && url.getPort() != 443)
                    || !(host.equals("api.github.com") || host.equals("github.com")
                         || host.equals("release-assets.githubusercontent.com") || host.equals("objects.githubusercontent.com")))
                throw new java.io.IOException("Unexpected metadata host");
            java.net.HttpURLConnection connection = (java.net.HttpURLConnection) url.openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(8000);
            connection.setRequestProperty("Accept", "application/vnd.github+json");
            connection.setRequestProperty("User-Agent", "DesignCraft-Android-Updater");
            try {
                int status = connection.getResponseCode();
                if (status == 301 || status == 302 || status == 303 || status == 307 || status == 308) {
                    String location = connection.getHeaderField("Location");
                    if (location == null) throw new java.io.IOException("Missing metadata redirect");
                    url = new java.net.URL(url, location);
                    continue;
                }
                if (status != 200) throw new java.io.IOException("GitHub returned HTTP " + status);
                try (InputStream input = connection.getInputStream(); java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
                    byte[] chunk = new byte[8192];
                    int count;
                    while ((count = input.read(chunk)) != -1) {
                        if (out.size() + count > limit) throw new java.io.IOException("Metadata response too large");
                        out.write(chunk, 0, count);
                    }
                    return out.toByteArray();
                }
            } finally {
                connection.disconnect();
            }
        }
        throw new java.io.IOException("Too many metadata redirects");
    }

