    // Manual DeckCraft-only updates. No suite-wide /latest endpoint or automatic installs.
    private final java.util.concurrent.atomic.AtomicBoolean deckUpdateBusy = new java.util.concurrent.atomic.AtomicBoolean();
    private File deckVerifiedApk;
    private static final int DECK_SAVE_UPDATE = 0x5071;

    private void deckMessage(String message) {
        runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
            .setTitle("DeckCraft Updates").setMessage(message).setPositiveButton("OK", null).show());
    }
    private static java.net.HttpURLConnection deckConnection(String address) throws Exception {
        java.net.URL url = new java.net.URL(address);
        if (!"https".equals(url.getProtocol())) throw new Exception("Update URL is not HTTPS");
        java.net.HttpURLConnection c = (java.net.HttpURLConnection) url.openConnection();
        c.setConnectTimeout(15000); c.setReadTimeout(30000);
        c.setRequestProperty("User-Agent", "DeckCraft-Android-Updater");
        return c;
    }
    private static long[] deckVersion(String value) {
        if (value == null) return null;
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("^(?:deckcraft-v)?(\\d+)\\.(\\d+)\\.(\\d+)(?:-android\\.(\\d+))?$").matcher(value);
        if (!m.matches()) return null;
        try { return new long[]{Long.parseLong(m.group(1)), Long.parseLong(m.group(2)),
            Long.parseLong(m.group(3)), m.group(4) == null ? 0 : Long.parseLong(m.group(4))}; }
        catch (NumberFormatException e) { return null; }
    }
    private static int deckCompare(long[] a, long[] b) {
        for (int i = 0; i < 4; i++) { int c = Long.compare(a[i], b[i]); if (c != 0) return c; }
        return 0;
    }
    public void deckCheckUpdates() {
        if (!deckUpdateBusy.compareAndSet(false, true)) { deckMessage("An update check, download or save is already running."); return; }
        runOnUiThread(() -> android.widget.Toast.makeText(this, "Checking DeckCraft updates…", android.widget.Toast.LENGTH_SHORT).show());
        io.execute(() -> {
            try {
                android.content.pm.PackageInfo installed = getPackageManager().getPackageInfo(getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
                long[] current = deckVersion(installed.versionName);
                if (current == null) throw new Exception("Installed version cannot be compared safely");
                JSONObject best = null; long[] bestVersion = current; String bestName = null;
                for (int page = 1; page <= 5; page++) {
                    java.net.HttpURLConnection c = deckConnection("https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100&page=" + page);
                    c.setRequestProperty("Accept", "application/vnd.github+json");
                    JSONArray releases;
                    try {
                        if (c.getResponseCode() != 200) throw new Exception("GitHub returned HTTP " + c.getResponseCode());
                        try (InputStream in = c.getInputStream(); java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
                            byte[] b = new byte[8192]; int n;
                            while ((n = in.read(b)) != -1) { if (out.size() + n > 8 * 1024 * 1024) throw new Exception("Release list too large"); out.write(b, 0, n); }
                            releases = new JSONArray(out.toString("UTF-8"));
                        }
                    } finally { c.disconnect(); }
                    for (int i = 0; i < releases.length(); i++) {
                        JSONObject r = releases.getJSONObject(i); String tag = r.optString("tag_name");
                        if (!tag.startsWith("deckcraft-v") || r.optBoolean("draft") || r.optBoolean("prerelease")) continue;
                        long[] version = deckVersion(tag);
                        if (version == null || deckCompare(version, bestVersion) <= 0) continue;
                        JSONArray assets = r.optJSONArray("assets"); if (assets == null) continue;
                        for (int j = 0; j < assets.length(); j++) {
                            JSONObject a = assets.getJSONObject(j); String name = a.optString("name").toLowerCase(java.util.Locale.ROOT);
                            if (!name.startsWith("deckcraft-") || !name.contains("arm64") || !name.endsWith(".apk") || name.contains("debug") || name.contains("unsigned")) continue;
                            if (!a.optString("browser_download_url").startsWith("https://github.com/KosmosSG/artcraft-android/releases/download/")) continue;
                            if (!a.optString("digest").matches("sha256:[0-9a-fA-F]{64}")) continue;
                            if (a.optLong("size") <= 0 || a.optLong("size") > 512L * 1024 * 1024) continue;
                            best = a; bestVersion = version; bestName = tag; break;
                        }
                    }
                    if (releases.length() < 100) break;
                }
                if (best == null) { deckMessage("No newer compatible DeckCraft ARM64 release with verification metadata found. Installed: " + installed.versionName); return; }
                final JSONObject asset = best; final String label = bestName;
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this).setTitle("DeckCraft update found")
                    .setMessage(label + "\nInstalled: " + installed.versionName + "\nDownload to verify package, version, ARM64 and original signing certificate.")
                    .setNegativeButton("Cancel", null).setPositiveButton("Download and verify", (dialog, which) -> deckDownloadUpdate(asset, label)).show());
            } catch (Exception e) { deckMessage("Could not check updates. Check your internet connection and try again.\n" + e.getMessage()); }
            finally { deckUpdateBusy.set(false); }
        });
    }
    private static java.util.Set<String> deckCertificates(android.content.pm.PackageInfo info) throws Exception {
        if (info == null || info.signingInfo == null) throw new Exception("Unsigned or unreadable APK");
        java.util.Set<String> result = new java.util.HashSet<>();
        android.content.pm.Signature[] signers = info.signingInfo.getApkContentsSigners();
        if (signers == null) throw new Exception("Unsigned APK");
        for (android.content.pm.Signature s : signers)
            result.add(android.util.Base64.encodeToString(java.security.MessageDigest.getInstance("SHA-256").digest(s.toByteArray()), android.util.Base64.NO_WRAP));
        if (result.isEmpty()) throw new Exception("Unsigned APK");
        return result;
    }
    private void deckDownloadUpdate(JSONObject asset, String tag) {
        if (!deckUpdateBusy.compareAndSet(false, true)) { deckMessage("An update operation is already running."); return; }
        io.execute(() -> {
            File apk = new File(getCacheDir(), "DeckCraft-verified-update.apk");
            boolean saving = false;
            try {
                java.net.HttpURLConnection c = deckConnection(asset.getString("browser_download_url"));
                c.setRequestProperty("Accept", "application/octet-stream");
                long total = 0;
                java.security.MessageDigest hash = java.security.MessageDigest.getInstance("SHA-256");
                try {
                    if (c.getResponseCode() != 200) throw new Exception("Download HTTP " + c.getResponseCode());
                    try (InputStream in = c.getInputStream(); FileOutputStream out = new FileOutputStream(apk)) {
                        byte[] b = new byte[65536]; int n;
                        while ((n = in.read(b)) != -1) { total += n; if (total > 512L * 1024 * 1024) throw new Exception("APK too large"); out.write(b, 0, n); hash.update(b, 0, n); }
                    }
                } finally { c.disconnect(); }
                if (total != asset.getLong("size")) throw new Exception("Incomplete APK download");
                StringBuilder hex = new StringBuilder(); for (byte b : hash.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
                if (!asset.getString("digest").equalsIgnoreCase("sha256:" + hex)) throw new Exception("APK hash mismatch");
                android.content.pm.PackageInfo installed = getPackageManager().getPackageInfo(getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
                android.content.pm.PackageInfo next = getPackageManager().getPackageArchiveInfo(apk.getAbsolutePath(), PackageManager.GET_SIGNING_CERTIFICATES);
                if (next == null || !getPackageName().equals(next.packageName)) throw new Exception("Wrong package");
                if (!deckCertificates(installed).equals(deckCertificates(next))) throw new Exception("APK does not have the original DeckCraft signing identity");
                long[] version = deckVersion(next.versionName), expected = deckVersion(tag), current = deckVersion(installed.versionName);
                if (version == null || expected == null || current == null || deckCompare(version, expected) != 0 || deckCompare(version, current) <= 0 || next.getLongVersionCode() <= installed.getLongVersionCode()) throw new Exception("Older, mismatched or non-upgrade APK version");
                if (next.applicationInfo == null || next.applicationInfo.minSdkVersion > Build.VERSION.SDK_INT) throw new Exception("Incompatible Android version");
                boolean arm64 = false;
                try (java.util.zip.ZipFile zip = new java.util.zip.ZipFile(apk)) {
                    java.util.Enumeration<? extends java.util.zip.ZipEntry> entries = zip.entries();
                    while (entries.hasMoreElements()) { String name = entries.nextElement().getName(); if (name.startsWith("lib/") && name.endsWith(".so")) { if (!name.startsWith("lib/arm64-v8a/")) throw new Exception("Incompatible native architecture"); arm64 = true; } }
                }
                if (!arm64) throw new Exception("ARM64 native library missing");
                deckVerifiedApk = apk;
                saving = true;
                runOnUiThread(() -> {
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                        .setType("application/vnd.android.package-archive").putExtra(Intent.EXTRA_TITLE, asset.optString("name", "DeckCraft-update.apk"));
                    try { startActivityForResult(intent, DECK_SAVE_UPDATE); }
                    catch (Exception e) { deckVerifiedApk = null; apk.delete(); deckUpdateBusy.set(false); deckMessage("Could not open APK save picker: " + e.getMessage()); }
                });
            } catch (Exception e) { apk.delete(); deckMessage("Update rejected: " + e.getMessage()); }
            finally { if (!saving) deckUpdateBusy.set(false); }
        });
    }
    private void deckSaveUpdate(int resultCode, Intent data) {
        final File apk = deckVerifiedApk; deckVerifiedApk = null;
        if (apk == null) { deckUpdateBusy.set(false); return; }
        if (resultCode != RESULT_OK || data == null || data.getData() == null) { apk.delete(); deckUpdateBusy.set(false); return; }
        final Uri uri = data.getData();
        io.execute(() -> {
            try (InputStream in = new FileInputStream(apk); OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
                if (out == null) throw new Exception("Save destination unavailable");
                byte[] b = new byte[65536]; int n; while ((n = in.read(b)) != -1) out.write(b, 0, n);
                deckMessage("Verified DeckCraft APK saved. Open it from Files to update. Keep the installed app; uninstalling removes its data.");
            } catch (Exception e) { deckMessage("Could not save update: " + e.getMessage()); }
            finally { apk.delete(); deckUpdateBusy.set(false); }
        });
    }
