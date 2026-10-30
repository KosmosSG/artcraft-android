
    // GRIDCRAFT_ANDROID_ADDONS_V1 -- GridCraft-only SAF font library and read-only update bridge.
    // This fragment is inserted into the generated GridCraftActivity, never other Activities.
    private static final int GC_FONT_REQUEST = 0x7121;
    private static final int GC_FOLDER_REQUEST = 0x7122;
    private static final String GC_SETTINGS = "gridcraft_android_settings";
    private static final String GC_FONT_TREE = "artcraft_shared_font_tree";
    private final java.util.concurrent.ConcurrentLinkedQueue<String> gcEvents =
            new java.util.concurrent.ConcurrentLinkedQueue<>();
    private final java.util.concurrent.ExecutorService gcWorker =
            java.util.concurrent.Executors.newSingleThreadExecutor();
    private final java.util.concurrent.atomic.AtomicBoolean gcChecking =
            new java.util.concurrent.atomic.AtomicBoolean(false);

    public String gcPollResult() { return gcEvents.poll(); }

    private void gcSend(String kind, String status, String message) {
        try {
            org.json.JSONObject event = new org.json.JSONObject();
            event.put("kind", kind);
            event.put("state", status);
            event.put("message", message);
            gcEvents.offer(event.toString());
        } catch (org.json.JSONException error) {
            android.util.Log.w(TAG, "Cannot serialize GridCraft feature event", error);
        }
    }

    public void gcImportFont() {
        runOnUiThread(() -> {
            try {
                android.content.Intent intent = new android.content.Intent(android.content.Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(android.content.Intent.CATEGORY_OPENABLE);
                intent.setType("*/*"); // MIME types vary across Android document providers.
                intent.addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivityForResult(intent, GC_FONT_REQUEST);
            } catch (Exception error) {
                gcSend("font", "error", "Font picker: " + error.getMessage());
            }
        });
    }

    public void gcSelectSharedFolder() {
        runOnUiThread(() -> {
            try {
                android.content.Intent intent = new android.content.Intent(android.content.Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION |
                        android.content.Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION |
                        android.content.Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
                startActivityForResult(intent, GC_FOLDER_REQUEST);
            } catch (Exception error) {
                gcSend("folder", "error", "Folder picker: " + error.getMessage());
            }
        });
    }

    public void gcRefreshSharedFolder() {
        String tree = getSharedPreferences(GC_SETTINGS, MODE_PRIVATE).getString(GC_FONT_TREE, null);
        if (tree == null) {
            gcSend("folder", "error", "Select the shared ArtCraft font folder first");
            return;
        }
        gcWorker.execute(() -> gcScanShared(android.net.Uri.parse(tree)));
    }

    private boolean gcHandleActivityResult(int requestCode, int resultCode, android.content.Intent data) {
        if (requestCode != GC_FONT_REQUEST && requestCode != GC_FOLDER_REQUEST) return false;
        final String kind = requestCode == GC_FONT_REQUEST ? "font" : "folder";
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            gcSend(kind, "cancelled", "Selection cancelled");
            return true;
        }
        android.net.Uri uri = data.getData();
        if (requestCode == GC_FOLDER_REQUEST) {
            try {
                int flags = data.getFlags() & android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION;
                if (flags == 0) throw new SecurityException("Folder read access was not granted");
                getContentResolver().takePersistableUriPermission(uri, flags);
                getSharedPreferences(GC_SETTINGS, MODE_PRIVATE).edit().putString(GC_FONT_TREE, uri.toString()).apply();
                gcWorker.execute(() -> gcScanShared(uri));
            } catch (Exception error) {
                gcSend(kind, "error", "Folder permission: " + error.getMessage());
            }
        } else {
            gcWorker.execute(() -> {
                try {
                    String filename = gcDisplayName(uri);
                    if (!gcHasFontExtension(filename)) throw new java.io.IOException("Select a .ttf or .otf font file");
                    java.io.File destination = new java.io.File(gcFontRoot(), "artcraft-imported");
                    if (!destination.isDirectory() && !destination.mkdirs()) throw new java.io.IOException("Cannot create font folder");
                    gcCopyFont(uri, new java.io.File(destination, gcHash(uri.toString()) + (filename.toLowerCase(java.util.Locale.ROOT).endsWith(".otf") ? ".otf" : ".ttf")));
                    gcSend("font", "ok", "Font file saved. Refreshing GridCraft catalog; check Detected font families for recognition.");
                } catch (Exception error) {
                    gcSend("font", "error", "Import failed: " + error.getMessage());
                }
            });
        }
        return true;
    }

    private java.io.File gcFontRoot() {
        // GridCraft's native font catalog scans $HOME/ArtCraft-Fonts.
        // The Android builder binds $HOME to getFilesDir()/home.
        // Do NOT use .local/share/fonts: that path is an Android SYSTEM font
        // symlink; writes there are not user fonts and may fail silently.
        return new java.io.File(getFilesDir(), "home/ArtCraft-Fonts");
    }

    private static boolean gcHasFontExtension(String name) {
        String lower = name.toLowerCase(java.util.Locale.ROOT);
        return lower.endsWith(".ttf") || lower.endsWith(".otf");
    }

    private String gcDisplayName(android.net.Uri uri) {
        try (android.database.Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
                if (index >= 0) return cursor.getString(index);
            }
        } catch (Exception ignored) { }
        return uri.getLastPathSegment() == null ? "" : uri.getLastPathSegment();
    }

    private static String gcHash(String text) throws Exception {
        byte[] hash = java.security.MessageDigest.getInstance("SHA-256")
                .digest(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        StringBuilder b = new StringBuilder();
        for (byte value : hash) b.append(String.format(java.util.Locale.ROOT, "%02x", value & 0xff));
        return b.toString();
    }

    private void gcCopyFont(android.net.Uri uri, java.io.File destination) throws Exception {
        java.io.File parent = destination.getParentFile();
        if (parent == null || (!parent.isDirectory() && !parent.mkdirs())) throw new java.io.IOException("Font storage unavailable");
        java.io.File temp = new java.io.File(parent, destination.getName() + ".part");
        long size = 0;
        try {
            try (java.io.InputStream in = getContentResolver().openInputStream(uri);
                 java.io.FileOutputStream out = new java.io.FileOutputStream(temp)) {
                if (in == null) throw new java.io.IOException("Font provider returned no data");
                byte[] buffer = new byte[64 * 1024];
                byte[] signature = new byte[4];
                int filled = 0, count;
                while ((count = in.read(buffer)) != -1) {
                    size += count;
                    if (size > 32L * 1024 * 1024) throw new java.io.IOException("Font exceeds 32 MB");
                    for (int i = 0; i < count && filled < 4; i++) signature[filled++] = buffer[i];
                    out.write(buffer, 0, count);
                }
                if (size < 4) throw new java.io.IOException("Font is empty or truncated");
                boolean ttf = signature[0] == 0 && signature[1] == 1 && signature[2] == 0 && signature[3] == 0;
                boolean otf = signature[0] == 'O' && signature[1] == 'T' && signature[2] == 'T' && signature[3] == 'O';
                if (!ttf && !otf) throw new java.io.IOException("File is not a supported TTF/OTF font");
                out.getFD().sync();
            }
            if (destination.exists() && !destination.delete()) throw new java.io.IOException("Cannot replace imported font");
            if (!temp.renameTo(destination)) throw new java.io.IOException("Cannot finalize imported font");
        } finally {
            if (temp.exists() && !temp.delete()) android.util.Log.w(TAG, "Unable to delete temporary font");
        }
    }

    private void gcScanShared(android.net.Uri tree) {
        java.io.File root = gcFontRoot();
        java.io.File active = new java.io.File(root, "artcraft-shared");
        java.io.File staged = new java.io.File(root, "artcraft-shared-staging");
        java.io.File previous = new java.io.File(root, "artcraft-shared-previous");
        try {
            if (!root.isDirectory() && !root.mkdirs()) throw new java.io.IOException("Cannot create font directory");
            gcDeleteTree(staged);
            if (!staged.mkdirs()) throw new java.io.IOException("Cannot prepare font cache");
            java.util.ArrayDeque<String> pending = new java.util.ArrayDeque<>();
            pending.add(android.provider.DocumentsContract.getTreeDocumentId(tree));
            int dirs = 0, imported = 0;
            while (!pending.isEmpty() && dirs++ < 200 && imported < 200) {
                String documentId = pending.removeFirst();
                android.net.Uri children = android.provider.DocumentsContract.buildChildDocumentsUriUsingTree(tree, documentId);
                try (android.database.Cursor cursor = getContentResolver().query(children,
                        new String[] { android.provider.DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                       android.provider.DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                                       android.provider.DocumentsContract.Document.COLUMN_MIME_TYPE },
                        null, null, null)) {
                    if (cursor == null) continue;
                    while (cursor.moveToNext() && imported < 200) {
                        String id = cursor.getString(0), name = cursor.getString(1), mime = cursor.getString(2);
                        if (id == null || name == null) continue;
                        if (android.provider.DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                            if (dirs + pending.size() < 200) pending.add(id);
                        } else if (gcHasFontExtension(name)) {
                            android.net.Uri child = android.provider.DocumentsContract.buildDocumentUriUsingTree(tree, id);
                            try {
                                gcCopyFont(child, new java.io.File(staged, gcHash(id) +
                                      (name.toLowerCase(java.util.Locale.ROOT).endsWith(".otf") ? ".otf" : ".ttf")));
                                imported++;
                            } catch (Exception badFont) {
                                android.util.Log.w(TAG, "Skipping unreadable/unsupported shared font", badFont);
                            }
                        }
                    }
                }
            }
            gcDeleteTree(previous);
            boolean hadActive = active.exists();
            if (hadActive && !active.renameTo(previous)) throw new java.io.IOException("Cannot prepare existing shared font cache");
            if (!staged.renameTo(active)) {
                if (hadActive && !previous.renameTo(active)) android.util.Log.e(TAG, "Cannot restore old shared font cache");
                throw new java.io.IOException("Cannot finish shared font refresh");
            }
            gcDeleteTree(previous);
            gcSend("folder", "ok", imported + " shared font files saved. Refreshing GridCraft catalog; check Detected font families for recognition.");
        } catch (Exception error) {
            gcDeleteTree(staged);
            gcSend("folder", "error", "Shared font folder: " + error.getMessage());
        }
    }

    private static void gcDeleteTree(java.io.File file) {
        if (!file.exists()) return;
        if (file.isDirectory()) {
            java.io.File[] children = file.listFiles();
            if (children != null) for (java.io.File child : children) gcDeleteTree(child);
        }
        if (!file.delete()) android.util.Log.w(TAG, "Cannot delete GridCraft temporary file " + file.getName());
    }

    // Legacy GridCraft-only preference retained for compatibility; no bottom dock is displayed.
    public boolean gcToolsPanelVisible() {
        return getSharedPreferences(GC_SETTINGS, MODE_PRIVATE).getBoolean("bottom_tools_visible", false);
    }

    public void gcSetToolsPanelVisible(boolean visible) {
        getSharedPreferences(GC_SETTINGS, MODE_PRIVATE).edit()
                .putBoolean("bottom_tools_visible", visible).apply();
    }

    public boolean gcStartupChecksEnabled() {
        return getSharedPreferences(GC_SETTINGS, MODE_PRIVATE).getBoolean("startup_update", false);
    }

    public void gcSetStartupChecks(boolean enabled) {
        getSharedPreferences(GC_SETTINGS, MODE_PRIVATE).edit().putBoolean("startup_update", enabled).apply();
    }

    private void gcStartIfEnabled() {
        if (gcStartupChecksEnabled()) gcCheckForUpdates();
    }

    public void gcCheckForUpdates() {
        if (!gcChecking.compareAndSet(false, true)) return;
        gcWorker.execute(() -> {
            java.net.HttpURLConnection connection = null;
            try {
                java.net.URL url = new java.net.URL("https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100");
                connection = (java.net.HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(10000);
                connection.setReadTimeout(12000);
                connection.setRequestProperty("Accept", "application/vnd.github+json");
                connection.setRequestProperty("User-Agent", "GridCraft-Android-UpdateCheck");
                if (connection.getResponseCode() != 200) throw new java.io.IOException("GitHub returned " + connection.getResponseCode());
                java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                try (java.io.InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[8192]; int n;
                    while ((n = input.read(buffer)) != -1) {
                        if (bytes.size() + n > 1024 * 1024) throw new java.io.IOException("Release list exceeds safe size");
                        bytes.write(buffer, 0, n);
                    }
                }
                org.json.JSONArray releases = new org.json.JSONArray(bytes.toString("UTF-8"));
                String bestVersion = null, bestUrl = null;
                for (int i = 0; i < releases.length(); i++) {
                    org.json.JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft") || release.optBoolean("prerelease")) continue;
                    String tag = release.optString("tag_name");
                    if (!tag.matches("gridcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+")) continue;
                    String version = tag.substring("gridcraft-v".length());
                    // Only real, published and downloadable GridCraft APKs are updates.
                    // A draft, a tag-only release, or another app's APK is not.
                    org.json.JSONArray assets = release.optJSONArray("assets");
                    boolean downloadable = false;
                    if (assets != null) for (int ai = 0; ai < assets.length(); ai++) {
                        org.json.JSONObject asset = assets.optJSONObject(ai);
                        if (asset != null &&
                            ("GridCraft-v" + version + "-arm64-v8a.apk").equals(asset.optString("name")) &&
                            "uploaded".equals(asset.optString("state")) &&
                            asset.optLong("size", 0) > 0) {
                            downloadable = true;
                            break;
                        }
                    }
                    if (!downloadable) continue;
                    String page = release.optString("html_url");
                    if (!page.startsWith("https://github.com/KosmosSG/artcraft-android/releases/tag/gridcraft-v")) continue;
                    if (bestVersion == null || gcCompareVersion(version, bestVersion) > 0) {
                        bestVersion = version;
                        bestUrl = page;
                    }
                }
                String installed = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
                if (installed == null) installed = "0.0.0";
                org.json.JSONObject result = new org.json.JSONObject();
                result.put("kind", "update");
                result.put("installed", installed);
                if (bestVersion == null) {
                    result.put("state", "no_release");
                    result.put("message", "No public GridCraft Android release found yet.");
                } else {
                    result.put("latest", bestVersion);
                    result.put("url", bestUrl);
                    boolean newer = gcCompareVersion(bestVersion, installed) > 0;
                    result.put("state", newer ? "update_available" : "up_to_date");
                    result.put("message", newer ? "GridCraft Android " + bestVersion + " is available."
                            : "GridCraft Android is up to date (" + installed + ").");
                }
                gcEvents.offer(result.toString());
            } catch (Exception error) {
                gcSend("update", "error", "Could not check GitHub releases: " + error.getMessage());
            } finally {
                if (connection != null) connection.disconnect();
                gcChecking.set(false);
            }
        });
    }

    private static int gcCompareVersion(String first, String second) {
        // Explicit numeric fields prevent lexicographic 0.10 versus 0.9 mistakes.
        String[] a = first.replace("-android.", ".").split("\\.");
        String[] b = second.replace("-android.", ".").split("\\.");
        for (int i = 0; i < 4; i++) {
            int x = gcVersionPart(a, i), y = gcVersionPart(b, i);
            if (x != y) return Integer.compare(x, y);
        }
        return 0;
    }

    private static int gcVersionPart(String[] parts, int i) {
        try { return i < parts.length ? Integer.parseInt(parts[i]) : 0; }
        catch (NumberFormatException ignored) { return 0; }
    }

    public void gcOpenUpdatePage(String target) {
        if (target == null || !target.matches("https://github\\.com/KosmosSG/artcraft-android/releases/tag/gridcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+")) return;
        runOnUiThread(() -> {
            try { startActivity(new android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(target))); }
            catch (Exception error) { gcSend("update", "error", "Cannot open release page: " + error.getMessage()); }
        });
    }
    private final java.util.concurrent.atomic.AtomicInteger gcDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean gcDialogActive;
    private final java.util.HashSet<Integer> gcDialogKeys = new java.util.HashSet<>();
    public int gcUnsavedDialog(boolean active) {
        gcDialogActive = active;
        int action = gcDialogAction.getAndSet(0);
        return active ? action : 0;
    }
    private final java.util.concurrent.atomic.AtomicBoolean gcEscapePending = new java.util.concurrent.atomic.AtomicBoolean();
    private volatile boolean gcEditorActive;
    public boolean gcEditorEscape(boolean active) {
        gcEditorActive = active;
        boolean pending = gcEscapePending.getAndSet(false);
        return active && pending;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {
            int code = event.getKeyCode();
            if (gcDialogKeys.contains(code)) {
                if (event.getAction() == android.view.KeyEvent.ACTION_UP) gcDialogKeys.remove(code);
                return true;
            }
            if (gcEditorActive && !gcDialogActive && code == android.view.KeyEvent.KEYCODE_ESCAPE
                    && event.hasNoModifiers() && event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                gcDialogKeys.add(code);
                if (event.getRepeatCount() == 0) gcEscapePending.set(true);
                return true;
            }
            int action = code == android.view.KeyEvent.KEYCODE_D ? 1 : code == android.view.KeyEvent.KEYCODE_C ? 2 : code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;
            if (gcDialogActive && action != 0 && event.hasNoModifiers()
                    && event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                gcDialogKeys.add(code);
                if (event.getRepeatCount() == 0) gcDialogAction.compareAndSet(0, action);
                return true;
            }
        }

        return super.dispatchKeyEvent(event);
    }
