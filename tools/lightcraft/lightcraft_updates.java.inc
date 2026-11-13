
    // LightCraft-only GitHub update checks. This queue is independent of SAF/IME.
    private final java.util.concurrent.ConcurrentLinkedQueue<String> lcUpdateResults =
            new java.util.concurrent.ConcurrentLinkedQueue<>();
    private final java.util.concurrent.ExecutorService lcUpdateIo =
            java.util.concurrent.Executors.newSingleThreadExecutor();

    // App-private SharedPreferences survive upgrades of com.artcraft.lightcraft.
    // The first launch defaults to OFF; no network connection is used at startup
    // unless this has been explicitly enabled.
    public boolean lcGetStartupUpdateCheck() {
        return getSharedPreferences("lightcraft.android.updates", MODE_PRIVATE)
            .getBoolean("check_at_startup", false);
    }

    public void lcSetStartupUpdateCheck(boolean enabled) {
        getSharedPreferences("lightcraft.android.updates", MODE_PRIVATE).edit()
            .putBoolean("check_at_startup", enabled).apply();
    }

    // User-selected channel is app-private and survives in-place upgrades.
    // This release enables previews because the owner opted in for all Craft apps.
    // Individual users can switch back to stable-only without uninstalling.
    public boolean lcGetIncludePreviewUpdates() {
        return getSharedPreferences("lightcraft.android.updates", MODE_PRIVATE)
            .getBoolean("include_preview_releases", true);
    }

    public void lcSetIncludePreviewUpdates(boolean enabled) {
        getSharedPreferences("lightcraft.android.updates", MODE_PRIVATE).edit()
            .putBoolean("include_preview_releases", enabled).apply();
    }

    public String lcGetInstalledVersion() {
        try {
            android.content.pm.PackageInfo info =
                getPackageManager().getPackageInfo(getPackageName(), 0);
            return info.versionName == null ? "unknown" : info.versionName;
        } catch (Exception ignored) {
            return "unknown";
        }
    }

    /** Initiate a bounded, asynchronous LightCraft-only GitHub check. */
    // Asynchronous download source selected by the last official release check.
    private volatile String lcLatestApkUrl = null;
    private volatile long lcLatestApkSize = 0L;
    private volatile String lcLatestVersion = null;
    private final java.util.concurrent.atomic.AtomicBoolean lcDownloading =
        new java.util.concurrent.atomic.AtomicBoolean(false);
    private volatile java.io.File lcPendingUpdateApk = null;

    // Android's stylus hover is observed before being forwarded to winit.
    private volatile boolean lcPenHovering = false;
    private volatile float lcPenX = 0.0f, lcPenY = 0.0f;
    private final java.util.concurrent.atomic.AtomicBoolean lcPenButton =
        new java.util.concurrent.atomic.AtomicBoolean(false);
    public boolean lcRecordStylusMotion(android.view.MotionEvent e) {
        if (e == null || !e.isFromSource(android.view.InputDevice.SOURCE_STYLUS)) return false;
        int action = e.getActionMasked();
        if (action == android.view.MotionEvent.ACTION_HOVER_ENTER ||
            action == android.view.MotionEvent.ACTION_HOVER_MOVE) {
            lcPenHovering = true;
            lcPenX = e.getX();
            lcPenY = e.getY();
        } else if (action == android.view.MotionEvent.ACTION_HOVER_EXIT) {
            lcPenHovering = false;
        } else if (action == android.view.MotionEvent.ACTION_BUTTON_PRESS &&
            (e.getActionButton() & android.view.MotionEvent.BUTTON_STYLUS_PRIMARY) != 0) {
            lcPenButton.set(true);
            return true;
        }
        return false;
    }
    public String lcStylusHoverSnapshot() {
        return lcPenHovering ? lcPenX + "," + lcPenY : "";
    }
    public boolean lcPollStylusButton() { return lcPenButton.getAndSet(false); }

    @Override public boolean dispatchKeyEvent(android.view.KeyEvent e) {
        android.view.InputDevice device = e == null ? null : e.getDevice();
        String name = device == null ? "" : device.getName();
        if (name != null && name.contains("Magic-Pencil 4s") &&
            (e.getKeyCode() == android.view.KeyEvent.KEYCODE_DPAD_DOWN ||
             e.getKeyCode() == android.view.KeyEvent.KEYCODE_DPAD_UP)) {
            if (e.getAction() == android.view.KeyEvent.ACTION_UP && e.getRepeatCount() == 0)
                lcPenButton.set(true);
            return true;
        }
        return super.dispatchKeyEvent(e);
    }

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
                final boolean includePreview = lcGetIncludePreviewUpdates();
                lcLatestApkUrl = null;
                lcLatestApkSize = 0L;
                lcLatestVersion = null;
                long latestCode = -1L;
                String selectedApk = null;
                long selectedSize = 0L;
                String latestName = null;
                String latestPage = null;
                for (int i = 0; i < releases.length(); i++) {
                    org.json.JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft") ||
                        (!includePreview && release.optBoolean("prerelease"))) continue;
                    String tag = release.optString("tag_name", "");
                    java.util.regex.Matcher m = java.util.regex.Pattern.compile(
                        "^lightcraft-v([0-9]+)\\.([0-9]+)\\.([0-9]+)-android\\.([1-9][0-9]*)$"
                    ).matcher(tag);
                    if (!m.matches()) continue;
                    int major = Integer.parseInt(m.group(1));
                    int minor = Integer.parseInt(m.group(2));
                    int patch = Integer.parseInt(m.group(3));
                    int android = Integer.parseInt(m.group(4));
                    // Matches the Android-only ArtCraft versionCode scheme; accept only
                    // unambiguous bounded version components and real ARM64 APK assets.
                    if (major > 255 || minor > 255 || patch > 205 || android > 50) continue;
                    // Avoid carrying Android revision increments into a different
                    // patch/versionCode slot; published builds must use this scheme.
                    if (patch + android > 255) continue;
                    long code = (1L << 24) | (major << 16) | (minor << 8) | patch;
                    code += android;
                    if (code <= latestCode) continue;
                    org.json.JSONArray assets = release.optJSONArray("assets");
                    // Reject similarly named APKs, other Craft apps, incomplete
                    // uploads, or any unapproved ABI. Older PhotoCraft-style
                    // filename and the current suite canonical alias are both
                    // accepted, but ONLY for this exact LightCraft tag.
                    String version = tag.substring("lightcraft-v".length());
                    String canonical = "LightCraft-v" + version + "-arm64-v8a.apk";
                    String legacy = "LightCraft-" + version + "-arm64-v8a.apk";
                    boolean exactAsset = false;
                    String foundUrl = null;
                    long foundSize = 0L;
                    if (assets != null) for (int j = 0; j < assets.length(); j++) {
                        org.json.JSONObject asset = assets.optJSONObject(j);
                        if (asset == null) continue;
                        String name = asset.optString("name", "");
                        String state = asset.optString("state", "");
                        if ((canonical.equals(name) || legacy.equals(name))
                            && "uploaded".equals(state) && asset.optLong("size", 0L) > 0L) {
                            exactAsset = true;
                            foundUrl = asset.optString("browser_download_url", "");
                            foundSize = asset.optLong("size", 0L);
                            break;
                        }
                    }
                    if (!exactAsset) continue;
                    String url = release.optString("html_url", "");
                    if (!url.startsWith(
                        "https://github.com/KosmosSG/artcraft-android/releases/tag/lightcraft-")) continue;
                    latestCode = code;
                    latestName = tag.substring("lightcraft-v".length());
                    latestPage = url;
                    selectedApk = foundUrl;
                    selectedSize = foundSize;
                }
                org.json.JSONObject result = new org.json.JSONObject();
                lcLatestApkUrl = selectedApk;
                lcLatestApkSize = selectedSize;
                lcLatestVersion = latestName;
                result.put("installed_version", installedName);
                result.put("installed_code", installedCode);
                result.put("channel", includePreview ? "stable_and_preview" : "stable");
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

    private void lcUpdateEvent(String state, String message, int percent) {
        try {
            org.json.JSONObject object = new org.json.JSONObject();
            object.put("state", state);
            object.put("status", "download");
            object.put("message", message);
            object.put("progress", percent);
            lcUpdateResults.offer(object.toString());
        } catch (Exception ignored) { }
    }
    // Explicit user permission is required; only exact owner LightCraft APK.
    public void lcBeginUpdateDownload() {
        String url = lcLatestApkUrl;
        long bytes = lcLatestApkSize;
        if (url == null ||
            !url.startsWith("https://github.com/KosmosSG/artcraft-android/releases/download/lightcraft-v") ||
            !url.endsWith("-arm64-v8a.apk") || bytes < 1 || bytes > 1073741824L) {
            lcUpdateEvent("download_failed", "No approved LightCraft ARM64 APK is available.", 0);
            return;
        }
        runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
            .setTitle("LightCraft " + lcLatestVersion)
            .setMessage("Download the LightCraft update in the app? Save your work. " +
                "Android will request confirmation before installing.")
            .setNegativeButton("Cancel", (d,w) ->
                lcUpdateEvent("download_cancelled", "Download cancelled.", 0))
            .setPositiveButton("Download", (d,w) -> lcDownloadApk(url, bytes))
            .show());
    }
    private void lcDownloadApk(String url, long expected) {
        if (!lcDownloading.compareAndSet(false, true)) return;
        lcUpdateEvent("download_started", "Downloading LightCraft…", 0);
        lcUpdateIo.execute(() -> {
            java.io.File partial = new java.io.File(getCacheDir(), "lc-update.part");
            java.io.File apk = new java.io.File(getCacheDir(), "lc-update.apk");
            java.net.HttpURLConnection conn = null;
            try {
                conn = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(20000);
                conn.setInstanceFollowRedirects(true);
                conn.setRequestProperty("User-Agent", "LightCraft-Android-Updater");
                if (conn.getResponseCode() != 200)
                    throw new java.io.IOException("HTTP " + conn.getResponseCode());
                String host = conn.getURL().getHost();
                if (!("github.com".equals(host) ||
                      "release-assets.githubusercontent.com".equals(host) ||
                      "objects.githubusercontent.com".equals(host)))
                    throw new java.io.IOException("Unexpected download host");
                partial.delete();
                long done = 0;
                int last = -1;
                try (java.io.InputStream in = conn.getInputStream();
                     java.io.OutputStream out = new java.io.FileOutputStream(partial)) {
                    byte[] buf = new byte[65536];
                    int count;
                    while ((count = in.read(buf)) != -1) {
                        done += count;
                        if (done > expected) throw new java.io.IOException("APK size mismatch");
                        out.write(buf, 0, count);
                        int progress = (int)(done * 100 / expected);
                        if (progress / 5 != last / 5) {
                            last = progress;
                            lcUpdateEvent("downloading", "Downloading LightCraft… " + progress + "%", progress);
                        }
                    }
                }
                if (done != expected || !partial.renameTo(apk))
                    throw new java.io.IOException("Incomplete APK download");
                android.content.pm.PackageInfo info =
                    getPackageManager().getPackageArchiveInfo(apk.getAbsolutePath(), 0);
                if (info == null || !"com.artcraft.lightcraft".equals(info.packageName))
                    throw new java.io.IOException("APK package identity mismatch");
                lcPendingUpdateApk = apk;
                if (!"com.artcraft.lightcraft".equals(getPackageName())) {
                    lcUpdateEvent("download_test_only",
                        "Verified APK downloaded; isolated TEST package cannot replace production LightCraft.", 100);
                } else {
                    lcUpdateEvent("download_complete", "APK downloaded; starting Android installer…", 100);
                    runOnUiThread(this::lcInstallDownloadedUpdate);
                }
            } catch (Exception ex) {
                partial.delete(); apk.delete(); lcPendingUpdateApk = null;
                lcUpdateEvent("download_failed", "Download failed: " + ex.getMessage(), 0);
            } finally {
                if (conn != null) conn.disconnect();
                lcDownloading.set(false);
            }
        });
    }
    public void lcResumeDownloadedUpdate() {
        if (lcPendingUpdateApk != null && getPackageManager().canRequestPackageInstalls()) {
            runOnUiThread(this::lcInstallDownloadedUpdate);
        }
    }
    private android.content.BroadcastReceiver lcInstallReceiver;
    private void lcInstallDownloadedUpdate() {
        java.io.File apk = lcPendingUpdateApk;
        if (!"com.artcraft.lightcraft".equals(getPackageName()) || apk == null || !apk.isFile()) return;
        if (!getPackageManager().canRequestPackageInstalls()) {
            lcUpdateEvent("install_permission", "Allow app updates in Android settings, then return.", 100);
            startActivity(new android.content.Intent(
                android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                android.net.Uri.parse("package:" + getPackageName())));
            return;
        }
        try {
            android.content.pm.PackageInstaller installer = getPackageManager().getPackageInstaller();
            android.content.pm.PackageInstaller.SessionParams params =
                new android.content.pm.PackageInstaller.SessionParams(
                    android.content.pm.PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            params.setAppPackageName("com.artcraft.lightcraft");
            int id = installer.createSession(params);
            try (android.content.pm.PackageInstaller.Session session = installer.openSession(id);
                 java.io.InputStream in = new java.io.FileInputStream(apk);
                 java.io.OutputStream out = session.openWrite("lightcraft.apk", 0, apk.length())) {
                byte[] buf = new byte[65536];
                int count;
                while ((count = in.read(buf)) != -1) out.write(buf, 0, count);
                session.fsync(out);
                lcRegisterInstallerReceiver();
                android.content.Intent result = new android.content.Intent(
                    "com.artcraft.lightcraft.UPDATE_INSTALLED").setPackage(getPackageName());
                int flags = android.app.PendingIntent.FLAG_UPDATE_CURRENT |
                    (android.os.Build.VERSION.SDK_INT >= 31 ? android.app.PendingIntent.FLAG_MUTABLE : 0);
                session.commit(android.app.PendingIntent.getBroadcast(
                    this, id, result, flags).getIntentSender());
            }
            lcUpdateEvent("install_submitted", "Waiting for Android installation confirmation…", 100);
        } catch (Exception ex) {
            lcUpdateEvent("install_failed", "Installer error: " + ex.getMessage(), 100);
        }
    }
    private void lcRegisterInstallerReceiver() {
        if (lcInstallReceiver != null) return;
        lcInstallReceiver = new android.content.BroadcastReceiver() {
            @Override public void onReceive(android.content.Context context, android.content.Intent intent) {
                int status = intent.getIntExtra(android.content.pm.PackageInstaller.EXTRA_STATUS,
                    android.content.pm.PackageInstaller.STATUS_FAILURE);
                if (status == android.content.pm.PackageInstaller.STATUS_PENDING_USER_ACTION) {
                    android.content.Intent confirm = intent.getParcelableExtra(android.content.Intent.EXTRA_INTENT);
                    if (confirm != null) {
                        confirm.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(confirm);
                    }
                } else {
                    lcUpdateEvent(status == android.content.pm.PackageInstaller.STATUS_SUCCESS
                        ? "install_success" : "install_failed",
                        status == android.content.pm.PackageInstaller.STATUS_SUCCESS
                            ? "LightCraft updated." : "Update was cancelled or the APK signing key differs.", 100);
                    lcPendingUpdateApk = null;
                    try { getApplicationContext().unregisterReceiver(this); } catch (Exception ignored) {}
                    lcInstallReceiver = null;
                }
            }
        };
        android.content.IntentFilter filter =
            new android.content.IntentFilter("com.artcraft.lightcraft.UPDATE_INSTALLED");
        if (android.os.Build.VERSION.SDK_INT >= 33)
            getApplicationContext().registerReceiver(lcInstallReceiver, filter,
                android.content.Context.RECEIVER_NOT_EXPORTED);
        else getApplicationContext().registerReceiver(lcInstallReceiver, filter);
    }
