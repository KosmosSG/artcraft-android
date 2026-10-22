
    // LightCraft-only GitHub update checks. This queue is independent of SAF/IME.
    private final java.util.concurrent.ConcurrentLinkedQueue<String> lcUpdateResults =
            new java.util.concurrent.ConcurrentLinkedQueue<>();
    private final java.util.concurrent.ExecutorService lcUpdateIo =
            java.util.concurrent.Executors.newSingleThreadExecutor();

    /** Initiate a bounded, asynchronous manual check of LightCraft GitHub Releases. */
    public void lcCheckForUpdates() {
        lcUpdateIo.execute(() -> {
            java.net.HttpURLConnection connection = null;
            try {
                connection = (java.net.HttpURLConnection) new java.net.URL(
                    "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100")
                    .openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(8000);
                connection.setRequestProperty("Accept", "application/vnd.github+json");
                connection.setRequestProperty("User-Agent", "LightCraft-Android-Updater");
                if (connection.getResponseCode() != 200) {
                    throw new java.io.IOException("GitHub returned HTTP " + connection.getResponseCode());
                }
                java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
                try (java.io.InputStream input = connection.getInputStream()) {
                    byte[] chunk = new byte[8192];
                    int n;
                    while ((n = input.read(chunk)) >= 0) {
                        if (buffer.size() + n > 1024 * 1024) {
                            throw new java.io.IOException("GitHub response exceeds 1 MB");
                        }
                        buffer.write(chunk, 0, n);
                    }
                }
                org.json.JSONArray releases = new org.json.JSONArray(
                    new String(buffer.toByteArray(), java.nio.charset.StandardCharsets.UTF_8));
                android.content.pm.PackageInfo installed =
                    getPackageManager().getPackageInfo(getPackageName(), 0);
                String installedName = installed.versionName == null ? "unknown" : installed.versionName;
                long installedCode = android.os.Build.VERSION.SDK_INT >= 28
                    ? installed.getLongVersionCode() : installed.versionCode;
                long latestCode = -1L;
                String latestName = null;
                String latestPage = null;
                for (int i = 0; i < releases.length(); i++) {
                    org.json.JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft") ||
                        release.optBoolean("prerelease")) continue;
                    String tag = release.optString("tag_name", "");
                    java.util.regex.Matcher m = java.util.regex.Pattern.compile(
                        "^lightcraft-v([0-9]+)\\.([0-9]+)\\.([0-9]+)(?:-android\\.([0-9]+))?$"
                    ).matcher(tag);
                    if (!m.matches()) continue;
                    int major = Integer.parseInt(m.group(1));
                    int minor = Integer.parseInt(m.group(2));
                    int patch = Integer.parseInt(m.group(3));
                    int android = m.group(4) == null ? 0 : Integer.parseInt(m.group(4));
                    // Matches the Android-only ArtCraft versionCode scheme; accept only
                    // unambiguous bounded version components and real ARM64 APK assets.
                    if (major > 255 || minor > 255 || patch > 255 || android > 50) continue;
                    long code = (1L << 24) | (major << 16) | (minor << 8) | patch;
                    code += android;
                    if (code <= latestCode) continue;
                    org.json.JSONArray assets = release.optJSONArray("assets");
                    boolean arm64 = false;
                    if (assets != null) for (int j = 0; j < assets.length(); j++) {
                        org.json.JSONObject asset = assets.optJSONObject(j);
                        String name = asset == null ? "" : asset.optString("name", "").toLowerCase(
                            java.util.Locale.ROOT);
                        if (name.endsWith(".apk") &&
                            (name.contains("arm64") || name.contains("aarch64"))) arm64 = true;
                    }
                    if (!arm64) continue;
                    String url = release.optString("html_url", "");
                    if (!url.startsWith(
                        "https://github.com/KosmosSG/artcraft-android/releases/tag/lightcraft-")) continue;
                    latestCode = code;
                    latestName = tag.substring("lightcraft-v".length());
                    latestPage = url;
                }
                org.json.JSONObject result = new org.json.JSONObject();
                result.put("installed_version", installedName);
                result.put("installed_code", installedCode);
                result.put("status", "ok");
                if (latestName == null) {
                    result.put("state", "no_release");
                } else {
                    result.put("state", latestCode > installedCode
                        ? "update_available" : "up_to_date");
                    result.put("latest_version", latestName);
                    result.put("url", latestPage);
                    result.put("latest_code", latestCode);
                }
                lcUpdateResults.offer(result.toString());
            } catch (Exception error) {
                try {
                    org.json.JSONObject result = new org.json.JSONObject();
                    result.put("status", "error");
                    result.put("state", "error");
                    result.put("message", error.getMessage() == null
                        ? "Network or GitHub release check failed" : error.getMessage());
                    lcUpdateResults.offer(result.toString());
                } catch (Exception ignored) { }
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    public String lcPollUpdateResult() { return lcUpdateResults.poll(); }

    /** Open only an official LightCraft release; never install an unverified APK silently. */
    public void lcOpenUpdatePage(String url) {
        if (url == null ||
            !url.startsWith("https://github.com/KosmosSG/artcraft-android/releases/tag/lightcraft-"))
            return;
        runOnUiThread(() -> {
            try {
                startActivity(new android.content.Intent(android.content.Intent.ACTION_VIEW,
                    android.net.Uri.parse(url)));
            } catch (Exception error) {
                android.util.Log.w("LightCraftUpdate", "Could not open release page", error);
            }
        });
    }
