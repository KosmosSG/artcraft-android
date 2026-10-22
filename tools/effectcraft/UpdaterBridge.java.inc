
    // EffectCraft-only Android GitHub Releases update bridge. This class is inserted
    // into the generated EffectCraftActivity on the isolated EffectCraft CI checkout.
    private static final String EC_RELEASE_API =
        "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100&page=";
    private static final String EC_TAG_PREFIX = "effectcraft-v";
    private static final String EC_DOWNLOAD_ROOT =
        "https://github.com/KosmosSG/artcraft-android/releases/download/";
    private final java.util.concurrent.ExecutorService ecUpdateExecutor =
        java.util.concurrent.Executors.newSingleThreadExecutor();
    private final java.util.concurrent.ConcurrentLinkedQueue<String> ecUpdateResults =
        new java.util.concurrent.ConcurrentLinkedQueue<>();

    private static int[] ecVersion(String version) {
        if (version == null || !version.matches("[0-9]{1,6}\\.[0-9]{1,6}\\.[0-9]{1,6}-android\\.[1-9][0-9]{0,5}"))
            return null;
        try {
            String[] components = version.replace("-android.", ".").split("\\.");
            if (components.length != 4) return null;
            int[] numbers = new int[4];
            for (int i = 0; i < 4; i++) numbers[i] = Integer.parseInt(components[i]);
            return numbers;
        } catch (NumberFormatException error) { return null; }
    }

    private static int ecCompare(int[] a, int[] b) {
        for (int i = 0; i < 4; i++) {
            if (a[i] != b[i]) return Integer.compare(a[i], b[i]);
        }
        return 0;
    }

    public String ecPollUpdateResult() {
        return ecUpdateResults.poll();
    }

    // Network I/O always happens on a worker, never Android UI/egui event thread.
    public void ecCheckForUpdates() {
        ecUpdateExecutor.execute(() -> {
            try {
                String installed = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
                int[] current = ecVersion(installed);
                if (current == null) throw new java.io.IOException("Installed EffectCraft version cannot be compared safely");
                String selectedVersion = null;
                String selectedPage = null;
                String selectedDownload = null;
                int[] selected = null;
                for (int page = 1; page <= 5; page++) {
                    java.net.HttpURLConnection connection = null;
                    org.json.JSONArray releases;
                    try {
                        connection = (java.net.HttpURLConnection)
                            new java.net.URL(EC_RELEASE_API + page).openConnection();
                        connection.setConnectTimeout(10000);
                        connection.setReadTimeout(10000);
                        connection.setRequestProperty("User-Agent", "KosmosSG-EffectCraft-Android");
                        connection.setRequestProperty("Accept", "application/vnd.github+json");
                        if (connection.getResponseCode() != 200)
                            throw new java.io.IOException("GitHub returned HTTP " + connection.getResponseCode());
                        java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
                        try (java.io.InputStream input = connection.getInputStream()) {
                            byte[] chunk = new byte[8192];
                            int count;
                            while ((count = input.read(chunk)) != -1) {
                                if (buffer.size() + count > 1024 * 1024)
                                    throw new java.io.IOException("GitHub response exceeds 1 MiB");
                                buffer.write(chunk, 0, count);
                            }
                        }
                        releases = new org.json.JSONArray(
                            new String(buffer.toByteArray(), java.nio.charset.StandardCharsets.UTF_8));
                    } finally {
                        if (connection != null) connection.disconnect();
                    }
                    for (int i = 0; i < releases.length(); i++) {
                        org.json.JSONObject release = releases.optJSONObject(i);
                        if (release == null || release.optBoolean("draft") || release.optBoolean("prerelease"))
                            continue;
                        String tag = release.optString("tag_name", "");
                        if (!tag.startsWith(EC_TAG_PREFIX)) continue;
                        String version = tag.substring(EC_TAG_PREFIX.length());
                        int[] candidate = ecVersion(version);
                        if (candidate == null || (selected != null && ecCompare(candidate, selected) <= 0))
                            continue;
                        String assetName = "EffectCraft-" + version + "-arm64-v8a.apk";
                        String requiredUrl = EC_DOWNLOAD_ROOT + tag + "/" + assetName;
                        org.json.JSONArray assets = release.optJSONArray("assets");
                        int matches = 0;
                        if (assets != null) {
                            for (int a = 0; a < assets.length(); a++) {
                                org.json.JSONObject asset = assets.optJSONObject(a);
                                if (asset != null && assetName.equals(asset.optString("name"))
                                    && requiredUrl.equals(asset.optString("browser_download_url")))
                                    matches++;
                            }
                        }
                        if (matches != 1) continue;
                        String requiredPage = "https://github.com/KosmosSG/artcraft-android/releases/tag/" + tag;
                        if (!requiredPage.equals(release.optString("html_url"))) continue;
                        selected = candidate;
                        selectedVersion = version;
                        selectedPage = requiredPage;
                        selectedDownload = requiredUrl;
                    }
                    if (releases.length() < 100) break;
                    if (page == 5) throw new java.io.IOException("Too many releases to check safely");
                }
                org.json.JSONObject result = new org.json.JSONObject();
                result.put("installed_version", installed);
                if (selected == null) {
                    result.put("state", "no_release");
                } else {
                    result.put("latest_version", selectedVersion);
                    result.put("release_url", selectedPage);
                    if (ecCompare(selected, current) > 0) {
                        result.put("state", "update_available");
                        result.put("download_url", selectedDownload);
                    } else {
                        result.put("state", "up_to_date");
                    }
                }
                ecUpdateResults.offer(result.toString());
            } catch (Exception error) {
                android.util.Log.w("EffectCraftUpdater", "Update check failed", error);
                org.json.JSONObject result = new org.json.JSONObject();
                try {
                    result.put("state", "error");
                    result.put("message", error.getMessage() == null ? "GitHub unavailable" : error.getMessage());
                } catch (org.json.JSONException ignored) {}
                ecUpdateResults.offer(result.toString());
            }
        });
    }
