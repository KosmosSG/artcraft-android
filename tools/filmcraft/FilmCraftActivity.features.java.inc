// FilmCraft-only feature bridge. Never share SAF picker result queues with media imports.
    private static final int FC_FONT_PICK = 0x4651;
    private static final int FC_FONT_TREE = 0x4652;
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
        return getSharedPreferences(FC_PREFS, MODE_PRIVATE).getBoolean("check_updates_startup", false);
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
                long totalBytes = 0;
                while (!queue.isEmpty() && folders < 128 && accepted + skipped < 256) {
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
                        while (cursor.moveToNext() && accepted + skipped < 256) {
                            String child = cursor.getString(0);
                            String name = cursor.getString(1);
                            String mime = cursor.getString(2);
                            if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                                if (queue.size() < 128) queue.addLast(child);
                                continue;
                            }
                            String lower = name == null ? "" : name.toLowerCase(java.util.Locale.ROOT);
                            if (!lower.endsWith(".ttf") && !lower.endsWith(".otf")) continue;
                            try {
                                android.net.Uri fontUri =
                                        DocumentsContract.buildDocumentUriUsingTree(tree, child);
                                java.io.File saved = fcCopyFont(fontUri, cache);
                                totalBytes += saved.length();
                                if (totalBytes > 128L * 1024 * 1024) {
                                    saved.delete();
                                    throw new java.io.IOException("Shared font cache limit reached");
                                }
                                paths.put(saved.getAbsolutePath());
                                accepted++;
                            } catch (Exception error) {
                                skipped++;
                                Log.w(TAG, "Skipping unreadable shared font", error);
                            }
                        }
                    }
                }
                fcAnswer("font_folder", "ok",
                        "Shared fonts loaded: " + accepted + "; skipped: " + skipped, paths);
            } catch (Exception error) {
                fcAnswer("font_folder", "error", error.toString(), null);
            }
        });
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

    public void fcCheckForUpdates() {
        fcUpdates.execute(() -> {
            java.net.HttpURLConnection connection = null;
            try {
                connection = (java.net.HttpURLConnection) new java.net.URL(
                        FC_RELEASES_API).openConnection();
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(8000);
                connection.setRequestProperty("Accept", "application/vnd.github+json");
                connection.setRequestProperty("User-Agent", "FilmCraft-Android-Updater");
                if (connection.getResponseCode() != 200) throw new java.io.IOException(
                        "GitHub API returned HTTP " + connection.getResponseCode());
                java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
                try (java.io.InputStream in = connection.getInputStream()) {
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = in.read(buf)) != -1) {
                        if (buffer.size() + n > 1024 * 1024)
                            throw new java.io.IOException("Release response too large");
                        buffer.write(buf, 0, n);
                    }
                }
                org.json.JSONArray releases = new org.json.JSONArray(
                        new String(buffer.toByteArray(), java.nio.charset.StandardCharsets.UTF_8));
                String installed = getPackageManager().getPackageInfo(
                        getPackageName(), 0).versionName;
                if (installed == null) throw new java.io.IOException("Installed version is unknown");
                String latest = null, page = null;
                for (int i = 0; i < releases.length(); i++) {
                    org.json.JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft") ||
                            release.optBoolean("prerelease")) continue;
                    String tag = release.optString("tag_name", "");
                    if (!tag.matches("filmcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+"))
                        continue;
                    String v = tag.substring("filmcraft-v".length());
                    org.json.JSONArray assets = release.optJSONArray("assets");
                    boolean validApk = false, checksums = false;
                    if (assets == null) continue;
                    for (int j = 0; j < assets.length(); j++) {
                        org.json.JSONObject asset = assets.optJSONObject(j);
                        if (asset == null) continue;
                        String name = asset.optString("name", "");
                        if (name.equals("filmcraft-" + v + ".apk") && asset.optLong("size") > 0)
                            validApk = true;
                        if (name.equals("SHA256SUMS.txt") && asset.optLong("size") > 0)
                            checksums = true;
                    }
                    if (!(validApk && checksums)) continue;
                    if (latest == null || fcCompareVersions(v, latest) > 0) {
                        latest = v;
                        page = release.optString("html_url", "");
                    }
                }
                org.json.JSONObject result = new org.json.JSONObject();
                result.put("kind", "updates");
                result.put("installed", installed);
                if (latest == null) {
                    result.put("status", "none");
                    result.put("message", "No verified public FilmCraft Android release yet");
                } else {
                    result.put("latest", latest);
                    result.put("url", page);
                    result.put("status", fcCompareVersions(latest, installed) > 0
                            ? "available" : "current");
                }
                fcResults.offer(result.toString());
            } catch (Exception error) {
                fcAnswer("updates", "error",
                        "Could not check FilmCraft releases: " + error.getMessage(), null);
            } finally {
                if (connection != null) connection.disconnect();
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
