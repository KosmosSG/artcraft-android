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

    private static long[] dcVersion(String text) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("([0-9]+)\\.([0-9]+)\\.([0-9]+)-android\\.([1-9][0-9]*)").matcher(text);
        if (!matcher.matches()) return null;
        try {
            return new long[]{Long.parseLong(matcher.group(1)), Long.parseLong(matcher.group(2)), Long.parseLong(matcher.group(3)), Long.parseLong(matcher.group(4))};
        } catch (NumberFormatException error) { return null; }
    }

    private static boolean dcNewer(long[] candidate, long[] installed) {
        if (candidate == null || installed == null) return false;
        for (int i = 0; i < 4; i++) {
            if (candidate[i] != installed[i]) return candidate[i] > installed[i];
        }
        return false;
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
            java.net.HttpURLConnection connection = null;
            try {
                connection = (java.net.HttpURLConnection) new java.net.URL("https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100").openConnection();
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(8000);
                connection.setRequestProperty("Accept", "application/vnd.github+json");
                connection.setRequestProperty("User-Agent", "DesignCraft-Android");
                if (connection.getResponseCode() != 200) throw new java.io.IOException("GitHub returned HTTP " + connection.getResponseCode());
                java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
                try (InputStream input = connection.getInputStream()) {
                    byte[] chunk = new byte[8192];
                    int read;
                    while ((read = input.read(chunk)) != -1) {
                        if (buffer.size() + read > 1024 * 1024) throw new java.io.IOException("Release list exceeds size limit");
                        buffer.write(chunk, 0, read);
                    }
                }
                JSONArray releases = new JSONArray(buffer.toString("UTF-8"));
                String installed = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
                long[] best = dcVersion(installed == null ? "" : installed);
                String bestTag = null, bestUrl = null;
                for (int i = 0; i < releases.length(); i++) {
                    JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft") || release.optBoolean("prerelease")) continue;
                    String tag = release.optString("tag_name", "");
                    if (!tag.startsWith("designcraft-v")) continue;
                    long[] candidate = dcVersion(tag.substring("designcraft-v".length()));
                    JSONArray assets = release.optJSONArray("assets");
                    boolean hasApk = false;
                    if (assets != null) for (int j = 0; j < assets.length(); j++) {
                        JSONObject asset = assets.optJSONObject(j);
                        if (asset == null) continue;
                        String name = asset.optString("name", "");
                        if (name.equals("DesignCraft-" + tag.substring("designcraft-v".length()) + "-arm64-v8a.apk")) hasApk = true;
                    }
                    String url = release.optString("html_url", "");
                    if (hasApk && dcNewer(candidate, best) && url.equals("https://github.com/KosmosSG/artcraft-android/releases/tag/" + tag)) {
                        best = candidate; bestTag = tag; bestUrl = url;
                    }
                }
                final String tag = bestTag, url = bestUrl;
                if (manual || tag != null) runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    android.app.AlertDialog.Builder dialog = new android.app.AlertDialog.Builder(this).setTitle("DesignCraft updates")
                        .setMessage(tag == null ? "Installed: " + installed + "\nNo newer published DesignCraft ARM64 release was found." : "Installed: " + installed + "\nAvailable: " + tag + "\nConfirm the production signing identity before installation.")
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
                if (connection != null) connection.disconnect();
                dcChecking.set(false);
            }
        });
    }
