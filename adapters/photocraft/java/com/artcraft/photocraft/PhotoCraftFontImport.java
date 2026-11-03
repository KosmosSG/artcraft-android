package com.artcraft.photocraft;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.UUID;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * SAF font import ported independently from the owner-tested PhotoCraft Android workflow.
 * Single/multiple TTF/OTF documents or recursively selected font folders, limited to 5,000
 * files, 32 MiB per font and 4 GiB copied to app-private DISK (not RAM) per request.
 * No all-files permission or storage root access is needed.
 */
final class PhotoCraftFontImport {
    static final int REQ_FILES = 0x5046;
    static final int REQ_FOLDER = 0x5045;
    private static final String TAG = "PhotoCraftFontImport";
    private static final long MAX_FILE = 32L * 1024 * 1024;
    private static final long MAX_BYTES = 4L * 1024 * 1024 * 1024;
    private static final int MAX_FILES = 5000;
    private static final int MAX_FOLDERS = 1000;
    private final PhotoCraftActivity activity;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final ConcurrentLinkedQueue<String> queue = new ConcurrentLinkedQueue<>();

    PhotoCraftFontImport(PhotoCraftActivity activity) { this.activity = activity; }

    String poll() { return queue.poll(); }

    void request(boolean folder) {
        activity.runOnUiThread(() -> {
            try {
                Intent intent = new Intent(folder ? Intent.ACTION_OPEN_DOCUMENT_TREE : Intent.ACTION_OPEN_DOCUMENT);
                if (!folder) {
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("*/*");
                    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                }
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                activity.startActivityForResult(intent, folder ? REQ_FOLDER : REQ_FILES);
            } catch (Exception e) {
                event("error", e.getMessage(), null, 0, false);
            }
        });
    }

    boolean result(int requestCode, int resultCode, Intent data) {
        if (requestCode != REQ_FILES && requestCode != REQ_FOLDER) return false;
        if (resultCode != Activity.RESULT_OK || data == null) {
            event("cancel", "Import cancelled", null, 0, false);
            return true;
        }
        worker.execute(() -> {
            JSONArray paths = new JSONArray();
            long[] copied = {0};
            boolean[] limit = {false};
            try {
                File cache = new File(activity.pcFilesDir(), "PhotoCraft/fonts-imported");
                if (!cache.isDirectory() && !cache.mkdirs()) throw new Exception("Could not create imported fonts folder");
                if (requestCode == REQ_FOLDER) {
                    Uri tree = data.getData();
                    if (tree == null) throw new Exception("No font folder selected");
                    scanTree(tree, cache, paths, copied, limit);
                } else {
                    ClipData clip = data.getClipData();
                    if (clip != null) {
                        for (int i = 0; i < clip.getItemCount() && paths.length() < MAX_FILES; ++i) {
                            Uri uri = clip.getItemAt(i).getUri();
                            if (uri != null) copyOne(uri, displayName(uri), size(uri), cache, paths, copied, limit);
                        }
                    } else if (data.getData() != null) {
                        Uri uri = data.getData();
                        copyOne(uri, displayName(uri), size(uri), cache, paths, copied, limit);
                    }
                }
                event("ok", "Imported " + paths.length() + " font file(s)", paths, copied[0], limit[0]);
            } catch (Exception e) {
                Log.w(TAG, "Font import failed", e);
                event("error", e.getMessage(), null, copied[0], limit[0]);
            }
        });
        return true;
    }

    private void scanTree(Uri tree, File cache, JSONArray paths, long[] copied, boolean[] limit) throws Exception {
        ContentResolver resolver = activity.getContentResolver();
        ArrayDeque<String> pending = new ArrayDeque<>();
        pending.add(DocumentsContract.getTreeDocumentId(tree));
        int visited = 0;
        while (!pending.isEmpty() && visited < MAX_FOLDERS && paths.length() < MAX_FILES && copied[0] < MAX_BYTES) {
            String parentId = pending.removeFirst();
            visited++;
            Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId);
            String[] cols = {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                             DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                             DocumentsContract.Document.COLUMN_MIME_TYPE,
                             DocumentsContract.Document.COLUMN_SIZE};
            try (Cursor cursor = resolver.query(children, cols, null, null, null)) {
                if (cursor == null) continue;
                while (cursor.moveToNext()) {
                    String id = cursor.getString(0);
                    String name = cursor.getString(1);
                    String mime = cursor.getString(2);
                    long len = cursor.isNull(3) ? -1 : cursor.getLong(3);
                    if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                        if (visited + pending.size() < MAX_FOLDERS) pending.addLast(id);
                        else limit[0] = true;
                        continue;
                    }
                    if (paths.length() >= MAX_FILES) { limit[0] = true; break; }
                    Uri file = DocumentsContract.buildDocumentUriUsingTree(tree, id);
                    copyOne(file, name, len, cache, paths, copied, limit);
                }
            }
        }
        if (!pending.isEmpty() || visited >= MAX_FOLDERS || paths.length() >= MAX_FILES) limit[0] = true;
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = activity.getContentResolver().query(uri,
                new String[] {android.provider.OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) return cursor.getString(0);
        } catch (Exception ignored) { }
        return uri.getLastPathSegment();
    }

    private long size(Uri uri) {
        try (Cursor cursor = activity.getContentResolver().query(uri,
                new String[] {android.provider.OpenableColumns.SIZE}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst() && !cursor.isNull(0)) return cursor.getLong(0);
        } catch (Exception ignored) { }
        return -1;
    }

    private void copyOne(Uri uri, String name, long length, File cache,
                         JSONArray paths, long[] copied, boolean[] limit) throws Exception {
        if (name == null) return;
        String lower = name.toLowerCase(java.util.Locale.ROOT);
        String ext = lower.endsWith(".ttf") ? ".ttf" : lower.endsWith(".otf") ? ".otf" : null;
        if (ext == null || length == 0 || length > MAX_FILE) return;
        if (length > 0 && length > MAX_BYTES - copied[0]) { limit[0] = true; return; }
        String identity = UUID.nameUUIDFromBytes(uri.toString().getBytes(StandardCharsets.UTF_8)).toString();
        File target = new File(cache, "font-" + identity + ext);
        File staging = new File(cache, "font-" + identity + ext + ".tmp");
        long total = 0;
        try (InputStream input = activity.getContentResolver().openInputStream(uri)) {
            if (input == null) throw new Exception("Could not open selected font");
            try (OutputStream output = new FileOutputStream(staging)) {
                byte[] buffer = new byte[16 * 1024];
                for (int n; (n = input.read(buffer)) != -1;) {
                    if (n == 0) continue;
                    total += n;
                    if (total > MAX_FILE || total > MAX_BYTES - copied[0]) {
                        limit[0] = true;
                        throw new Exception("Font import limit exceeded");
                    }
                    output.write(buffer, 0, n);
                }
            }
            if (total < 4) return;
            if (target.exists() && !target.delete()) throw new Exception("Old font cache file cannot be replaced");
            if (!staging.renameTo(target)) throw new Exception("Could not save imported font");
            paths.put(target.getAbsolutePath());
            copied[0] += total;
        } finally {
            if (staging.exists()) staging.delete();
        }
    }

    private void event(String status, String message, JSONArray paths, long bytes, boolean limit) {
        try {
            JSONObject out = new JSONObject();
            out.put("status", status);
            out.put("kind", "font_import");
            out.put("message", message == null ? "" : message);
            out.put("paths", paths == null ? new JSONArray() : paths);
            out.put("scanned_bytes", bytes);
            out.put("scan_limit_reached", limit);
            queue.offer(out.toString());
        } catch (Exception e) { Log.w(TAG, "Failed to send font import result", e); }
    }
}
