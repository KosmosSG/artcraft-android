
    // WordCraft-only Android enhancements. These are injected only into the isolated
    // WordCraft candidate's generated Activity; other ArtCraft apps are unchanged.
    private static final int WC_FONT_FOLDER_REQUEST = 0x5751;
    private static final String WC_FONT_TREE_KEY = "wordcraft_shared_font_tree";
    private static final int WC_FONT_IMPORT_REQUEST = 0x5752;
    private static final int WC_MAX_FONTS = 5_000;
    private static final int WC_MAX_FOLDERS = 20_000;
    private static final long WC_MAX_FONT_TOTAL_BYTES = 4L * 1024 * 1024 * 1024;
    private static final long WC_MAX_SINGLE_FONT_BYTES = 256L * 1024 * 1024;
    private final ConcurrentLinkedQueue<String> wcFontEvents = new ConcurrentLinkedQueue<>();
    private final ConcurrentLinkedQueue<String> wcUpdateEvents = new ConcurrentLinkedQueue<>();
    private final ExecutorService wcUpdateIo = Executors.newSingleThreadExecutor();

    // WC_INDIVIDUAL_FONT_IMPORT_V1: SAF picker for one or many TTF/OTF fonts.
    // Does not replace the selected persistent shared folder or require storage permission.
    public void wcImportFonts() {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivityForResult(intent, WC_FONT_IMPORT_REQUEST);
            } catch (Exception error) {
                wcFontError("Could not open font import picker: " + error.getMessage());
            }
        });
    }

    private void wcHandleImportedFonts(int resultCode, Intent data) {
        if (resultCode != RESULT_OK || data == null) {
            try { wcFontEvents.offer(new JSONObject().put("state", "cancelled").toString()); }
            catch (Exception ignored) { }
            return;
        }
        final java.util.LinkedHashSet<Uri> selected = new java.util.LinkedHashSet<>();
        if (data.getData() != null) selected.add(data.getData());
        android.content.ClipData clip = data.getClipData();
        if (clip != null) {
            for (int i = 0; i < clip.getItemCount() && selected.size() < WC_MAX_FONTS; i++) {
                Uri uri = clip.getItemAt(i).getUri();
                if (uri != null) selected.add(uri);
            }
        }
        if (selected.isEmpty()) {
            wcFontError("No font file selected");
            return;
        }
        io.execute(() -> wcStageImportedFonts(selected));
    }

    // Copies only selected font files to private, persistent app storage on the
    // existing SAF I/O executor. Native 'font.add' validates actual font bytes.
    private void wcStageImportedFonts(java.util.Set<Uri> selected) {
        File store = new File(appStorageDir(), "wordcraft-imported-font-cache");
        if (!store.isDirectory() && !store.mkdirs()) {
            wcFontError("Cannot create imported-font cache");
            return;
        }
        JSONArray paths = new JSONArray();
        int count = 0, skipped = 0;
        long bytes = 0L;
        try {
            for (Uri uri : selected) {
                if (count >= WC_MAX_FONTS || bytes >= WC_MAX_FONT_TOTAL_BYTES) break;
                String name = null;
                try (Cursor cursor = getContentResolver().query(uri,
                        new String[] { android.provider.OpenableColumns.DISPLAY_NAME }, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) name = cursor.getString(0);
                } catch (Exception ignored) { }
                if (name == null) { skipped++; continue; }
                String lower = name.toLowerCase(java.util.Locale.ROOT);
                if (!lower.endsWith(".ttf") && !lower.endsWith(".otf")
                        && !lower.endsWith(".ttc") && !lower.endsWith(".otc")) {
                    skipped++;
                    continue;
                }
                String suffix = lower.substring(lower.lastIndexOf('.'));
                String key = java.util.UUID.nameUUIDFromBytes(
                        uri.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
                File target = new File(store, "imported-" + key + suffix);
                if (target.isFile() && target.length() > 0
                        && bytes + target.length() <= WC_MAX_FONT_TOTAL_BYTES) {
                    paths.put(target.getAbsolutePath());
                    bytes += target.length(); count++;
                    continue;
                }
                File temp = new File(store, "imported-" + key + suffix + ".part");
                long copied = 0;
                try (InputStream in = getContentResolver().openInputStream(uri);
                     OutputStream out = new FileOutputStream(temp)) {
                    if (in == null) throw new java.io.IOException("Cannot open selected font");
                    byte[] buffer = new byte[65536];
                    int n;
                    while ((n = in.read(buffer)) != -1) {
                        copied += n;
                        if (copied > WC_MAX_SINGLE_FONT_BYTES
                                || bytes + copied > WC_MAX_FONT_TOTAL_BYTES)
                            throw new java.io.IOException("Font import size limit exceeded");
                        out.write(buffer, 0, n);
                    }
                    if (copied == 0) throw new java.io.IOException("Empty font");
                } catch (Exception ex) {
                    temp.delete();
                    skipped++;
                    Log.w(TAG, "Skipping invalid/unreadable selected font", ex);
                    continue;
                }
                if (target.isFile() && !target.delete()) {
                    temp.delete(); skipped++; continue;
                }
                if (!temp.renameTo(target)) {
                    temp.delete(); skipped++; continue;
                }
                paths.put(target.getAbsolutePath());
                bytes += copied;
                count++;
            }
            JSONObject result = new JSONObject();
            result.put("state", "ok");
            result.put("paths", paths);
            result.put("count", count);
            result.put("skipped", skipped);
            result.put("limited", selected.size() > WC_MAX_FONTS || bytes >= WC_MAX_FONT_TOTAL_BYTES);
            result.put("scannedBytes", bytes);
            wcFontEvents.offer(result.toString());
        } catch (Exception ex) {
            wcFontError("Could not import selected fonts: " + ex.getMessage());
        }
    }

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
            while (!pending.isEmpty() && scannedFolders < WC_MAX_FOLDERS && copied < WC_MAX_FONTS
                    && copiedBytes < WC_MAX_FONT_TOTAL_BYTES) {
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
                    while (cursor.moveToNext() && copied < WC_MAX_FONTS
                            && copiedBytes < WC_MAX_FONT_TOTAL_BYTES) {
                        String id = cursor.getString(0);
                        String name = cursor.getString(1);
                        String mime = cursor.getString(2);
                        if (id == null || name == null) continue;
                        if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                            if (pending.size() + seen.size() < WC_MAX_FOLDERS) pending.addLast(id);
                            continue;
                        }
                        String lower = name.toLowerCase(java.util.Locale.ROOT);
                        if (!lower.endsWith(".ttf") && !lower.endsWith(".otf")
                                && !lower.endsWith(".ttc") && !lower.endsWith(".otc")) continue;
                        long size = cursor.isNull(3) ? -1 : cursor.getLong(3);
                        if (size == 0 || size > WC_MAX_SINGLE_FONT_BYTES
                                || (size > 0 && copiedBytes + size > WC_MAX_FONT_TOTAL_BYTES)) { skipped++; continue; }
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
                                if (total > WC_MAX_SINGLE_FONT_BYTES
                                        || copiedBytes + total > WC_MAX_FONT_TOTAL_BYTES)
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
            result.put("limited", !pending.isEmpty() || copied >= WC_MAX_FONTS
                    || copiedBytes >= WC_MAX_FONT_TOTAL_BYTES || scannedFolders >= WC_MAX_FOLDERS);
            result.put("scannedBytes", copiedBytes);
            result.put("maxFonts", WC_MAX_FONTS);
            result.put("maxBytes", WC_MAX_FONT_TOTAL_BYTES);
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


    // Physical trackpad / mouse-wheel to document canvas bridge. Stock Android
    // winit receives finger touches but ignores ACTION_SCROLL for pointer sources.
    // Capture both axes here, without swallowing touches, drag, Android back
    // gestures or any non-scroll event. Native reads one coalesced value per frame.
    private final Object wcScrollLock = new Object();
    private float wcScrollX;
    private float wcScrollY;
    private float wcScrollPointerX;
    private float wcScrollPointerY;

    @Override public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        if (event != null && event.getActionMasked() == android.view.MotionEvent.ACTION_SCROLL) {
            int source = event.getSource();
            boolean trackpadOrMouse =
                    (source & android.view.InputDevice.SOURCE_MOUSE) == android.view.InputDevice.SOURCE_MOUSE
                    || (source & android.view.InputDevice.SOURCE_TOUCHPAD) == android.view.InputDevice.SOURCE_TOUCHPAD;
            if (trackpadOrMouse) {
                float horizontal = event.getAxisValue(android.view.MotionEvent.AXIS_HSCROLL);
                float vertical = event.getAxisValue(android.view.MotionEvent.AXIS_VSCROLL);
                if (Float.isFinite(horizontal) && Float.isFinite(vertical)
                        && (horizontal != 0.0f || vertical != 0.0f)) {
                    android.view.ViewConfiguration config = android.view.ViewConfiguration.get(this);
                    // Android scroll factors are physical pixels per axis unit.
                    // Rust converts these to egui points using the live viewport scale.
                    float dx = horizontal * config.getScaledHorizontalScrollFactor();
                    float dy = vertical * config.getScaledVerticalScrollFactor();
                    if (Float.isFinite(dx) && Float.isFinite(dy)) {
                        synchronized (wcScrollLock) {
                            wcScrollX += dx;
                            wcScrollY += dy;
                            wcScrollPointerX = event.getX();
                            wcScrollPointerY = event.getY();
                        }
                        // Let GameActivity's input queue wake the native event loop.
                        // It currently ignores ACTION_SCROLL; Rust consumes our bridge
                        // only once and translates it to an egui Point wheel event.
                        super.dispatchGenericMotionEvent(event);
                        return true;
                    }
                }
            }
        }
        return super.dispatchGenericMotionEvent(event);
    }

    public String wcTakeTrackpadScroll() {
        synchronized (wcScrollLock) {
            if (wcScrollX == 0.0f && wcScrollY == 0.0f) return null;
            String message = Float.toString(wcScrollX) + ","
                    + Float.toString(wcScrollY) + ","
                    + Float.toString(wcScrollPointerX) + ","
                    + Float.toString(wcScrollPointerY);
            wcScrollX = 0.0f;
            wcScrollY = 0.0f;
            return message;
        }
    }


    // Two-finger touchscreen canvas pan; do not swallow native touch/pinch.
    private final Object wcTouchPanLock = new Object();
    private boolean wcTouchPairActive;
    private float wcTouchLastX, wcTouchLastY, wcTouchLastSpan;
    private float wcTouchPanX, wcTouchPanY, wcTouchPanCenterX, wcTouchPanCenterY;

    @Override public boolean dispatchTouchEvent(android.view.MotionEvent event) {
        if (event != null && event.isFromSource(android.view.InputDevice.SOURCE_TOUCHSCREEN)) {
            synchronized (wcTouchPanLock) {
                int action = event.getActionMasked();
                if (event.getPointerCount() == 2
                        && (action == android.view.MotionEvent.ACTION_POINTER_DOWN
                            || action == android.view.MotionEvent.ACTION_MOVE)) {
                    float x = (event.getX(0) + event.getX(1)) * .5f;
                    float y = (event.getY(0) + event.getY(1)) * .5f;
                    float span = (float) Math.hypot(event.getX(1) - event.getX(0),
                                                     event.getY(1) - event.getY(0));
                    if (Float.isFinite(x) && Float.isFinite(y) && Float.isFinite(span)) {
                        if (wcTouchPairActive && action == android.view.MotionEvent.ACTION_MOVE) {
                            float dx = x - wcTouchLastX, dy = y - wcTouchLastY;
                            if (Math.abs(span - wcTouchLastSpan) < Math.max(6f, wcTouchLastSpan * .025f)
                                    && Math.abs(dx) < 160f && Math.abs(dy) < 160f) {
                                wcTouchPanX += dx;
                                wcTouchPanY += dy;
                                wcTouchPanCenterX = x;
                                wcTouchPanCenterY = y;
                            }
                        }
                        wcTouchPairActive = true;
                        wcTouchLastX = x;
                        wcTouchLastY = y;
                        wcTouchLastSpan = span;
                    }
                } else if (action == android.view.MotionEvent.ACTION_POINTER_UP
                        || action == android.view.MotionEvent.ACTION_UP
                        || action == android.view.MotionEvent.ACTION_CANCEL
                        || event.getPointerCount() != 2) {
                    wcTouchPairActive = false;
                }
            }
        }
        return super.dispatchTouchEvent(event);
    }

    public String wcTakeTwoFingerPan() {
        synchronized (wcTouchPanLock) {
            if (wcTouchPanX == 0f && wcTouchPanY == 0f) return null;
            String value = wcTouchPanX + "," + wcTouchPanY + ","
                         + wcTouchPanCenterX + "," + wcTouchPanCenterY;
            wcTouchPanX = wcTouchPanY = 0f;
            return value;
        }
    }

    // WC_ANDROID_FAST_INPUT_V1: notify Rust while the hidden Android IME host
    // is active so pending keyboard commits are collected on responsive frames.
    public boolean wcFastInputActive() { return imeWanted; }

    private final java.util.concurrent.atomic.AtomicInteger wcDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean wcDialogActive;
    private final java.util.concurrent.atomic.AtomicInteger wcNewDocument = new java.util.concurrent.atomic.AtomicInteger();
    public boolean wcTakeNewDocument() { return wcNewDocument.getAndSet(0) != 0; }
    private final java.util.concurrent.atomic.AtomicInteger wcSaveAs = new java.util.concurrent.atomic.AtomicInteger();
    public boolean wcTakeSaveAs() { return wcSaveAs.getAndSet(0) != 0; }
    private final java.util.concurrent.atomic.AtomicInteger wcQuit = new java.util.concurrent.atomic.AtomicInteger();
    public boolean wcTakeQuit() { return wcQuit.getAndSet(0) != 0; }
    private final java.util.HashSet<Integer> wcDialogKeys = new java.util.HashSet<>();
    public int wcUnsavedDialog(boolean active) {
        boolean justOpened = active && !wcDialogActive;
        wcDialogActive = active;
        if (justOpened) {
            // The native Activity can retain keyboard focus in the editor/IME.
            // Reacquire the app window when the modal opens, without requiring
            // a manual tap on the WordCraft dialog title bar.
            runOnUiThread(() -> {
                android.view.Window window = getWindow();
                if (window != null && window.getDecorView() != null) {
                    window.getDecorView().setFocusableInTouchMode(true);
                    window.getDecorView().requestFocus();
                }
            });
            Log.i(TAG, "WC_DCS_DIAG modal_focus_requested");
        }
        // Do not silently drain a queued key while the UI is transitioning
        // into or out of the dialog. The dialog consumes its own choice.
        if (!active) { wcDialogAction.set(0); return 0; }
        int action = wcDialogAction.getAndSet(0);
        if (action != 0) Log.i(TAG, "WC_DCS_DIAG delivered=" + action);
        return action;
    }
    // Intercepts the IME path where physical D/C/S never reach GameActivity.
    public boolean wcHandleImeChoice(CharSequence text) {
        if (!wcDialogActive || text == null || text.length() != 1) return false;
        char c = Character.toLowerCase(text.charAt(0));
        int choice = c == 'd' ? 1 : c == 'c' ? 2 : c == 's' ? 3 : 0;
        if (choice == 0) return false;
        wcDialogAction.compareAndSet(0, choice);
        Log.i(TAG, "WC_DCS_DIAG ime_choice=" + choice);
        return true;
    }

    // Called by Activity, invisible EditText and its InputConnection. Never
    // intercept a normal letter unless the unsaved-changes dialog is open.
    public boolean wcHandleHardwareShortcut(android.view.KeyEvent event) {
        if (event == null) return false;
        int key = event.getKeyCode();
        if (wcDialogKeys.contains(key)) {
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) wcDialogKeys.remove(key);
            return true;
        }
        if (wcDialogActive && event.hasNoModifiers()) {
            int choice = key == android.view.KeyEvent.KEYCODE_D ? 1
                    : key == android.view.KeyEvent.KEYCODE_C ? 2
                    : key == android.view.KeyEvent.KEYCODE_S ? 3
                    : key == android.view.KeyEvent.KEYCODE_ESCAPE ? 2 : 0;
            if (choice != 0) {
                if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                    wcDialogKeys.add(key);
                    if (event.getRepeatCount() == 0) {
                        wcDialogAction.compareAndSet(0, choice);
                        Log.i(TAG, "WC_DCS_DIAG physical_choice=" + choice);
                    }
                }
                return true;
            }
        }
        if (!wcDialogActive && event.isCtrlPressed()
                && !event.isAltPressed() && !event.isMetaPressed()) {
            int cmd = 0;
            if (event.isShiftPressed() && key == android.view.KeyEvent.KEYCODE_S) cmd = 1;
            else if (!event.isShiftPressed() && key == android.view.KeyEvent.KEYCODE_N) cmd = 2;
            else if (!event.isShiftPressed() && key == android.view.KeyEvent.KEYCODE_Q) cmd = 3;
            if (cmd != 0) {
                if (event.getAction() == android.view.KeyEvent.ACTION_DOWN
                        && event.getRepeatCount() == 0) {
                    if (cmd == 1) wcSaveAs.set(1);
                    if (cmd == 2) wcNewDocument.set(1);
                    if (cmd == 3) wcQuit.set(1);
                    Log.i(TAG, "WC_SHORTCUT_DIAG physical_command=" + cmd);
                }
                return true;
            }
        }
        return false;
    }

    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (wcHandleHardwareShortcut(event)) return true;
        return super.dispatchKeyEvent(event);
    }
