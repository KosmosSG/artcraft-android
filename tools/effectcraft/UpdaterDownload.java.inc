
    // ------------------------------------------------------------------------
    // EffectCraft: PhotoCraft-style download + PackageInstaller handoff.
    // Runs on the existing single-threaded update executor, never on UI/egui.
    // Only official KosmosSG release assets are accepted. The Android OS
    // requires user confirmation and enforces matching package and signing key.
    // ------------------------------------------------------------------------
    private final java.util.concurrent.atomic.AtomicBoolean ecDownloadBusy =
        new java.util.concurrent.atomic.AtomicBoolean(false);
    private volatile boolean ecInstallReceiverRegistered;

    /** Validate the expected published APK URL; never trust an arbitrary JSON URL. */
    private String ecTrustedReleaseAsset(org.json.JSONObject release) throws java.io.IOException {
        String version = release.optString("latest_version", "");
        if (ecVersion(version) == null) throw new java.io.IOException("Invalid update version");
        String expected = EC_DOWNLOAD_ROOT + EC_TAG_PREFIX + version + "/"
            + "EffectCraft-v" + version + "-arm64-v8a.apk";
        if (!expected.equals(release.optString("download_url", ""))) {
            throw new java.io.IOException("Refusing unverified update address");
        }
        return expected;
    }

    private void ecBeginDownload(org.json.JSONObject release) {
        if (!ecDownloadBusy.compareAndSet(false, true)) {
            ecFontMessage("An EffectCraft update is already downloading.");
            return;
        }
        final String verifiedUrl;
        final String targetVersion;
        try {
            verifiedUrl = ecTrustedReleaseAsset(release);
            targetVersion = release.getString("latest_version");
        } catch (Exception error) {
            ecDownloadBusy.set(false);
            ecFontMessage("Cannot download update: " + error.getMessage());
            return;
        }
        android.widget.ProgressBar progress = new android.widget.ProgressBar(
            this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setIndeterminate(true);
        progress.setMax(1000);
        progress.setPadding(48, 24, 48, 0);
        final java.util.concurrent.atomic.AtomicBoolean cancelled =
            new java.util.concurrent.atomic.AtomicBoolean(false);
        android.app.AlertDialog dialog = new android.app.AlertDialog.Builder(
                this, android.app.AlertDialog.THEME_DEVICE_DEFAULT_DARK)
            .setTitle("Downloading EffectCraft " + targetVersion)
            .setView(progress)
            .setNegativeButton("Cancel", (d, w) -> cancelled.set(true))
            .setCancelable(false).create();
        if (isFinishing()) {
            ecDownloadBusy.set(false);
            return;
        }
        dialog.show();
        ecUpdateExecutor.execute(() -> {
            java.io.File folder = new java.io.File(getCacheDir(), "effectcraft-updates");
            java.io.File partial = new java.io.File(folder, "effectcraft-update.part");
            java.io.File downloaded = new java.io.File(folder, "effectcraft-update.apk");
            String error = null;
            try {
                if (!folder.exists() && !folder.mkdirs())
                    throw new java.io.IOException("Cannot make private update cache");
                if (partial.exists() && !partial.delete())
                    throw new java.io.IOException("Cannot replace previous download");
                java.net.URL url = new java.net.URL(verifiedUrl);
                if (!"https".equalsIgnoreCase(url.getProtocol())
                    || !"github.com".equalsIgnoreCase(url.getHost()))
                    throw new java.io.IOException("Untrusted update URL");
                java.net.HttpURLConnection c = (java.net.HttpURLConnection)url.openConnection();
                try {
                    c.setConnectTimeout(12000);
                    c.setReadTimeout(18000);
                    c.setRequestProperty("User-Agent", "KosmosSG-EffectCraft-Android");
                    c.setRequestProperty("Accept", "application/octet-stream");
                    if (c.getResponseCode() != java.net.HttpURLConnection.HTTP_OK)
                        throw new java.io.IOException("Download HTTP " + c.getResponseCode());
                    final long expected = c.getContentLengthLong();
                    final long ceiling = 700L * 1024 * 1024;
                    if (expected > ceiling)
                        throw new java.io.IOException("APK exceeds update size limit");
                    long bytes = 0;
                    try (java.io.InputStream in = c.getInputStream();
                         java.io.FileOutputStream out = new java.io.FileOutputStream(partial)) {
                        byte[] buffer = new byte[64 * 1024];
                        int read;
                        while ((read = in.read(buffer)) != -1) {
                            if (cancelled.get())
                                throw new java.io.IOException("Download cancelled");
                            bytes += read;
                            if (bytes > ceiling)
                                throw new java.io.IOException("APK exceeds update size limit");
                            out.write(buffer, 0, read);
                            if (expected > 0) {
                                final int current = (int)Math.min(1000, bytes * 1000 / expected);
                                runOnUiThread(() -> {
                                    progress.setIndeterminate(false);
                                    progress.setProgress(current);
                                });
                            }
                        }
                        out.getFD().sync();
                    }
                    if (bytes < 128 * 1024 || (expected > 0 && expected != bytes))
                        throw new java.io.IOException("APK download was incomplete");
                } finally { c.disconnect(); }
                if (downloaded.exists() && !downloaded.delete())
                    throw new java.io.IOException("Cannot replace previous cached update");
                if (!partial.renameTo(downloaded))
                    throw new java.io.IOException("Cannot finalize downloaded APK");
                ecValidateDownloadedApk(downloaded, targetVersion);
            } catch (Exception failure) {
                error = failure.getMessage();
                android.util.Log.w("EffectCraftUpdater", "In-app update download", failure);
                // The cached APK must never be reused after a failed validation.
                partial.delete();
                downloaded.delete();
            }
            final String failure = error;
            runOnUiThread(() -> {
                ecDownloadBusy.set(false);
                dialog.dismiss();
                if (cancelled.get()) return;
                if (failure != null) {
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("EffectCraft Update")
                        .setMessage("Unable to download or install update:\n" + failure)
                        .setPositiveButton("OK", null).show();
                } else {
                    ecInstallDownloadedApk(downloaded);
                }
            });
        });
    }

    /** Reject an invalid APK/version/package before Android installer sees it. */
    private void ecValidateDownloadedApk(java.io.File apk, String version)
            throws java.io.IOException {
        if (!apk.isFile() || apk.length() < 128 * 1024)
            throw new java.io.IOException("Downloaded APK is missing or empty");
        android.content.pm.PackageInfo info = getPackageManager().getPackageArchiveInfo(
            apk.getAbsolutePath(), android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES);
        if (info == null || info.packageName == null)
            throw new java.io.IOException("Downloaded file is not an Android APK");
        if (!getPackageName().equals(info.packageName)) {
            throw new java.io.IOException(
                "This TEST app uses a separate package and cannot replace the "
                + "production EffectCraft APK. Install a compatible production-signed "
                + "release through your regular EffectCraft app.");
        }
        if (!version.equals(info.versionName))
            throw new java.io.IOException("Downloaded APK version does not match the release");
    }

    /** Android handles permission, signature validation and final confirmation. */
    private void ecInstallDownloadedApk(java.io.File apk) {
        if (android.os.Build.VERSION.SDK_INT >= 26
                && !getPackageManager().canRequestPackageInstalls()) {
            getSharedPreferences("effectcraft_updates", MODE_PRIVATE).edit()
                .putBoolean("pending_install", true).apply();
            ecFontMessage("Allow EffectCraft to install updates, then return to the app.");
            try {
                startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName())));
            } catch (Exception e) {
                ecFontMessage("Please enable installation permission in Android Settings.");
            }
            return;
        }
        ecUpdateExecutor.execute(() -> {
            try {
                android.content.pm.PackageInstaller installer =
                    getPackageManager().getPackageInstaller();
                android.content.pm.PackageInstaller.SessionParams params =
                    new android.content.pm.PackageInstaller.SessionParams(
                        android.content.pm.PackageInstaller.SessionParams.MODE_FULL_INSTALL);
                params.setAppPackageName(getPackageName());
                int sessionId = installer.createSession(params);
                try (android.content.pm.PackageInstaller.Session session =
                        installer.openSession(sessionId)) {
                    try (java.io.FileInputStream input = new java.io.FileInputStream(apk);
                         java.io.OutputStream output =
                            session.openWrite("effectcraft.apk", 0, apk.length())) {
                        byte[] bytes = new byte[65536];
                        int n;
                        while ((n = input.read(bytes)) != -1) output.write(bytes, 0, n);
                        session.fsync(output);
                    }
                    runOnUiThread(this::ecRegisterInstallReceiver);
                    android.content.Intent status = new android.content.Intent(
                        getPackageName() + ".EFFECTCRAFT_UPDATE_INSTALL_RESULT")
                        .setPackage(getPackageName());
                    int flags = android.app.PendingIntent.FLAG_UPDATE_CURRENT;
                    if (android.os.Build.VERSION.SDK_INT >= 31)
                        flags |= android.app.PendingIntent.FLAG_MUTABLE;
                    session.commit(android.app.PendingIntent.getBroadcast(this, sessionId,
                        status, flags).getIntentSender());
                }
            } catch (Exception error) {
                android.util.Log.w("EffectCraftUpdater", "In-app update install", error);
                runOnUiThread(() -> ecFontMessage(
                    "Cannot install update: " + error.getMessage()));
            }
        });
    }

    private void ecRegisterInstallReceiver() {
        if (ecInstallReceiverRegistered) return;
        ecInstallReceiverRegistered = true;
        android.content.BroadcastReceiver receiver = new android.content.BroadcastReceiver() {
            @Override public void onReceive(android.content.Context context, Intent intent) {
                if (!((getPackageName() + ".EFFECTCRAFT_UPDATE_INSTALL_RESULT")
                        .equals(intent.getAction()))) return;
                int status = intent.getIntExtra(
                    android.content.pm.PackageInstaller.EXTRA_STATUS,
                    android.content.pm.PackageInstaller.STATUS_FAILURE);
                if (status == android.content.pm.PackageInstaller.STATUS_PENDING_USER_ACTION) {
                    Intent confirm = intent.getParcelableExtra(Intent.EXTRA_INTENT);
                    if (confirm != null) {
                        confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        context.startActivity(confirm);
                    }
                } else if (status == android.content.pm.PackageInstaller.STATUS_SUCCESS) {
                    ecFontMessage("EffectCraft update installed.");
                } else {
                    String description = intent.getStringExtra(
                        android.content.pm.PackageInstaller.EXTRA_STATUS_MESSAGE);
                    ecFontMessage("Update installation did not complete: "
                        + (description == null ? "Android rejected the package" : description));
                }
            }
        };
        android.content.IntentFilter filter = new android.content.IntentFilter(
            getPackageName() + ".EFFECTCRAFT_UPDATE_INSTALL_RESULT");
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            getApplicationContext().registerReceiver(receiver, filter,
                android.content.Context.RECEIVER_NOT_EXPORTED);
        } else {
            getApplicationContext().registerReceiver(receiver, filter);
        }
    }

    @Override protected void onResume() {
        super.onResume();
        boolean pending = getSharedPreferences("effectcraft_updates", MODE_PRIVATE)
            .getBoolean("pending_install", false);
        if (!pending) return;
        if (android.os.Build.VERSION.SDK_INT >= 26
                && !getPackageManager().canRequestPackageInstalls()) return;
        getSharedPreferences("effectcraft_updates", MODE_PRIVATE).edit()
            .putBoolean("pending_install", false).apply();
        java.io.File apk = new java.io.File(new java.io.File(
            getCacheDir(), "effectcraft-updates"), "effectcraft-update.apk");
        if (apk.isFile()) {
            try {
                ecValidateDownloadedApk(apk, getPackageManager()
                    .getPackageArchiveInfo(apk.getAbsolutePath(),
                        android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES).versionName);
                getWindow().getDecorView().post(() -> ecInstallDownloadedApk(apk));
            } catch (Exception error) {
                ecFontMessage("Downloaded update is no longer valid.");
            }
        }
    }
