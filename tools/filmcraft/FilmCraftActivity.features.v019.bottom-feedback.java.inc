// FilmCraft-only feature bridge. Never share SAF picker result queues with media imports.
    private static final int FC_FONT_PICK = 0x4651;
    private static final int FC_FONT_TREE = 0x4652;
    // Bound scans by files, folders and bytes independently. 4 GiB is not a file-count limit.
    private static final int FC_SCAN_MAX_FONT_FILES = 5000;
    private static final int FC_SCAN_MAX_FOLDERS = 2048;
    private static final String FC_PREFS = "filmcraft_android_features";
    private static final String FC_TREE_PREF = "shared_font_tree_uri";
    private static final String FC_RELEASES_API =
            "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100";
    private final java.util.concurrent.ConcurrentLinkedQueue<String> fcResults =
            new java.util.concurrent.ConcurrentLinkedQueue<>();
    private final java.util.concurrent.ExecutorService fcWorkers =
            java.util.concurrent.Executors.newSingleThreadExecutor();
    private final java.util.concurrent.ExecutorService fcUpdates =
            java.util.concurrent.Executors.newSingleThreadExecutor();

    public String fcFeatureFilesDir() { return appStorageDir().getAbsolutePath(); }
    public String fcFeaturePoll() { return fcResults.poll(); }
    public boolean fcStartupUpdatesEnabled() {
        return getSharedPreferences(FC_PREFS, MODE_PRIVATE).getBoolean("check_updates_startup", !"com.artcraft.filmcraft.test".equals(getPackageName()));
    }
    public void fcSetStartupUpdatesEnabled(boolean enabled) {
        getSharedPreferences(FC_PREFS, MODE_PRIVATE).edit()
                .putBoolean("check_updates_startup", enabled).apply();
    }

    private void fcAnswer(String kind, String state, String detail, org.json.JSONArray paths) {
        try {
            org.json.JSONObject json = new org.json.JSONObject();
            json.put("kind", kind);
            json.put("status", state);
            json.put("message", detail);
            if (paths != null) json.put("paths", paths);
            fcResults.offer(json.toString());
        } catch (Exception error) {
            Log.e(TAG, "FilmCraft feature result failed", error);
        }
    }

    public void fcRequestFontImport() {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivityForResult(intent, FC_FONT_PICK);
            } catch (Exception error) {
                fcAnswer("font_import", "error", error.toString(), null);
            }
        });
    }

    public void fcRequestSharedFontFolder() {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION |
                        Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION |
                        Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
                startActivityForResult(intent, FC_FONT_TREE);
            } catch (Exception error) {
                fcAnswer("font_folder", "error", error.toString(), null);
            }
        });
    }

    public void fcRefreshSharedFonts() {
        String encoded = getSharedPreferences(FC_PREFS, MODE_PRIVATE)
                .getString(FC_TREE_PREF, null);
        if (encoded == null) {
            fcAnswer("font_folder", "error", "Choose a shared font folder first", null);
            return;
        }
        fcScanSharedFonts(android.net.Uri.parse(encoded));
    }

    // Only feature request codes are handled here; the builder's existing SAF media
    // picker, save/export, and content URI staging remain untouched.
    private boolean fcHandleActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != FC_FONT_PICK && requestCode != FC_FONT_TREE) return false;
        final String kind = requestCode == FC_FONT_PICK ? "font_import" : "font_folder";
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            fcAnswer(kind, "cancel", "Cancelled", null);
            return true;
        }
        final android.net.Uri uri = data.getData();
        if (requestCode == FC_FONT_PICK) {
            fcWorkers.execute(() -> {
                try {
                    java.io.File dir = new java.io.File(appStorageDir(), "custom-fonts");
                    if (!dir.isDirectory() && !dir.mkdirs()) {
                        throw new java.io.IOException("Could not create custom-fonts directory");
                    }
                    java.io.File file = fcCopyFont(uri, dir);
                    org.json.JSONArray paths = new org.json.JSONArray();
                    paths.put(file.getAbsolutePath());
                    fcAnswer("font_import", "ok", "Font imported", paths);
                } catch (Exception error) {
                    fcAnswer("font_import", "error", error.toString(), null);
                }
            });
        } else {
            try {
                getContentResolver().takePersistableUriPermission(
                        uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
                getSharedPreferences(FC_PREFS, MODE_PRIVATE).edit()
                        .putString(FC_TREE_PREF, uri.toString()).apply();
                fcScanSharedFonts(uri);
            } catch (Exception error) {
                fcAnswer("font_folder", "error", error.toString(), null);
            }
        }
        return true;
    }

    private java.io.File fcCopyFont(android.net.Uri uri, java.io.File directory)
            throws java.io.IOException {
        return fcCopyFont(uri, directory, new long[]{0});
    }

    private java.io.File fcCopyFont(android.net.Uri uri, java.io.File directory, long[] scanBytes)
            throws java.io.IOException {
        String name = displayName(uri);
        String lower = name == null ? "" : name.toLowerCase(java.util.Locale.ROOT);
        String extension = lower.endsWith(".ttf") ? ".ttf" :
                lower.endsWith(".otf") ? ".otf" : null;
        if (extension == null) throw new java.io.IOException("Only .ttf and .otf files are supported");
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new java.io.IOException("Cannot create font cache");
        }
        // File name derived from the document URI, never from untrusted path segments.
        String key = Integer.toHexString(uri.toString().hashCode());
        java.io.File out = new java.io.File(directory, "font-" + key + extension);
        java.io.File tmp = new java.io.File(directory, "font-" + key + extension + ".partial");
        int total = 0;
        byte[] header = new byte[4];
        try (java.io.InputStream in = getContentResolver().openInputStream(uri);
             java.io.FileOutputStream stream = new java.io.FileOutputStream(tmp)) {
            if (in == null) throw new java.io.IOException("Font provider returned no stream");
            byte[] buf = new byte[64 * 1024];
            int n, inspected = 0;
            while ((n = in.read(buf)) != -1) {
                if (total + n > 32 * 1024 * 1024) {
                    throw new java.io.IOException("Font exceeds 32 MiB");
                }
                for (int j = 0; j < n && inspected < 4; j++) header[inspected++] = buf[j];
                if (scanBytes[0] > 4L * 1024 * 1024 * 1024 - n) {
                    scanBytes[0] = 4L * 1024 * 1024 * 1024;
                    throw new java.io.IOException("Font scan reached the 4 GB limit");
                }
                scanBytes[0] += n;
                stream.write(buf, 0, n);
                total += n;
            }
            stream.flush();
        } catch (Exception error) {
            tmp.delete();
            if (error instanceof java.io.IOException) throw (java.io.IOException) error;
            throw new java.io.IOException(error);
        }
        boolean sfnt = header[0] == 0 && header[1] == 1 && header[2] == 0 && header[3] == 0;
        boolean otto = header[0] == 'O' && header[1] == 'T'
                && header[2] == 'T' && header[3] == 'O';
        boolean collection = header[0] == 't' && header[1] == 't'
                && header[2] == 'c' && header[3] == 'f';
        if (total < 4 || !(sfnt || otto || collection)) {
            tmp.delete();
            throw new java.io.IOException("Selected file is not a supported OpenType/TrueType font");
        }
        if (!tmp.renameTo(out)) {
            // A prior imported font with the same URI may exist; replace only that cache file.
            if (!out.delete() || !tmp.renameTo(out)) {
                tmp.delete();
                throw new java.io.IOException("Could not finish font cache write");
            }
        }
        return out;
    }

    private void fcScanSharedFonts(android.net.Uri tree) {
        fcWorkers.execute(() -> {
            int accepted = 0, skipped = 0;
            org.json.JSONArray paths = new org.json.JSONArray();
            try {
                boolean authorized = false;
                for (android.content.UriPermission permission :
                        getContentResolver().getPersistedUriPermissions()) {
                    if (tree.equals(permission.getUri()) && permission.isReadPermission()) {
                        authorized = true;
                        break;
                    }
                }
                if (!authorized) throw new java.io.IOException(
                        "Shared font folder permission expired; please select it again");
                java.io.File cache = new java.io.File(appStorageDir(), "shared-font-cache");
                if (!cache.isDirectory() && !cache.mkdirs()) {
                    throw new java.io.IOException("Could not create shared-font cache");
                }
                java.util.ArrayDeque<String> queue = new java.util.ArrayDeque<>();
                java.util.HashSet<String> visited = new java.util.HashSet<>();
                queue.add(DocumentsContract.getTreeDocumentId(tree));
                int folders = 0;
                long[] scanBytes = {0};
                while (!queue.isEmpty() && folders < FC_SCAN_MAX_FOLDERS && accepted + skipped < FC_SCAN_MAX_FONT_FILES && scanBytes[0] < 4L * 1024 * 1024 * 1024) {
                    String parent = queue.removeFirst();
                    if (!visited.add(parent)) continue;
                    folders++;
                    android.net.Uri children =
                            DocumentsContract.buildChildDocumentsUriUsingTree(tree, parent);
                    try (Cursor cursor = getContentResolver().query(children,
                            new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                    DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                                    DocumentsContract.Document.COLUMN_MIME_TYPE}, null, null, null)) {
                        if (cursor == null) continue;
                        while (cursor.moveToNext() && accepted + skipped < FC_SCAN_MAX_FONT_FILES && scanBytes[0] < 4L * 1024 * 1024 * 1024) {
                            String child = cursor.getString(0);
                            String name = cursor.getString(1);
                            String mime = cursor.getString(2);
                            if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                                if (queue.size() < FC_SCAN_MAX_FOLDERS) queue.addLast(child);
                                continue;
                            }
                            String lower = name == null ? "" : name.toLowerCase(java.util.Locale.ROOT);
                            if (!lower.endsWith(".ttf") && !lower.endsWith(".otf")) continue;
                            try {
                                android.net.Uri fontUri =
                                        DocumentsContract.buildDocumentUriUsingTree(tree, child);
                                java.io.File saved = fcCopyFont(fontUri, cache, scanBytes);
                                paths.put(saved.getAbsolutePath());
                                accepted++;
                            } catch (Exception error) {
                                skipped++;
                                Log.w(TAG, "Skipping unreadable shared font", error);
                            }
                        }
                    }
                }
                String limit = accepted + skipped >= FC_SCAN_MAX_FONT_FILES
                        ? " (5,000-file limit reached; some fonts remain)"
                        : folders >= FC_SCAN_MAX_FOLDERS && !queue.isEmpty()
                            ? " (2,048-folder limit reached; some folders remain)"
                            : scanBytes[0] >= 4L * 1024 * 1024 * 1024
                                ? " (4 GiB scan budget reached; some fonts remain)" : "";
                fcAnswer("font_folder", "ok",
                        "Font files found: " + accepted + "; skipped: " + skipped
                                + "; folders scanned: " + folders + limit, paths);
            } catch (Exception error) {
                fcAnswer("font_folder", "error", error.toString(), null);
            }
        });
    }


    // Production package stays unchanged. The disposable .test package can
    // verify an official release download, but must NEVER invoke its installer.
    private static final String FC_PUBLIC_PACKAGE = "com.artcraft.filmcraft";
    private static final long FC_MAX_UPDATE_BYTES = 512L * 1024 * 1024;
    private volatile String fcSelectedVersion;
    private volatile String fcSelectedApkName;
    private volatile String fcSelectedApkUrl;
    private volatile String fcSelectedChecksumsUrl;
    private volatile long fcSelectedApkBytes;
    private volatile long fcDownloadId = -1;
    private volatile String fcVerifiedApkSha;
    private final java.util.concurrent.atomic.AtomicBoolean fcDownloading =
            new java.util.concurrent.atomic.AtomicBoolean(false);


    // PhotoCraft-style Android progress UI: only the main thread owns widgets.
    // The existing DownloadManager, SHA-256 and certificate checks remain authoritative.
    private volatile android.app.AlertDialog fcProgressDialog;
    private volatile android.widget.ProgressBar fcProgressBar;
    private volatile android.widget.TextView fcProgressLabel;
    private final java.util.concurrent.atomic.AtomicBoolean fcDownloadCancelled =
            new java.util.concurrent.atomic.AtomicBoolean(false);

    private void fcShowDownloadDialog(String version) {
        runOnUiThread(() -> {
            if (!fcDownloading.get() || fcDownloadCancelled.get() || isFinishing() || isDestroyed())
                return;
            if (fcProgressDialog != null) fcProgressDialog.dismiss();
            android.widget.ProgressBar bar = new android.widget.ProgressBar(
                    this, null, android.R.attr.progressBarStyleHorizontal);
            bar.setMax(1000);
            bar.setProgress(0);
            android.widget.TextView label = new android.widget.TextView(this);
            label.setText("Preparing verified download… 0%");
            label.setTextSize(13.0f);
            label.setGravity(android.view.Gravity.CENTER_HORIZONTAL);
            android.widget.LinearLayout content = new android.widget.LinearLayout(this);
            content.setOrientation(android.widget.LinearLayout.VERTICAL);
            int pad = (int) (20 * getResources().getDisplayMetrics().density + 0.5f);
            content.setPadding(pad, pad, pad, pad);
            content.addView(bar, new android.widget.LinearLayout.LayoutParams(
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                    android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
            content.addView(label, new android.widget.LinearLayout.LayoutParams(
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                    android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
            android.app.AlertDialog dialog = new android.app.AlertDialog.Builder(
                    this, android.app.AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                    .setTitle("Downloading FilmCraft " + version)
                    .setView(content)
                    .setCancelable(false)
                    .setNegativeButton("Cancel", (d, which) -> {
                        // Worker removes this DownloadManager job and any incomplete file.
                        fcDownloadCancelled.set(true);
                    })
                    .create();
            fcProgressDialog = dialog;
            fcProgressBar = bar;
            fcProgressLabel = label;
            dialog.show();
        });
    }

    private void fcUpdateDownloadDialog(int percentage, long received, long total) {
        runOnUiThread(() -> {
            android.widget.ProgressBar bar = fcProgressBar;
            android.widget.TextView label = fcProgressLabel;
            if (bar == null || label == null || fcDownloadCancelled.get()) return;
            int clamped = Math.max(0, Math.min(100, percentage));
            bar.setIndeterminate(false);
            bar.setProgress(clamped * 10);
            label.setText(String.format(java.util.Locale.ROOT,
                    "%d%%  •  %.1f / %.1f MB", clamped,
                    received / 1048576.0, total / 1048576.0));
        });
    }

    private void fcVerifyDownloadDialog() {
        runOnUiThread(() -> {
            if (fcProgressBar != null) fcProgressBar.setIndeterminate(true);
            if (fcProgressLabel != null) fcProgressLabel.setText(
                    "Download complete. Verifying SHA-256 and APK identity…");
        });
    }

    private void fcFinishDownloadDialog(String message, boolean verified) {
        runOnUiThread(() -> {
            android.app.AlertDialog dialog = fcProgressDialog;
            fcProgressDialog = null;
            fcProgressBar = null;
            fcProgressLabel = null;
            if (dialog != null && dialog.isShowing()) dialog.dismiss();
            if (!verified || fcDownloadCancelled.get() || isFinishing() || isDestroyed()) return;
            boolean test = "com.artcraft.filmcraft.test".equals(getPackageName());
            android.app.AlertDialog.Builder next = new android.app.AlertDialog.Builder(
                    this, android.app.AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                    .setTitle("FilmCraft download verified")
                    .setMessage(message);
            if (test) {
                // Result is already routed to the PhotoCraft-style bottom
                // feedback pill. Do not stack a second Android modal.
                return;
            }
            next.setPositiveButton("Install", (d, which) -> fcInstallVerifiedDownload())
                .setNegativeButton("Later", null);
            next.show();
        });
    }

    private void fcRejectCancelledDownload() throws java.io.IOException {
        if (fcDownloadCancelled.get()) throw new java.io.IOException("cancelled");
    }

    private static int fcCompareVersions(String one, String two) {
        java.util.regex.Pattern p = java.util.regex.Pattern.compile(
                "([0-9]+)\\.([0-9]+)\\.([0-9]+)-android\\.([0-9]+)");
        java.util.regex.Matcher a = p.matcher(one), b = p.matcher(two);
        if (!a.matches() || !b.matches()) throw new IllegalArgumentException(
                "Update comparison requires an official Android versionName");
        for (int i = 1; i <= 4; i++) {
            int comparison = new java.math.BigInteger(a.group(i)).compareTo(
                    new java.math.BigInteger(b.group(i)));
            if (comparison != 0) return Integer.signum(comparison);
        }
        return 0;
    }

    private static boolean fcIsOfficialVersion(String version) {
        return version != null && version.matches(
                "[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+");
    }

    // Follow only canonical GitHub Release download URLs in this repository.
    // The remote release JSON is not trusted to supply arbitrary download hosts.
    private static String fcOfficialAssetUrl(String tag, String asset) {
        return "https://github.com/KosmosSG/artcraft-android/releases/download/"
                + tag + "/" + asset;
    }

    private static String fcReadBoundedHttps(String source, int maxBytes)
            throws java.io.IOException {
        if (!source.startsWith("https://github.com/KosmosSG/artcraft-android/releases/download/")
                && !FC_RELEASES_API.equals(source))
            throw new java.io.IOException("Untrusted update source");
        java.net.HttpURLConnection connection = null;
        try {
            connection = (java.net.HttpURLConnection) new java.net.URL(source).openConnection();
            connection.setConnectTimeout(12000);
            connection.setReadTimeout(20000);
            connection.setRequestProperty("User-Agent", "FilmCraft-Android-Updater");
            connection.setRequestProperty("Accept", "application/vnd.github+json");
            if (connection.getResponseCode() != 200) throw new java.io.IOException(
                    "Update server returned HTTP " + connection.getResponseCode());
            java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
            try (java.io.InputStream in = connection.getInputStream()) {
                byte[] chunk = new byte[8192];
                int n;
                while ((n = in.read(chunk)) != -1) {
                    if (buffer.size() + n > maxBytes) throw new java.io.IOException(
                            "Update metadata exceeds size limit");
                    buffer.write(chunk, 0, n);
                }
            }
            return new String(buffer.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    public void fcCheckForUpdates() {
        fcUpdates.execute(() -> {
            try {
                fcSelectedVersion = null;
                fcSelectedApkName = null;
                fcSelectedApkUrl = null;
                fcSelectedChecksumsUrl = null;
                fcSelectedApkBytes = 0;
                org.json.JSONArray releases = new org.json.JSONArray(
                        fcReadBoundedHttps(FC_RELEASES_API, 2 * 1024 * 1024));
                String installed = getPackageManager().getPackageInfo(
                        getPackageName(), 0).versionName;
                if (installed == null) throw new java.io.IOException("Installed version missing");
                boolean testPackage = "com.artcraft.filmcraft.test".equals(getPackageName());
                if (!testPackage && !FC_PUBLIC_PACKAGE.equals(getPackageName()))
                    throw new java.io.IOException("Unknown package identity: refusing updater");
                if (!testPackage && !fcIsOfficialVersion(installed))
                    throw new java.io.IOException("Installed production version is not official");
                String latest = null, page = null, filename = null, apkUrl = null, checksumsUrl = null;
                long bytes = 0;
                for (int i = 0; i < releases.length(); i++) {
                    org.json.JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft") ||
                            release.optBoolean("prerelease")) continue;
                    String tag = release.optString("tag_name", "");
                    if (!tag.matches("filmcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+"))
                        continue;
                    String version = tag.substring("filmcraft-v".length());
                    org.json.JSONArray assets = release.optJSONArray("assets");
                    if (assets == null) continue;
                    String foundApk = null, foundUrl = null, foundChecksums = null;
                    long foundSize = 0;
                    for (int j = 0; j < assets.length(); j++) {
                        org.json.JSONObject asset = assets.optJSONObject(j);
                        if (asset == null) continue;
                        String name = asset.optString("name", "");
                        String url = asset.optString("browser_download_url", "");
                        if (!url.equals(fcOfficialAssetUrl(tag, name))) continue;
                        if (name.equals("SHA256SUMS.txt") && asset.optLong("size") > 0)
                            foundChecksums = url;
                        boolean validName = name.equals("FilmCraft-v" + version + "-arm64-v8a.apk")
                                || name.equals("filmcraft-" + version + ".apk");
                        long size = asset.optLong("size");
                        if (validName && size > 1024 && size <= FC_MAX_UPDATE_BYTES) {
                            foundApk = name;
                            foundUrl = url;
                            foundSize = size;
                        }
                    }
                    if (foundApk == null || foundChecksums == null) continue;
                    if (latest == null || fcCompareVersions(version, latest) > 0) {
                        latest = version;
                        page = "https://github.com/KosmosSG/artcraft-android/releases/tag/" + tag;
                        filename = foundApk;
                        apkUrl = foundUrl;
                        checksumsUrl = foundChecksums;
                        bytes = foundSize;
                    }
                }
                org.json.JSONObject result = new org.json.JSONObject();
                result.put("kind", "updates");
                result.put("installed", installed);
                if (latest == null) {
                    result.put("status", "none");
                    result.put("message", "No public FilmCraft Android release with APK + SHA256SUMS");
                } else {
                    fcSelectedVersion = latest;
                    fcSelectedApkName = filename;
                    fcSelectedApkUrl = apkUrl;
                    fcSelectedChecksumsUrl = checksumsUrl;
                    fcSelectedApkBytes = bytes;
                    result.put("latest", latest);
                    result.put("url", page);
                    if (testPackage) {
                        result.put("status", "test");
                        result.put("message", "Test build: official APK can be downloaded and verified, but cannot be installed from this test app");
                    } else {
                        result.put("status", fcCompareVersions(latest, installed) > 0
                                ? "available" : "current");
                    }
                }
                fcResults.offer(result.toString());
            } catch (Exception error) {
                fcAnswer("updates", "error",
                        "Could not check FilmCraft releases: " + error.getMessage(), null);
            }
        });
    }

    private static String fcExpectedShaFromChecksums(String checksums, String file)
            throws java.io.IOException {
        String expected = null;
        for (String line : checksums.split("\\r?\\n")) {
            java.util.regex.Matcher match = java.util.regex.Pattern.compile(
                    "^([0-9a-fA-F]{64})\\s+\\*?(.+?)\\s*$").matcher(line);
            if (!match.matches() || !file.equals(match.group(2))) continue;
            if (expected != null) throw new java.io.IOException("Duplicate checksum entry");
            expected = match.group(1).toLowerCase(java.util.Locale.ROOT);
        }
        if (expected == null) throw new java.io.IOException(
                "Official SHA256SUMS does not identify the APK");
        return expected;
    }

    private static String fcFileSha256(java.io.File path) throws Exception {
        java.security.MessageDigest sha = java.security.MessageDigest.getInstance("SHA-256");
        try (java.io.FileInputStream in = new java.io.FileInputStream(path)) {
            byte[] buf = new byte[64 * 1024];
            int n;
            while ((n = in.read(buf)) != -1) sha.update(buf, 0, n);
        }
        StringBuilder output = new StringBuilder();
        for (byte b : sha.digest())
            output.append(String.format(java.util.Locale.ROOT, "%02x", b & 0xff));
        return output.toString();
    }

    private void fcVerifyArchive(java.io.File apk) throws Exception {
        final int flags = android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES;
        android.content.pm.PackageInfo candidate =
                getPackageManager().getPackageArchiveInfo(apk.getAbsolutePath(), flags);
        if (candidate == null || !FC_PUBLIC_PACKAGE.equals(candidate.packageName))
            throw new java.io.IOException("Downloaded APK is not the official FilmCraft application");
        if ("com.artcraft.filmcraft.test".equals(getPackageName())) return;
        android.content.pm.PackageInfo installed =
                getPackageManager().getPackageInfo(getPackageName(), flags);
        if (candidate.getLongVersionCode() <= installed.getLongVersionCode())
            throw new java.io.IOException("Downloaded APK is not newer than the installed release");
        if (installed.signingInfo == null || candidate.signingInfo == null)
            throw new java.io.IOException("Signing certificates could not be verified");
        android.content.pm.Signature[] current =
                installed.signingInfo.getApkContentsSigners();
        android.content.pm.Signature[] replacement =
                candidate.signingInfo.getApkContentsSigners();
        boolean matching = false;
        for (android.content.pm.Signature one : current)
            for (android.content.pm.Signature two : replacement)
                if (java.util.Arrays.equals(one.toByteArray(), two.toByteArray()))
                    matching = true;
        if (!matching) throw new java.io.IOException(
                "APK signing certificate differs from installed FilmCraft; refusing install");
    }

    public void fcDownloadVerifiedUpdate() {
        if (!fcDownloading.compareAndSet(false, true)) {
            fcAnswer("download", "progress", "APK download already running", null);
            return;
        }
        fcDownloadCancelled.set(false);
        fcVerifiedApkSha = null;
        fcDownloadId = -1;
        String selectedVersion = fcSelectedVersion;
        fcShowDownloadDialog(selectedVersion == null ? "" : selectedVersion);
        fcUpdates.execute(() -> {
            android.app.DownloadManager manager = null;
            java.io.File downloaded = null;
            String completedMessage = null;
            boolean verified = false;
            long activeId = -1;
            try {
                String name = fcSelectedApkName;
                String url = fcSelectedApkUrl;
                String checksumsUrl = fcSelectedChecksumsUrl;
                long expectedSize = fcSelectedApkBytes;
                if (name == null || url == null || checksumsUrl == null ||
                        expectedSize <= 0 || expectedSize > FC_MAX_UPDATE_BYTES)
                    throw new java.io.IOException("Check for Updates before downloading");
                String version = fcSelectedVersion;
                String tag = "filmcraft-v" + version;
                if (!name.equals("FilmCraft-v" + version + "-arm64-v8a.apk")
                        && !name.equals("filmcraft-" + version + ".apk"))
                    throw new java.io.IOException("Unexpected APK name");
                if (!url.equals(fcOfficialAssetUrl(tag, name)) ||
                        !checksumsUrl.equals(fcOfficialAssetUrl(tag, "SHA256SUMS.txt")))
                    throw new java.io.IOException("Untrusted APK or checksum URL");
                fcRejectCancelledDownload();
                String expectedSha = fcExpectedShaFromChecksums(
                        fcReadBoundedHttps(checksumsUrl, 128 * 1024), name);
                fcRejectCancelledDownload();
                java.io.File folder = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS);
                if (folder == null) throw new java.io.IOException("App download directory unavailable");
                java.io.File updates = new java.io.File(folder, "filmcraft-updates");
                if (!updates.isDirectory() && !updates.mkdirs())
                    throw new java.io.IOException("Could not create update directory");
                downloaded = new java.io.File(updates, name);
                if (downloaded.exists() && !downloaded.delete())
                    throw new java.io.IOException("Could not remove a previous APK download");
                android.app.DownloadManager.Request request =
                        new android.app.DownloadManager.Request(android.net.Uri.parse(url));
                request.setTitle("FilmCraft " + version);
                request.setDescription("Verified official ArtCraft Android APK");
                request.setMimeType("application/vnd.android.package-archive");
                request.setNotificationVisibility(
                        android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalFilesDir(this,
                        android.os.Environment.DIRECTORY_DOWNLOADS,
                        "filmcraft-updates/" + name);
                manager = (android.app.DownloadManager)
                        getSystemService(android.content.Context.DOWNLOAD_SERVICE);
                if (manager == null) throw new java.io.IOException("Android DownloadManager unavailable");
                fcRejectCancelledDownload();
                activeId = manager.enqueue(request);
                fcDownloadId = activeId;
                fcAnswer("download", "progress", "Downloading FilmCraft " + version + "…", null);
                long deadline = android.os.SystemClock.elapsedRealtime() + 20 * 60 * 1000L;
                boolean complete = false;
                int lastReportedDecile = -1;
                while (android.os.SystemClock.elapsedRealtime() < deadline) {
                    fcRejectCancelledDownload();
                    android.app.DownloadManager.Query query =
                            new android.app.DownloadManager.Query().setFilterById(activeId);
                    try (Cursor cursor = manager.query(query)) {
                        if (cursor == null || !cursor.moveToFirst())
                            throw new java.io.IOException("Update download no longer exists");
                        int status = cursor.getInt(
                                cursor.getColumnIndexOrThrow(android.app.DownloadManager.COLUMN_STATUS));
                        if (status == android.app.DownloadManager.STATUS_FAILED)
                            throw new java.io.IOException("Android DownloadManager reported failure");
                        long received = cursor.getLong(cursor.getColumnIndexOrThrow(
                                android.app.DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                        int percent = (int) Math.max(0,
                                Math.min(100, received * 100 / expectedSize));
                        fcUpdateDownloadDialog(percent, received, expectedSize);
                        if (percent / 10 != lastReportedDecile) {
                            lastReportedDecile = percent / 10;
                            fcAnswer("download", "progress",
                                    "Downloading FilmCraft: " + percent + "%", null);
                        }
                        if (status == android.app.DownloadManager.STATUS_SUCCESSFUL) {
                            complete = true;
                            break;
                        }
                    }
                    Thread.sleep(1200);
                }
                if (!complete) throw new java.io.IOException("Update download timed out");
                fcRejectCancelledDownload();
                if (!downloaded.isFile() || downloaded.length() != expectedSize)
                    throw new java.io.IOException("Downloaded APK size does not match GitHub release");
                fcVerifyDownloadDialog();
                String actual = fcFileSha256(downloaded);
                fcRejectCancelledDownload();
                if (!actual.equals(expectedSha))
                    throw new java.io.IOException("Downloaded APK SHA-256 mismatch");
                fcVerifyArchive(downloaded);
                fcRejectCancelledDownload();
                fcVerifiedApkSha = expectedSha;
                verified = true;
                if ("com.artcraft.filmcraft.test".equals(getPackageName())) {
                    completedMessage = "APK downloaded and verified. This is a separate test app, so installing over published FilmCraft is disabled.";
                    fcAnswer("download", "test_ready", completedMessage, null);
                } else {
                    completedMessage = "APK downloaded and verified (SHA-256, identity and signing certificate). Save your project before installing.";
                    fcAnswer("download", "ready", completedMessage, null);
                }
            } catch (Exception error) {
                fcVerifiedApkSha = null;
                if (fcDownloadCancelled.get()) {
                    fcAnswer("download", "cancelled", "Download cancelled", null);
                } else {
                    fcAnswer("download", "error",
                            "APK download blocked: " + error.getMessage(), null);
                }
            } finally {
                if (fcDownloadCancelled.get()) {
                    if (manager != null && activeId > 0) manager.remove(activeId);
                    if (downloaded != null && downloaded.exists()) downloaded.delete();
                    fcDownloadId = -1;
                    fcVerifiedApkSha = null;
                    verified = false;
                }
                fcDownloading.set(false);
                fcFinishDownloadDialog(completedMessage, verified);
            }
        });
    }

    public void fcInstallVerifiedDownload() {
        if ("com.artcraft.filmcraft.test".equals(getPackageName())) {
            fcAnswer("download", "test_ready",
                    "Test APK cannot install an update to the published FilmCraft package", null);
            return;
        }
        if (!FC_PUBLIC_PACKAGE.equals(getPackageName())) {
            fcAnswer("download", "error", "Unknown FilmCraft package; installer blocked", null);
            return;
        }
        fcUpdates.execute(() -> {
            try {
                if (fcDownloading.get() || fcVerifiedApkSha == null ||
                        fcSelectedApkName == null || fcDownloadId == -1)
                    throw new java.io.IOException("Download and verify the latest APK first");
                java.io.File folder = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS);
                if (folder == null) throw new java.io.IOException("Download folder unavailable");
                java.io.File apk = new java.io.File(
                        new java.io.File(folder, "filmcraft-updates"), fcSelectedApkName);
                if (!apk.isFile() || !fcFileSha256(apk).equals(fcVerifiedApkSha))
                    throw new java.io.IOException("APK checksum changed; download again");
                fcVerifyArchive(apk);
                android.app.DownloadManager manager = (android.app.DownloadManager)
                        getSystemService(android.content.Context.DOWNLOAD_SERVICE);
                android.net.Uri contentUri = manager == null ? null :
                        manager.getUriForDownloadedFile(fcDownloadId);
                if (contentUri == null || !"content".equals(contentUri.getScheme()))
                    throw new java.io.IOException("Android download content URI unavailable");
                runOnUiThread(() -> {
                    try {
                        if (android.os.Build.VERSION.SDK_INT >= 26 &&
                                !getPackageManager().canRequestPackageInstalls()) {
                            Intent settings = new Intent(
                                    android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                    android.net.Uri.parse("package:" + getPackageName()));
                            startActivity(settings);
                            fcAnswer("download", "ready",
                                    "Allow installs from FilmCraft, then select Install Verified Download again", null);
                            return;
                        }
                        Intent installer = new Intent(Intent.ACTION_VIEW);
                        installer.setDataAndType(contentUri,
                                "application/vnd.android.package-archive");
                        installer.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        startActivity(installer);
                        fcAnswer("download", "ready",
                                "Android installer opened; confirm installation if you approve", null);
                    } catch (Exception error) {
                        fcAnswer("download", "error",
                                "Could not open Android installer: " + error.getMessage(), null);
                    }
                });
            } catch (Exception error) {
                fcAnswer("download", "error", "Install blocked: " + error.getMessage(), null);
            }
        });
    }

    public void fcOpenUpdatePage(String url) {
        if (url == null || !url.matches(
                "https://github\\.com/KosmosSG/artcraft-android/releases/tag/filmcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+"))
            return;
        runOnUiThread(() -> {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url)));
            } catch (Exception error) {
                fcAnswer("updates", "error", "Could not open GitHub release page", null);
            }
        });
    }
