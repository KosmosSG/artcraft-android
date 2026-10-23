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

    // Read-only release discovery. Downloads and installation always stay with the user.
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
                String bestTag = null, bestUrl = null;
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
                        }
                    }
                    if (releases.length() < 100) { exhausted = true; break; }
                }
                if (!exhausted) throw new java.io.IOException("Release inventory exceeds the supported bound");
                final String tag = bestTag, url = bestUrl;
                if (manual || tag != null) runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    android.app.AlertDialog.Builder dialog = new android.app.AlertDialog.Builder(this).setTitle("DesignCraft updates")
                        .setMessage(tag == null ? "Installed: " + installed + "\nNo newer published DesignCraft ARM64 release was found." : "Installed: " + installed + "\nAvailable: " + tag + "\nOpen the release to download. Android verifies the APK signature during installation.")
                        .setNegativeButton("Close", null);
                    if (url != null) dialog.setPositiveButton("View release", (d, w) -> {
                        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
                        catch (Exception error) { Log.w(TAG, "Cannot open release page", error); }
                    });
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

