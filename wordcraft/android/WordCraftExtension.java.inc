
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


    // WC_ANDROID_STYLUS_INPUT_V1: native Android pen/eraser identification.
    // Uses TOOL_TYPE_* rather than assuming every touchscreen contact is a pen.
    // Existing upstream Draw tab owns ink geometry, editing, undo and saving.
    private volatile boolean wcPenSeen = false;
    private volatile boolean wcPenHover = false;
    private volatile boolean wcPenContact = false;
    private volatile float wcPenPressure = 0f;
    private volatile float wcPenTilt = 0f;
    private volatile float wcPenPeakPressure = 0f;
    private volatile float wcPenLastContactPressure = 0f;
    private volatile float wcPenHoverX = Float.NaN;
    private volatile float wcPenHoverY = Float.NaN;
    // Keep historical stylus events that the egui frame-based pointer misses.
    private final Object wcStylusTrailLock = new Object();
    private final java.util.ArrayDeque<String> wcStylusTrail = new java.util.ArrayDeque<>();
    private static final int WC_STYLUS_TRAIL_LIMIT = 256;
    private volatile long wcPenEventAt = 0L;
    private boolean wcPalmSuppressed = false;
    private int wcPalmSuppressedCount = 0;

    private static boolean wcHasStylus(android.view.MotionEvent event) {
        if (event == null) return false;
        for (int i = 0; i < event.getPointerCount(); i++) {
            int tool = event.getToolType(i);
            if (tool == android.view.MotionEvent.TOOL_TYPE_STYLUS
                    || tool == android.view.MotionEvent.TOOL_TYPE_ERASER) return true;
        }
        return false;
    }

    private static boolean wcOnlyFingers(android.view.MotionEvent event) {
        if (event == null || event.getPointerCount() < 1) return false;
        for (int i = 0; i < event.getPointerCount(); i++) {
            if (event.getToolType(i) != android.view.MotionEvent.TOOL_TYPE_FINGER) return false;
        }
        return true;
    }

    private void wcRecordStylus(android.view.MotionEvent event) {
        if (!wcHasStylus(event)) return;
        wcPenSeen = true;
        wcPenEventAt = android.os.SystemClock.uptimeMillis();
        int action = event.getActionMasked();
        boolean hover = action == android.view.MotionEvent.ACTION_HOVER_ENTER
                || action == android.view.MotionEvent.ACTION_HOVER_MOVE;
        if (hover) { wcPenHover = true; wcPenContact = false; }
        else if (action == android.view.MotionEvent.ACTION_DOWN
                || action == android.view.MotionEvent.ACTION_MOVE
                || action == android.view.MotionEvent.ACTION_POINTER_DOWN) {
            wcPenContact = true;
            wcPenHover = false;
        } else if (action == android.view.MotionEvent.ACTION_UP
                || action == android.view.MotionEvent.ACTION_POINTER_UP
                || action == android.view.MotionEvent.ACTION_CANCEL) {
            wcPenContact = false;
        } else if (action == android.view.MotionEvent.ACTION_HOVER_EXIT) {
            wcPenHover = false;
        }
        for (int i = 0; i < event.getPointerCount(); i++) {
            int tool = event.getToolType(i);
            if (tool == android.view.MotionEvent.TOOL_TYPE_STYLUS
                    || tool == android.view.MotionEvent.TOOL_TYPE_ERASER) {
                if (hover) {
                    wcPenHoverX = event.getX(i);
                    wcPenHoverY = event.getY(i);
                }
                if (action == android.view.MotionEvent.ACTION_HOVER_EXIT) {
                    wcPenHoverX = Float.NaN;
                    wcPenHoverY = Float.NaN;
                }
                wcPenPressure = event.getPressure(i);
                if (wcPenContact && Float.isFinite(wcPenPressure)) {
                    wcPenLastContactPressure = wcPenPressure;
                    wcPenPeakPressure = Math.max(wcPenPeakPressure, wcPenPressure);
                }
                wcPenTilt = event.getAxisValue(android.view.MotionEvent.AXIS_TILT, i);
                break;
            }
        }
    }

    // WC_ANDROID_STYLUS_HISTORY_V1: preserve Android's historical pen movement
    // while forwarding the original event to GameActivity unmodified.
    private static final String WC_PRESSURE_PREFS = "wordcraft_android_stylus";
    // WC_ANDROID10_PRESSURE_DEFAULT_ON_V1: new candidate installs enable
    // pressure-sensitive ink automatically, without changing stored choices
    // made by existing installations.
    public boolean wcPressureInkEnabled() {
        return getSharedPreferences(WC_PRESSURE_PREFS, MODE_PRIVATE)
                .getBoolean("pressure_ink", true);
    }
    public void wcSetPressureInkEnabled(boolean on) {
        getSharedPreferences(WC_PRESSURE_PREFS, MODE_PRIVATE).edit()
                .putBoolean("pressure_ink", on).apply();
    }

    private void wcAppendStylusPoint(float x, float y, float pressure) {
        if (!Float.isFinite(x) || !Float.isFinite(y)) return;
        if (!Float.isFinite(pressure) || pressure <= 0f) pressure = 0f;
        synchronized (wcStylusTrailLock) {
            while (wcStylusTrail.size() >= WC_STYLUS_TRAIL_LIMIT)
                wcStylusTrail.pollFirst();
            wcStylusTrail.addLast(Float.toString(x) + "," + Float.toString(y) + "," + Float.toString(pressure));
        }
    }

    private void wcCaptureStylusHistory(android.view.MotionEvent event) {
        if (!wcHasStylus(event)) return;
        int action = event.getActionMasked();
        if (action != android.view.MotionEvent.ACTION_DOWN
                && action != android.view.MotionEvent.ACTION_MOVE
                && action != android.view.MotionEvent.ACTION_UP
                && action != android.view.MotionEvent.ACTION_POINTER_DOWN
                && action != android.view.MotionEvent.ACTION_POINTER_UP) return;
        if (action == android.view.MotionEvent.ACTION_DOWN) {
            synchronized (wcStylusTrailLock) { wcStylusTrail.clear(); }
            wcPenPeakPressure = 0f;
            wcPenLastContactPressure = 0f;
        }
        for (int i = 0; i < event.getPointerCount(); ++i) {
            int tool = event.getToolType(i);
            if (tool != android.view.MotionEvent.TOOL_TYPE_STYLUS
                    && tool != android.view.MotionEvent.TOOL_TYPE_ERASER) continue;
            final int count = event.getHistorySize();
            for (int h = Math.max(0, count - 80); h < count; ++h) {
                wcAppendStylusPoint(event.getHistoricalX(i, h), event.getHistoricalY(i, h),
                        event.getHistoricalPressure(i, h));
                float pressure = event.getHistoricalPressure(i, h);
                if (Float.isFinite(pressure))
                    wcPenPeakPressure = Math.max(wcPenPeakPressure, pressure);
            }
            wcAppendStylusPoint(event.getX(i), event.getY(i), event.getPressure(i));
            float pressure = event.getPressure(i);
            if (Float.isFinite(pressure) && pressure > 0f)
                wcPenPeakPressure = Math.max(wcPenPeakPressure, pressure);
        }
    }

    /** One-shot batched pen samples; safe to poll from the native UI thread. */
    public String wcTakeStylusTrail() {
        synchronized (wcStylusTrailLock) {
            if (wcStylusTrail.isEmpty()) return null;
            StringBuilder result = new StringBuilder(wcStylusTrail.size() * 20);
            for (String sample : wcStylusTrail) {
                if (result.length() > 0) result.append(';');
                result.append(sample);
            }
            wcStylusTrail.clear();
            return result.toString();
        }
    }

    /** Non-contact cursor position. Does not synthesize drawing/press events. */
    public String wcStylusHoverPosition() {
        if (!wcPenHover || !Float.isFinite(wcPenHoverX) || !Float.isFinite(wcPenHoverY))
            return null;
        return Float.toString(wcPenHoverX) + "," + Float.toString(wcPenHoverY);
    }

    /** Read-only, throttled by the Rust UI; diagnostic status in the Wc icon menu. */
    public String wcStylusStatus() {
        if (!wcPenSeen) return "Stylus: Not detected yet";
        if (wcPenContact) return "Stylus: Contact | pressure " + wcPenPressure
                + " | peak " + wcPenPeakPressure;
        if (wcPenSeen && wcPenPeakPressure > 0f && !wcPenHover)
            return "Stylus: Detected | last pressure " + wcPenLastContactPressure
                    + " | peak " + wcPenPeakPressure;
        if (wcPenHover) return "Stylus: Hovering | last pressure "
                + wcPenLastContactPressure + " | peak " + wcPenPeakPressure;
        return "Stylus: Detected";
    }

    /**
     * Conservative palm filtering while pen contact is active.
     * A swallowed finger gesture remains swallowed until UP/CANCEL, preventing
     * orphan MOVE input from reaching upstream. Stylus events always pass through.
     * Two-finger scrolling remains unchanged whenever pen is not in contact.
     */
    private boolean wcRejectPalm(android.view.MotionEvent event) {
        if (event == null || wcHasStylus(event)) return false;
        int action = event.getActionMasked();
        if (wcPalmSuppressed) {
            if (action == android.view.MotionEvent.ACTION_UP
                    || action == android.view.MotionEvent.ACTION_CANCEL) {
                wcPalmSuppressed = false;
            }
            wcPalmSuppressedCount++;
            return true;
        }
        if (action == android.view.MotionEvent.ACTION_DOWN
                && wcOnlyFingers(event) && wcPenContact) {
            wcPalmSuppressed = true;
            wcPalmSuppressedCount++;
            return true;
        }
        return false;
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
    private float wcScrollZoom = 1.0f;
    private boolean wcClassifiedTrackpadActive;

    // WC_ANDROID10_CLASSIFIED_TRACKPAD_V1: Android 14+ touchpads send
    // single-pointer SOURCE_MOUSE ACTION_MOVE with a gesture classification.
    // Previous pointerCount>=2 tracking cannot see these gestures.
    private boolean wcDispatchClassifiedTrackpad(android.view.MotionEvent event) {
        if (event == null || android.os.Build.VERSION.SDK_INT < 34
                || wcHasStylus(event)
                || !(event.isFromSource(android.view.InputDevice.SOURCE_MOUSE)
                    || event.isFromSource(android.view.InputDevice.SOURCE_TOUCHPAD)))
            return false;
        int action = event.getActionMasked();
        int cls = event.getClassification();
        boolean swipe = cls == android.view.MotionEvent.CLASSIFICATION_TWO_FINGER_SWIPE;
        boolean pinch = cls == android.view.MotionEvent.CLASSIFICATION_PINCH;
        boolean sample = (action == android.view.MotionEvent.ACTION_MOVE
                || action == android.view.MotionEvent.ACTION_SCROLL) && (swipe || pinch);
        if (!sample && !wcClassifiedTrackpadActive) return false;
        if (sample && !wcClassifiedTrackpadActive) {
            wcClassifiedTrackpadActive = true;
            // Cancel any one-finger editor drag before adopting navigation;
            // the original ACTION_MOVE must never reach text/ink processing.
            android.view.MotionEvent cancel = android.view.MotionEvent.obtain(event);
            try {
                cancel.setAction(android.view.MotionEvent.ACTION_CANCEL);
                super.dispatchTouchEvent(cancel);
            } finally { cancel.recycle(); }
        }
        wcMarkTrackpadNavigation();
        if (sample) {
            float dx = 0f, dy = 0f, zoom = 1f;
            int history = event.getHistorySize();
            // Gesture axes describe DELTAS, not positions. Consume history as
            // well as the current sample or horizontal pan/pinch will stutter.
            for (int h = 0; h <= history; h++) {
                boolean now = h == history;
                float sx = now
                        ? event.getAxisValue(android.view.MotionEvent.AXIS_GESTURE_SCROLL_X_DISTANCE)
                        : event.getHistoricalAxisValue(android.view.MotionEvent.AXIS_GESTURE_SCROLL_X_DISTANCE, 0, h);
                float sy = now
                        ? event.getAxisValue(android.view.MotionEvent.AXIS_GESTURE_SCROLL_Y_DISTANCE)
                        : event.getHistoricalAxisValue(android.view.MotionEvent.AXIS_GESTURE_SCROLL_Y_DISTANCE, 0, h);
                float p = now
                        ? event.getAxisValue(android.view.MotionEvent.AXIS_GESTURE_PINCH_SCALE_FACTOR)
                        : event.getHistoricalAxisValue(android.view.MotionEvent.AXIS_GESTURE_PINCH_SCALE_FACTOR, 0, h);
                if (swipe && Float.isFinite(sx) && Float.isFinite(sy)) {
                    dx += sx;
                    dy += sy;
                }
                if (pinch && Float.isFinite(p) && p > 0f)
                    zoom *= Math.max(.80f, Math.min(1.25f, p));
            }
            if (swipe && action == android.view.MotionEvent.ACTION_SCROLL
                    && dx == 0f && dy == 0f) {
                // Android vendors may supply conventional wheel axes instead.
                android.view.ViewConfiguration config = android.view.ViewConfiguration.get(this);
                dx = event.getAxisValue(android.view.MotionEvent.AXIS_HSCROLL)
                        * config.getScaledHorizontalScrollFactor();
                dy = event.getAxisValue(android.view.MotionEvent.AXIS_VSCROLL)
                        * config.getScaledVerticalScrollFactor();
            }
            if (Float.isFinite(dx) && Float.isFinite(dy) && Float.isFinite(zoom)) {
                synchronized (wcScrollLock) {
                    wcScrollX += Math.max(-240f, Math.min(240f, dx));
                    wcScrollY += Math.max(-240f, Math.min(240f, dy));
                    wcScrollZoom = Math.max(.2f, Math.min(5f, wcScrollZoom * zoom));
                    wcScrollPointerX = event.getX();
                    wcScrollPointerY = event.getY();
                }
            }
        }
        if (action == android.view.MotionEvent.ACTION_UP
                || action == android.view.MotionEvent.ACTION_CANCEL) {
            wcClassifiedTrackpadActive = false;
        }
        // Gesture is consumed here, never delivered to editor as a mouse drag.
        return true;
    }

    // WC_ANDROID9_PINCH_TRACKPAD_GUARD_V1: prevent trackpad gesture drags.
    private volatile long wcTrackpadNavUntilMs;
    private boolean wcTrackpadPairConsuming, wcTrackpadPairActive;
    private float wcTrackpadLastX, wcTrackpadLastY;
    private void wcMarkTrackpadNavigation() {
        wcTrackpadNavUntilMs = android.os.SystemClock.uptimeMillis() + 180L;
    }
    public boolean wcTrackpadNavigationActive() {
        return android.os.SystemClock.uptimeMillis() < wcTrackpadNavUntilMs;
    }
    // MagicOS may send dual-contact touchpad input instead of ACTION_SCROLL.
    // Cancel the original editor pointer and swallow all remaining pair events.
    private boolean wcDispatchTrackpadFingers(android.view.MotionEvent event) {
        if (event == null || wcHasStylus(event)
                || (!event.isFromSource(android.view.InputDevice.SOURCE_TOUCHPAD)
                    && !(event.isFromSource(android.view.InputDevice.SOURCE_MOUSE)
                         && (wcTrackpadPairConsuming || event.getPointerCount() >= 2))))
            return false;
        int action = event.getActionMasked();
        boolean start = !wcTrackpadPairConsuming && event.getPointerCount() >= 2
                && (action == android.view.MotionEvent.ACTION_POINTER_DOWN
                    || action == android.view.MotionEvent.ACTION_MOVE);
        if (start) {
            wcTrackpadPairConsuming = true;
            wcTrackpadPairActive = false;
            wcMarkTrackpadNavigation();
            android.view.MotionEvent cancel = android.view.MotionEvent.obtain(event);
            try {
                cancel.setAction(android.view.MotionEvent.ACTION_CANCEL);
                super.dispatchTouchEvent(cancel);
            } finally { cancel.recycle(); }
        }
        if (!wcTrackpadPairConsuming) return false;
        wcMarkTrackpadNavigation();
        if (event.getPointerCount() >= 2 && action == android.view.MotionEvent.ACTION_MOVE) {
            int history = event.getHistorySize();
            for (int i = Math.max(0, history - 64); i <= history; i++) {
                boolean current = i == history;
                float x = (current ? event.getX(0) + event.getX(1)
                        : event.getHistoricalX(0, i) + event.getHistoricalX(1, i)) * .5f;
                float y = (current ? event.getY(0) + event.getY(1)
                        : event.getHistoricalY(0, i) + event.getHistoricalY(1, i)) * .5f;
                if (wcTrackpadPairActive) {
                    float dx = x - wcTrackpadLastX, dy = y - wcTrackpadLastY;
                    if (Float.isFinite(dx) && Float.isFinite(dy)
                            && Math.abs(dx) < 160f && Math.abs(dy) < 160f) {
                        synchronized (wcScrollLock) {
                            wcScrollX += dx;
                            wcScrollY += dy;
                        }
                    }
                }
                wcTrackpadLastX = x; wcTrackpadLastY = y;
                wcTrackpadPairActive = true;
            }
        } else if (action == android.view.MotionEvent.ACTION_POINTER_DOWN
                && event.getPointerCount() >= 2) {
            wcTrackpadLastX = (event.getX(0) + event.getX(1)) * .5f;
            wcTrackpadLastY = (event.getY(0) + event.getY(1)) * .5f;
            wcTrackpadPairActive = true;
        }
        if (action == android.view.MotionEvent.ACTION_POINTER_UP) wcTrackpadPairActive = false;
        if (action == android.view.MotionEvent.ACTION_UP
                || action == android.view.MotionEvent.ACTION_CANCEL) {
            wcTrackpadPairConsuming = false;
            wcTrackpadPairActive = false;
        }
        return true;
    }

    @Override public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        if (wcHasStylus(event)) wcRecordStylus(event);
        if (wcDispatchClassifiedTrackpad(event)) return true;
        if (event != null
                && event.getActionMasked() == android.view.MotionEvent.ACTION_HOVER_MOVE
                && event.isFromSource(android.view.InputDevice.SOURCE_MOUSE)) {
            synchronized (wcScrollLock) {
                wcScrollPointerX = event.getX();
                wcScrollPointerY = event.getY();
            }
        }
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
                        wcMarkTrackpadNavigation();
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
            if (wcScrollX == 0.0f && wcScrollY == 0.0f && wcScrollZoom == 1f)
                return null;
            String message = Float.toString(wcScrollX) + ","
                    + Float.toString(wcScrollY) + ","
                    + Float.toString(wcScrollPointerX) + ","
                    + Float.toString(wcScrollPointerY) + ","
                    + Float.toString(wcScrollZoom);
            wcScrollX = 0.0f;
            wcScrollY = 0.0f;
            wcScrollZoom = 1f;
            return message;
        }
    }


    // WC_TWOFINGER_NAV_NO_SELECTION_V2: a two-finger gesture owns the canvas;
    // never dispatch its MOVE/UP as editing, object drag or pen input.
    private final Object wcTouchPanLock = new Object();
    private boolean wcTouchPairActive, wcTouchNavConsuming;
    private volatile boolean wcTouchNavSuppressInk;
    private int wcTouchMode; // 1 pan (default), 2 deliberate pinch
    private int wcTouchPinchEvidence;
    private float wcTouchStartSpan, wcTouchStartX, wcTouchStartY, wcTouchLastX, wcTouchLastY, wcTouchLastSpan;
    private float wcTouchLastFinger0X, wcTouchLastFinger0Y, wcTouchLastFinger1X, wcTouchLastFinger1Y;
    private float wcTouchPreviousPanX;
    private float wcTouchPanX, wcTouchPanY, wcTouchPanCenterX, wcTouchPanCenterY;
    private float wcTouchZoom = 1f;
    private volatile float wcCanvasLeft = Float.NaN, wcCanvasTop = Float.NaN;
    private volatile float wcCanvasRight = Float.NaN, wcCanvasBottom = Float.NaN;

    public void wcSetTouchCanvasBounds(String bounds) {
        if (bounds == null) return;
        String[] p = bounds.split(",", -1);
        if (p.length != 4) return;
        try {
            float l = Float.parseFloat(p[0]), t = Float.parseFloat(p[1]);
            float r = Float.parseFloat(p[2]), b = Float.parseFloat(p[3]);
            if (Float.isFinite(l) && Float.isFinite(t)
                    && Float.isFinite(r) && Float.isFinite(b) && r > l && b > t) {
                wcCanvasLeft = l; wcCanvasTop = t;
                wcCanvasRight = r; wcCanvasBottom = b;
            } else {
                wcCanvasLeft = wcCanvasTop = wcCanvasRight = wcCanvasBottom = Float.NaN;
            }
        } catch (NumberFormatException ex) {
            wcCanvasLeft = wcCanvasTop = wcCanvasRight = wcCanvasBottom = Float.NaN;
        }
    }

    public boolean wcTouchNavigationCancellingInk() {
        return wcTouchNavSuppressInk || wcTrackpadNavigationActive();
    }

    private boolean wcTouchOnCanvas(float x, float y) {
        return Float.isFinite(x) && Float.isFinite(y)
                && x >= wcCanvasLeft && x <= wcCanvasRight
                && y >= wcCanvasTop && y <= wcCanvasBottom;
    }

    // WC_ANDROID11_PAN_FIRST_PINCH_HYSTERESIS_V1
    // All historical samples are consumed; navigation begins on the first
    // two-finger MOVE rather than waiting for an arbitrary hold/drag threshold.
    // Pinch requires coherent distance growth/shrink and two consecutive
    // samples with distance motion dominant over centroid motion.
    private void wcAccumulateTwoFingerSample(float x0, float y0, float x1, float y1) {
        if (!Float.isFinite(x0) || !Float.isFinite(y0)
                || !Float.isFinite(x1) || !Float.isFinite(y1)) return;
        float x = (x0 + x1) * .5f, y = (y0 + y1) * .5f;
        float span = (float) Math.hypot(x1 - x0, y1 - y0);
        if (!Float.isFinite(span)) return;
        if (wcTouchPairActive) {
            float dx = x - wcTouchLastX, dy = y - wcTouchLastY;
            float spanStep = Math.abs(span - wcTouchLastSpan);
            float centerStep = (float) Math.hypot(dx, dy);
            float cumulativeSpan = Math.abs(span - wcTouchStartSpan);
            float d0x = x0 - wcTouchLastFinger0X, d0y = y0 - wcTouchLastFinger0Y;
            float d1x = x1 - wcTouchLastFinger1X, d1y = y1 - wcTouchLastFinger1Y;
            boolean opposed = d0x * d1x + d0y * d1y < 0f;
            boolean scaleDominant = spanStep > Math.max(2.0f, centerStep * 1.2f)
                    && (opposed || centerStep < spanStep * .7f);
            boolean intentionalPinch = scaleDominant
                    && cumulativeSpan > Math.max(11f, wcTouchStartSpan * .03f);
            if (wcTouchMode == 1) {
                wcTouchPinchEvidence = intentionalPinch
                        ? Math.min(3, wcTouchPinchEvidence + 1) : 0;
                if (wcTouchPinchEvidence >= 2) {
                    wcTouchMode = 2;
                    // Never send accumulated pan and pinch in the same frame.
                    wcTouchPanX = wcTouchPanY = 0f;
                    wcTouchPreviousPanX = 0f;
                }
            }
            if (wcTouchMode == 2 && wcTouchLastSpan > 0f) {
                float ratio = span / wcTouchLastSpan;
                if (Float.isFinite(ratio) && ratio > 0f)
                    wcTouchZoom = Math.max(.2f, Math.min(5f,
                            wcTouchZoom * Math.max(.75f, Math.min(1.33f, ratio))));
            } else if (wcTouchMode == 1 && Math.abs(dx) < 160f && Math.abs(dy) < 160f) {
                // Apply a light horizontal low-pass only; vertical pan already
                // performs well. Historical deltas remain accumulated per frame.
                wcTouchPanX += dx * .80f + wcTouchPreviousPanX * .20f;
                wcTouchPreviousPanX = dx;
                wcTouchPanY += dy;
            }
        } else {
            wcTouchStartSpan = Math.max(span, 1f);
            wcTouchStartX = x; wcTouchStartY = y;
            wcTouchMode = 1; // Two-finger pan immediately, no hold required.
            wcTouchPinchEvidence = 0;
            wcTouchPreviousPanX = 0f;
        }
        wcTouchPairActive = true;
        wcTouchLastX = x; wcTouchLastY = y; wcTouchLastSpan = span;
        wcTouchLastFinger0X = x0; wcTouchLastFinger0Y = y0;
        wcTouchLastFinger1X = x1; wcTouchLastFinger1Y = y1;
        wcTouchPanCenterX = x; wcTouchPanCenterY = y;
    }

    private void wcAccumulateTwoFingerEvent(android.view.MotionEvent event, int historyIndex) {
        float x0 = historyIndex < 0 ? event.getX(0) : event.getHistoricalX(0, historyIndex);
        float x1 = historyIndex < 0 ? event.getX(1) : event.getHistoricalX(1, historyIndex);
        float y0 = historyIndex < 0 ? event.getY(0) : event.getHistoricalY(0, historyIndex);
        float y1 = historyIndex < 0 ? event.getY(1) : event.getHistoricalY(1, historyIndex);
        wcAccumulateTwoFingerSample(x0, y0, x1, y1);
    }

    @Override public boolean dispatchTouchEvent(android.view.MotionEvent event) {
        if (wcHasStylus(event)) {
            wcRecordStylus(event);
            wcCaptureStylusHistory(event);
            if (event != null
                    && event.getActionMasked() == android.view.MotionEvent.ACTION_DOWN) {
                wcTrackpadNavUntilMs = 0L;
                // Stylus is an independent editing tool. Starting a new pen
                // stroke must clear the previous finger navigation latch.
                synchronized (wcTouchPanLock) {
                    wcTouchNavSuppressInk = false;
                    wcTouchNavConsuming = false;
                    wcTouchPairActive = false;
                }
            }
        }
        if (wcDispatchClassifiedTrackpad(event)) return true;
        if (wcDispatchTrackpadFingers(event)) return true;
        if (wcRejectPalm(event)) return true;
        if (event == null || !event.isFromSource(android.view.InputDevice.SOURCE_TOUCHSCREEN)
                || wcHasStylus(event)) return super.dispatchTouchEvent(event);
        int action = event.getActionMasked();
        boolean mustCancel = false, consume = false;
        synchronized (wcTouchPanLock) {
            if (action == android.view.MotionEvent.ACTION_DOWN && !wcTouchNavConsuming) {
                wcTouchNavSuppressInk = false;
                wcTouchPairActive = false;
                wcTouchMode = 0;
            }
            if (!wcTouchNavConsuming && action == android.view.MotionEvent.ACTION_POINTER_DOWN
                    && event.getPointerCount() == 2 && wcOnlyFingers(event)
                    && wcTouchOnCanvas((event.getX(0) + event.getX(1)) * .5f,
                                       (event.getY(0) + event.getY(1)) * .5f)) {
                wcTouchNavConsuming = true;
                wcTouchNavSuppressInk = true;
                wcTouchPairActive = false; wcTouchMode = 1; wcTouchZoom = 1f;
                wcTouchPinchEvidence = 0;
                wcTouchPreviousPanX = 0f;
                wcTouchPanX = wcTouchPanY = 0f;
                wcAccumulateTwoFingerEvent(event, -1);
                mustCancel = true;
            }
            if (wcTouchNavConsuming) {
                consume = true;
                if (event.getPointerCount() == 2 && wcOnlyFingers(event)
                        && action == android.view.MotionEvent.ACTION_MOVE) {
                    int history = event.getHistorySize();
                    for (int h = Math.max(0, history - 64); h < history; ++h)
                        wcAccumulateTwoFingerEvent(event, h);
                    wcAccumulateTwoFingerEvent(event, -1);
                }
                // Consume the remaining one-finger events until the full
                // gesture ends; otherwise the last finger selects text.
                if (action == android.view.MotionEvent.ACTION_POINTER_UP)
                    wcTouchPairActive = false;
                if (action == android.view.MotionEvent.ACTION_UP
                        || action == android.view.MotionEvent.ACTION_CANCEL) {
                    wcTouchNavConsuming = false;
                    wcTouchPairActive = false;
                    wcTouchMode = 0;
                }
            }
        }
        if (mustCancel) {
            // Explicitly terminate the first finger's pending upstream
            // selection/pen drag. Do not forward second-finger button presses.
            android.view.MotionEvent cancel = android.view.MotionEvent.obtain(event);
            try {
                cancel.setAction(android.view.MotionEvent.ACTION_CANCEL);
                super.dispatchTouchEvent(cancel);
            } finally {
                cancel.recycle();
            }
        }
        if (consume) return true;
        return super.dispatchTouchEvent(event);
    }

    public String wcTakeTwoFingerPan() {
        synchronized (wcTouchPanLock) {
            if (wcTouchPanX == 0f && wcTouchPanY == 0f && wcTouchZoom == 1f)
                return null;
            String result = wcTouchPanX + "," + wcTouchPanY + ","
                    + wcTouchPanCenterX + "," + wcTouchPanCenterY + "," + wcTouchZoom;
            wcTouchPanX = wcTouchPanY = 0f;
            wcTouchZoom = 1f;
            return result;
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
