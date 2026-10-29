
    // WordCraft-only Android enhancements. These are injected only into the isolated
    // WordCraft candidate's generated Activity; other ArtCraft apps are unchanged.
    private static final int WC_FONT_FOLDER_REQUEST = 0x5751;
    private static final String WC_FONT_TREE_KEY = "wordcraft_shared_font_tree";
    private final ConcurrentLinkedQueue<String> wcFontEvents = new ConcurrentLinkedQueue<>();
    private final ConcurrentLinkedQueue<String> wcUpdateEvents = new ConcurrentLinkedQueue<>();
    private final ExecutorService wcUpdateIo = Executors.newSingleThreadExecutor();

    public void wcRequestFontFolder() {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                startActivityForResult(intent, WC_FONT_FOLDER_REQUEST);
            } catch (Exception error) {
                wcFontError("Could not open font folder picker: " + error);
            }
        });
    }

    private void wcFontError(String message) {
        try {
            JSONObject result = new JSONObject();
            result.put("state", "error");
            result.put("message", message);
            wcFontEvents.offer(result.toString());
        } catch (Exception error) {
            Log.e(TAG, "Could not encode WordCraft font error", error);
        }
    }

    private void wcHandleFontFolderResult(int resultCode, Intent data) {
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            try {
                wcFontEvents.offer(new JSONObject().put("state", "cancelled").toString());
            } catch (Exception ignored) { }
            return;
        }
        try {
            Uri tree = data.getData();
            int read = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
            if (read == 0) throw new SecurityException("Folder read permission was not granted");
            getContentResolver().takePersistableUriPermission(tree, read);
            getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                    .putString(WC_FONT_TREE_KEY, tree.toString()).apply();
            wcRefreshFontFolder();
        } catch (Exception error) {
            wcFontError("Could not retain font folder access: " + error);
        }
    }

    public boolean wcHasFontFolder() {
        return getSharedPreferences(PREFS, MODE_PRIVATE)
                .contains(WC_FONT_TREE_KEY);
    }

    public void wcRefreshFontFolder() {
        String saved = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(WC_FONT_TREE_KEY, null);
        if (saved == null || saved.isEmpty()) {
            wcFontError("Choose a shared font folder first");
            return;
        }
        io.execute(() -> wcScanFontTree(Uri.parse(saved)));
    }

    // Read-only SAF tree scan: supports nested folders and non-primary volumes.
    // Limits both count and bytes, stages files privately, and never asks for
    // MANAGE_EXTERNAL_STORAGE. The native WordCraft font engine validates bytes.
    private void wcScanFontTree(Uri tree) {
        try {
            boolean allowed = false;
            for (android.content.UriPermission permission :
                    getContentResolver().getPersistedUriPermissions()) {
                if (tree.equals(permission.getUri()) && permission.isReadPermission()) {
                    allowed = true;
                    break;
                }
            }
            if (!allowed) throw new SecurityException("Shared font folder permission expired; select it again");

            File cache = new File(appStorageDir(), "wordcraft-shared-font-cache");
            if (!cache.isDirectory() && !cache.mkdirs())
                throw new java.io.IOException("Cannot create private font cache");

            JSONArray paths = new JSONArray();
            java.util.ArrayDeque<String> pending = new java.util.ArrayDeque<>();
            java.util.HashSet<String> seen = new java.util.HashSet<>();
            pending.add(DocumentsContract.getTreeDocumentId(tree));
            int scannedFolders = 0;
            int copied = 0;
            long copiedBytes = 0;
            int skipped = 0;
            while (!pending.isEmpty() && scannedFolders < 300 && copied < 150
                    && copiedBytes < 200L * 1024 * 1024) {
                String parentId = pending.removeFirst();
                if (!seen.add(parentId)) continue;
                scannedFolders++;
                Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId);
                try (Cursor cursor = getContentResolver().query(children,
                        new String[] { DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                                DocumentsContract.Document.COLUMN_MIME_TYPE,
                                DocumentsContract.Document.COLUMN_SIZE },
                        null, null, null)) {
                    if (cursor == null) { skipped++; continue; }
                    while (cursor.moveToNext() && copied < 150
                            && copiedBytes < 200L * 1024 * 1024) {
                        String id = cursor.getString(0);
                        String name = cursor.getString(1);
                        String mime = cursor.getString(2);
                        if (id == null || name == null) continue;
                        if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                            if (pending.size() + seen.size() < 300) pending.addLast(id);
                            continue;
                        }
                        String lower = name.toLowerCase(java.util.Locale.ROOT);
                        if (!lower.endsWith(".ttf") && !lower.endsWith(".otf")
                                && !lower.endsWith(".ttc") && !lower.endsWith(".otc")) continue;
                        long size = cursor.isNull(3) ? -1 : cursor.getLong(3);
                        if (size == 0 || size > 20L * 1024 * 1024) { skipped++; continue; }
                        String suffix = lower.substring(lower.lastIndexOf('.'));
                        String hash = java.util.UUID.nameUUIDFromBytes(
                                id.getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
                        File target = new File(cache, "font-" + hash + suffix);
                        File temp = new File(cache, "font-" + hash + suffix + ".part");
                        Uri document = DocumentsContract.buildDocumentUriUsingTree(tree, id);
                        long total = 0;
                        try (InputStream input = getContentResolver().openInputStream(document);
                             OutputStream output = new FileOutputStream(temp)) {
                            if (input == null) throw new java.io.IOException("Unreadable font");
                            byte[] buffer = new byte[65536];
                            int n;
                            while ((n = input.read(buffer)) != -1) {
                                total += n;
                                if (total > 20L * 1024 * 1024
                                        || copiedBytes + total > 200L * 1024 * 1024)
                                    throw new java.io.IOException("Font storage limit exceeded");
                                output.write(buffer, 0, n);
                            }
                            if (total == 0) throw new java.io.IOException("Empty font");
                        } catch (Exception error) {
                            temp.delete();
                            skipped++;
                            Log.w(TAG, "Skipping unreadable shared font " + name, error);
                            continue;
                        }
                        if (target.exists() && !target.delete()) {
                            temp.delete(); skipped++; continue;
                        }
                        if (!temp.renameTo(target)) {
                            temp.delete(); skipped++; continue;
                        }
                        paths.put(target.getAbsolutePath());
                        copiedBytes += total;
                        copied++;
                    }
                } catch (SecurityException error) {
                    throw error;
                } catch (Exception error) {
                    skipped++;
                    Log.w(TAG, "Skipping unreadable shared font subfolder", error);
                }
            }
            JSONObject result = new JSONObject();
            result.put("state", "ok");
            result.put("paths", paths);
            result.put("count", copied);
            result.put("skipped", skipped);
            result.put("limited", !pending.isEmpty());
            wcFontEvents.offer(result.toString());
        } catch (Exception error) {
            wcFontError("Could not read shared font folder: " + error);
        }
    }

    public String wcPollFontResult() { return wcFontEvents.poll(); }

    public boolean wcStartupUpdates() {
        return getSharedPreferences(PREFS, MODE_PRIVATE)
                .getBoolean("wordcraft_check_updates_startup", false);
    }

    public void wcSetStartupUpdates(boolean enabled) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putBoolean("wordcraft_check_updates_startup", enabled).apply();
    }

    public String wcGetShortcutPad() {
        return getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString("wordcraft_shortcut_pad", "");
    }

    public void wcSetShortcutPad(String value) {
        if (value == null || value.length() > 200 || !value.matches("[a-zA-Z0-9.,-]*")) return;
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("wordcraft_shortcut_pad", value).apply();
    }

    private static int wcCompareVersion(String left, String right) {
        String[] a = left.replace("-android.", ".").split("\\.");
        String[] b = right.replace("-android.", ".").split("\\.");
        if (a.length != 4 || b.length != 4) return 0;
        for (int i = 0; i < 4; i++) {
            int av = Integer.parseInt(a[i]);
            int bv = Integer.parseInt(b[i]);
            if (av != bv) return Integer.compare(av, bv);
        }
        return 0;
    }

    // Read-only, manual by default; startup checks require explicit opt-in.
    // Only consider published WordCraft Android releases with matching APK assets.
    // Never install, sideload, replace a certificate or fetch a draft APK.
    public void wcCheckForUpdates() {
        wcUpdateIo.execute(() -> {
            try {
                java.net.HttpURLConnection connection = (java.net.HttpURLConnection)
                        new java.net.URL("https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100")
                                .openConnection();
                try {
                    connection.setConnectTimeout(8000);
                    connection.setReadTimeout(8000);
                    connection.setRequestProperty("Accept", "application/vnd.github+json");
                    connection.setRequestProperty("User-Agent", "WordCraft-Android-Update-Check");
                    if (connection.getResponseCode() != 200)
                        throw new java.io.IOException("GitHub HTTP " + connection.getResponseCode());
                    java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
                    try (InputStream input = connection.getInputStream()) {
                        byte[] chunk = new byte[8192];
                        int n;
                        while ((n = input.read(chunk)) != -1) {
                            if (buffer.size() + n > 1024 * 1024)
                                throw new java.io.IOException("GitHub response too large");
                            buffer.write(chunk, 0, n);
                        }
                    }
                    JSONArray releases = new JSONArray(
                            new String(buffer.toByteArray(), java.nio.charset.StandardCharsets.UTF_8));
                    String installed = getPackageManager()
                            .getPackageInfo(getPackageName(), 0).versionName;
                    if (installed == null) installed = "0.0.0-android.0";
                    String latest = null;
                    String url = null;
                    for (int i = 0; i < releases.length(); i++) {
                        JSONObject release = releases.optJSONObject(i);
                        if (release == null || release.optBoolean("draft")
                                || release.optBoolean("prerelease")) continue;
                        String tag = release.optString("tag_name", "");
                        if (!tag.matches("wordcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+")) continue;
                        String version = tag.substring("wordcraft-v".length());
                        // Match the suite's production ARM64 filename, with exact
                        // legacy naming only for backwards-compatible releases.
                        String expectedApk = "WordCraft-v" + version + "-arm64-v8a.apk";
                        String legacyApk = "wordcraft-" + version + ".apk";
                        boolean hasApk = false;
                        JSONArray assets = release.optJSONArray("assets");
                        if (assets != null) {
                            for (int j = 0; j < assets.length(); j++) {
                                JSONObject asset = assets.optJSONObject(j);
                                if (asset != null && (expectedApk.equals(asset.optString("name", ""))
                                        || legacyApk.equals(asset.optString("name", "")))
                                        && asset.optLong("size", 0) > 0) {
                                    hasApk = true;
                                    break;
                                }
                            }
                        }
                        if (!hasApk) continue;
                        if (latest == null || wcCompareVersion(version, latest) > 0) {
                            latest = version;
                            url = "https://github.com/KosmosSG/artcraft-android/releases/tag/" + tag;
                        }
                    }
                    JSONObject result = new JSONObject();
                    result.put("installed", installed);
                    if (latest == null) {
                        result.put("state", "no_release");
                        result.put("message", "No published WordCraft Android APK release yet");
                    } else {
                        result.put("latest", latest);
                        result.put("url", url);
                        result.put("state", wcCompareVersion(latest, installed) > 0
                                ? "update_available" : "up_to_date");
                    }
                    wcUpdateEvents.offer(result.toString());
                } finally {
                    connection.disconnect();
                }
            } catch (Exception error) {
                Log.w(TAG, "WordCraft update check failed", error);
                try {
                    wcUpdateEvents.offer(new JSONObject().put("state", "error")
                            .put("message", error.toString()).toString());
                } catch (Exception ignored) { }
            }
        });
    }

    // Immediate, native Android feedback; editor confirmation remains in its
    // persistent non-floating status strip, including errors and release links.
    public void wcShowUpdateMessage(String message) {
        if (message == null || message.isEmpty()) return;
        runOnUiThread(() -> android.widget.Toast.makeText(
                this, message, android.widget.Toast.LENGTH_LONG).show());
    }

    public String wcPollUpdateResult() { return wcUpdateEvents.poll(); }

    public void wcOpenUpdatePage(String url) {
        if (url == null || !url.matches(
                "https://github\\.com/KosmosSG/artcraft-android/releases/tag/wordcraft-v[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[0-9]+"))
            return;
        runOnUiThread(() -> {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            } catch (Exception error) {
                Log.w(TAG, "Could not open WordCraft release page", error);
            }
        });
    }

    private final java.util.concurrent.atomic.AtomicInteger wcDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean wcDialogActive;
    private final java.util.HashSet<Integer> wcDialogKeys = new java.util.HashSet<>();
    public int wcUnsavedDialog(boolean active) {
        wcDialogActive = active;
        int action = wcDialogAction.getAndSet(0);
        return active ? action : 0;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {
            int code = event.getKeyCode();
            if (wcDialogKeys.contains(code)) {
                if (event.getAction() == android.view.KeyEvent.ACTION_UP) wcDialogKeys.remove(code);
                return true;
            }
            int action = code == android.view.KeyEvent.KEYCODE_D ? 1 : code == android.view.KeyEvent.KEYCODE_C ? 2 : code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;
            if (wcDialogActive && action != 0 && event.hasNoModifiers()
                    && event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                wcDialogKeys.add(code);
                if (event.getRepeatCount() == 0) wcDialogAction.compareAndSet(0, action);
                return true;
            }
        }

        return super.dispatchKeyEvent(event);
    }
