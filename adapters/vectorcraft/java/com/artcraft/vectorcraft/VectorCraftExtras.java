package com.artcraft.vectorcraft;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.HashSet;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Android-only, optional font library and read-only release checker.
 * Keeps the existing VectorCraft SAF Open/Save bridge and signing identity untouched.
 *
 * A shared ArtCraft-Fonts folder is never written to: a persisted read-only SAF grant
 * is used to refresh a bounded snapshot under this app's own Files/Fonts/Shared folder.
 * The VectorCraft text engine then rescans its existing app-font directory.
 */
final class VectorCraftExtras {
    static final int REQ_FONT_IMPORT = 0x5650;
    static final int REQ_FONT_FOLDER = 0x5651;
    private static final String TAG = "VectorCraftExtras";
    private static final String PREFS = "vectorcraft_font_library";
    private static final String TREE_URI_KEY = "shared_font_tree_uri";
    private static final long MAX_FONT = 64L * 1024 * 1024;
    private static final int MAX_FONTS = 5000; // Total supported font-library scan index.
    private static final int MAX_FOLDERS = 5000;
    private static final long MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024;
    // Avoid copying and immediately indexing multi-GiB font libraries in one
    // frame on a tablet. Continue deterministically on Refresh Shared Fonts.
    private static final int MAX_FONTS_PER_PASS = 128; // Keep storage-provider batches short.
    private static final long MAX_SCAN_BATCH_BYTES = 64L * 1024 * 1024; // Max copied per refresh.
    private static final String TREE_SCAN_OFFSET = "shared_font_next_offset";
    private static final String TREE_SCAN_BYTES = "shared_font_scanned_bytes"; // 64-bit cumulative 4 GiB allowance.
    private static final String TREE_SCAN_ADDED = "shared_font_total_added";
    private static final String RELEASES_API =
            "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100";
    private static final String RELEASE_PREFIX =
            "https://github.com/KosmosSG/artcraft-android/releases/tag/vectorcraft-v";
    private static final String TAG_PREFIX = "vectorcraft-v";
    private static final java.util.regex.Pattern VERSION =
            java.util.regex.Pattern.compile("[0-9]+\\.[0-9]+\\.[0-9]+-android\\.[1-9][0-9]*");

    private final VectorCraftActivity activity;
    private final ExecutorService fontIo = Executors.newSingleThreadExecutor();
    private final ExecutorService updateIo = Executors.newSingleThreadExecutor();
    private final ConcurrentLinkedQueue<String> updates = new ConcurrentLinkedQueue<>();
    private long pendingImport = -1;
    private long pendingFolder = -1;
    private static final String UPDATE_PREFS = "vectorcraft.android.updates";

    boolean includePreviewUpdates() {
        return activity.getSharedPreferences(UPDATE_PREFS, Activity.MODE_PRIVATE)
            .getBoolean("include_preview_releases", true);
    }

    void setIncludePreviewUpdates(boolean enabled) {
        activity.getSharedPreferences(UPDATE_PREFS, Activity.MODE_PRIVATE).edit()
            .putBoolean("include_preview_releases", enabled).apply();
    }


    VectorCraftExtras(VectorCraftActivity activity) {
        this.activity = activity;
    }

    private File files() { return new File(activity.vcFilesDir()); }
    private File fonts() { return new File(files(), "Fonts"); }

    private void report(long id, String kind, String status, String message, int count) {
        try {
            JSONObject result = new JSONObject();
            result.put("id", id);
            result.put("kind", kind);
            result.put("status", status);
            result.put("message", message);
            result.put("count", count);
            activity.vcOfferExtraResult(result.toString());
        } catch (Exception error) {
            Log.e(TAG, "Unable to queue picker response", error);
        }
    }

    void requestFontImport(long id) {
        activity.runOnUiThread(() -> {
            if (pendingImport != -1) {
                report(id, "font_import", "error", "A font picker is already open", 0);
                return;
            }
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*"); // Providers often lack font MIME declarations.
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                pendingImport = id;
                activity.startActivityForResult(intent, REQ_FONT_IMPORT);
            } catch (Exception error) {
                pendingImport = -1;
                report(id, "font_import", "error", error.toString(), 0);
            }
        });
    }

    void requestFontFolder(long id) {
        activity.runOnUiThread(() -> {
            if (pendingFolder != -1) {
                report(id, "font_folder", "error", "A folder picker is already open", 0);
                return;
            }
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                pendingFolder = id;
                activity.startActivityForResult(intent, REQ_FONT_FOLDER);
            } catch (Exception error) {
                pendingFolder = -1;
                report(id, "font_folder", "error", error.toString(), 0);
            }
        });
    }

    void refreshFontFolder(long id) {
        String stored = activity.getSharedPreferences(PREFS, Activity.MODE_PRIVATE)
                .getString(TREE_URI_KEY, null);
        if (stored == null) {
            report(id, "font_folder", "error", "Select Shared Font Folder first", 0);
            return;
        }
        scanFontFolder(id, Uri.parse(stored));
    }

    boolean handleActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != REQ_FONT_IMPORT && requestCode != REQ_FONT_FOLDER) return false;
        final String kind = requestCode == REQ_FONT_IMPORT ? "font_import" : "font_folder";
        final long id;
        if (requestCode == REQ_FONT_IMPORT) {
            id = pendingImport; pendingImport = -1;
        } else {
            id = pendingFolder; pendingFolder = -1;
        }
        if (id < 0) return true;
        if (resultCode != Activity.RESULT_OK || data == null || data.getData() == null) {
            report(id, kind, "cancel", "Selection cancelled", 0);
            return true;
        }
        Uri uri = data.getData();
        if (requestCode == REQ_FONT_IMPORT) {
            fontIo.execute(() -> importFont(id, uri));
            return true;
        }
        try {
            int grant = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
            if (grant == 0) throw new SecurityException("Read permission not granted");
            activity.getContentResolver().takePersistableUriPermission(uri, grant);
            activity.getSharedPreferences(PREFS, Activity.MODE_PRIVATE).edit()
                    .putString(TREE_URI_KEY, uri.toString())
                    .putInt(TREE_SCAN_OFFSET, 0)
                    .putLong(TREE_SCAN_BYTES, 0L)
                    .putInt(TREE_SCAN_ADDED, 0).apply();
            clearScanState(); // Explicit folder selection starts a new BFS scan.
            scanFontFolder(id, uri);
        } catch (Exception error) {
            report(id, kind, "error", error.toString(), 0);
        }
        return true;
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = activity.getContentResolver().query(uri,
                new String[] {OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) return cursor.getString(0);
        } catch (Exception error) {
            Log.w(TAG, "Font display name unavailable", error);
        }
        return "";
    }

    private static String extension(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".ttf")) return ".ttf";
        if (lower.endsWith(".otf")) return ".otf";
        if (lower.endsWith(".ttc")) return ".ttc";
        return null;
    }

    private static void copyValidated(InputStream input, File target) throws Exception {
        copyValidated(input, target, new long[]{0});
    }

    private static void copyValidated(InputStream input, File target, long[] budget) throws Exception {
        if (input == null) throw new java.io.IOException("Font provider returned no data");
        long total = 0;
        try (InputStream from = input; OutputStream to = new FileOutputStream(target)) {
            byte[] block = new byte[64 * 1024];
            int n;
            while ((n = from.read(block)) != -1) {
                total += n;
                budget[0] += n;
                if (budget.length > 1) {
                    budget[1] += n;
                    if (budget[1] > MAX_SCAN_BYTES)
                        throw new java.io.IOException("Scan reached cumulative 4 GiB limit");
                }
                if (budget[0] > MAX_SCAN_BATCH_BYTES) throw new java.io.IOException("Safe font-scan batch budget reached");
                if (total > MAX_FONT) throw new java.io.IOException("Font exceeds 64 MiB limit");
                to.write(block, 0, n);
            }
        } catch (Exception error) {
            target.delete();
            throw error;
        }
        if (total < 4) {
            target.delete();
            throw new java.io.IOException("Empty or truncated font");
        }
        try (InputStream in = new FileInputStream(target)) {
            byte[] signature = new byte[4];
            if (in.read(signature) != 4) throw new java.io.IOException("Invalid font header");
            String s = new String(signature, StandardCharsets.US_ASCII);
            boolean sfnt = (signature[0] == 0 && signature[1] == 1
                    && signature[2] == 0 && signature[3] == 0)
                    || "OTTO".equals(s) || "true".equals(s) || "typ1".equals(s) || "ttcf".equals(s);
            if (!sfnt) throw new java.io.IOException("File is not a valid TTF/OTF/TTC font");
        } catch (Exception error) {
            target.delete();
            throw error;
        }
    }

    private static String fontDigest(File file) throws Exception {
        java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
        try (InputStream input = new FileInputStream(file)) {
            byte[] block = new byte[65536];
            int count;
            while ((count = input.read(block)) != -1) digest.update(block, 0, count);
        }
        StringBuilder hex = new StringBuilder();
        for (byte b : digest.digest()) hex.append(String.format(Locale.ROOT, "%02x", b & 255));
        return hex.toString();
    }

    // Also recognizes legacy UUID filenames without renaming or deleting existing fonts.
    private static boolean containsFont(File folder, String digest) throws Exception {
        File[] children = folder.listFiles();
        if (children == null) return false;
        for (File child : children) {
            if (child.isDirectory()) {
                if (containsFont(child, digest)) return true;
            } else if (extension(child.getName()) != null && fontDigest(child).equals(digest)) {
                return true;
            }
        }
        return false;
    }

    private void importFont(long id, Uri uri) {
        File target = null;
        try {
            String ext = extension(displayName(uri));
            if (ext == null) throw new java.io.IOException("Choose a .ttf, .otf or .ttc font");
            File dest = new File(fonts(), "Imported");
            if (!dest.isDirectory() && !dest.mkdirs())
                throw new java.io.IOException("Cannot create imported font folder");
            target = new File(files(), "pending-font-" + UUID.randomUUID());
            copyValidated(activity.getContentResolver().openInputStream(uri), target);
            String digest = fontDigest(target);
            if (containsFont(fonts(), digest)) {
                report(id, "font_import", "ok", "This font is already available", 0);
                return;
            }
            if (!target.renameTo(new File(dest, "font-" + digest + ext)))
                throw new java.io.IOException("Cannot store imported font");
            report(id, "font_import", "ok", "Font imported to private Fonts/Imported folder", 1);
        } catch (Exception error) {
            report(id, "font_import", "error", error.toString(), 0);
        } finally {
            if (target != null) target.delete();
        }
    }


    // A durable breadth-first work queue, not an offset into a repeated recursive
    // walk. Every document ID is enqueued at most once, and folder cursor order
    // changes do not affect subsequent batches or resumed scans.
    private static final int FONT_SCAN_STATE_VERSION = 1;
    private static final int MAX_WORK_ITEMS = MAX_FONTS + MAX_FOLDERS;
    private static final int MAX_DIRECTORIES_PER_PASS = 32;
    private static final String SCAN_STATE_NAME = "shared-font-scan-v1.bin";

    private static final class ScanEntry {
        final String documentId;
        final String name;
        final boolean directory;
        final long reportedSize;
        ScanEntry(String id, String name, boolean directory, long size) {
            this.documentId = id;
            this.name = name;
            this.directory = directory;
            this.reportedSize = size;
        }
    }

    private static final class ScanProgress {
        final String uri;
        final ArrayDeque<ScanEntry> queue = new ArrayDeque<>();
        final HashSet<String> scheduled = new HashSet<>();
        int attempted, folders, added, skipped;
        long bytes;
        boolean truncated;
        ScanProgress(String uri, String rootId) {
            this.uri = uri;
            queue.addLast(new ScanEntry(rootId, "", true, -1L));
            scheduled.add("D:" + rootId);
        }
    }

    private File scanStateFile() { return new File(files(), SCAN_STATE_NAME); }

    private void clearScanState() {
        File state = scanStateFile();
        if (state.exists() && !state.delete()) Log.w(TAG, "Could not reset font scan checkpoint");
    }

    private ScanProgress loadScanState(Uri treeUri) throws Exception {
        File state = scanStateFile();
        String uri = treeUri.toString();
        if (!state.isFile()) return new ScanProgress(uri, DocumentsContract.getTreeDocumentId(treeUri));
        try (java.io.DataInputStream input = new java.io.DataInputStream(
                new java.io.BufferedInputStream(new FileInputStream(state)))) {
            if (input.readInt() != FONT_SCAN_STATE_VERSION || !uri.equals(input.readUTF())) {
                return new ScanProgress(uri, DocumentsContract.getTreeDocumentId(treeUri));
            }
            ScanProgress saved = new ScanProgress(uri, DocumentsContract.getTreeDocumentId(treeUri));
            saved.queue.clear();
            saved.scheduled.clear();
            saved.attempted = input.readInt();
            saved.folders = input.readInt();
            saved.added = input.readInt();
            saved.skipped = input.readInt();
            saved.bytes = input.readLong();
            saved.truncated = input.readBoolean();
            int n = input.readInt();
            if (n < 0 || n > MAX_WORK_ITEMS) throw new java.io.IOException("Invalid queue length");
            for (int i = 0; i < n; i++) {
                saved.queue.addLast(new ScanEntry(input.readUTF(), input.readUTF(), input.readBoolean(), input.readLong()));
            }
            n = input.readInt();
            if (n < 0 || n > MAX_WORK_ITEMS * 2) throw new java.io.IOException("Invalid seen-set length");
            for (int i = 0; i < n; i++) saved.scheduled.add(input.readUTF());
            return saved;
        } catch (java.io.IOException corrupted) {
            Log.w(TAG, "Unusable shared font checkpoint; starting a new scan", corrupted);
            return new ScanProgress(uri, DocumentsContract.getTreeDocumentId(treeUri));
        }
    }

    private void saveScanState(ScanProgress progress) throws Exception {
        File state = scanStateFile();
        File temp = new File(files(), SCAN_STATE_NAME + ".tmp");
        try (java.io.DataOutputStream output = new java.io.DataOutputStream(
                new java.io.BufferedOutputStream(new FileOutputStream(temp)))) {
            output.writeInt(FONT_SCAN_STATE_VERSION);
            output.writeUTF(progress.uri);
            output.writeInt(progress.attempted);
            output.writeInt(progress.folders);
            output.writeInt(progress.added);
            output.writeInt(progress.skipped);
            output.writeLong(progress.bytes);
            output.writeBoolean(progress.truncated);
            output.writeInt(progress.queue.size());
            for (ScanEntry e : progress.queue) {
                output.writeUTF(e.documentId);
                output.writeUTF(e.name);
                output.writeBoolean(e.directory);
                output.writeLong(e.reportedSize);
            }
            output.writeInt(progress.scheduled.size());
            for (String seen : progress.scheduled) output.writeUTF(seen);
        }
        try {
            java.nio.file.Files.move(temp.toPath(), state.toPath(),
                    java.nio.file.StandardCopyOption.REPLACE_EXISTING,
                    java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (java.nio.file.AtomicMoveNotSupportedException unsupported) {
            java.nio.file.Files.move(temp.toPath(), state.toPath(),
                    java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private void scanFontFolder(long id, Uri treeUri) {
        // Single executor serializes all SAF operations and all checkpoint writes.
        fontIo.execute(() -> scanFontBatch(id, treeUri));
    }

    private void scanFontBatch(long id, Uri treeUri) {
        File staging = new File(files(), "pending-shared-fonts-" + UUID.randomUUID());
        try {
            boolean granted = false;
            for (android.content.UriPermission permission :
                    activity.getContentResolver().getPersistedUriPermissions()) {
                if (treeUri.equals(permission.getUri()) && permission.isReadPermission()) {
                    granted = true;
                    break;
                }
            }
            if (!granted) throw new SecurityException("Shared folder access expired; select again");
            if (!staging.mkdirs()) throw new java.io.IOException("Cannot create font staging folder");

            ScanProgress p = loadScanState(treeUri);
            long[] budget = {0L, p.bytes};
            int filesThisPass = 0, foldersThisPass = 0;
            while (!p.queue.isEmpty() && filesThisPass < MAX_FONTS_PER_PASS
                    && foldersThisPass < MAX_DIRECTORIES_PER_PASS
                    && p.attempted < MAX_FONTS && p.folders < MAX_FOLDERS
                    && budget[0] < MAX_SCAN_BATCH_BYTES && budget[1] < MAX_SCAN_BYTES) {
                ScanEntry entry = p.queue.removeFirst();
                if (entry.directory) {
                    foldersThisPass++;
                    p.folders++;
                    Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, entry.documentId);
                    try (Cursor cursor = activity.getContentResolver().query(children,
                            new String[] {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                    DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                                    DocumentsContract.Document.COLUMN_MIME_TYPE,
                                    DocumentsContract.Document.COLUMN_SIZE}, null, null, null)) {
                        if (cursor == null) { p.skipped++; continue; }
                        while (cursor.moveToNext()) {
                            String documentId = cursor.getString(0);
                            String name = cursor.getString(1);
                            String mime = cursor.getString(2);
                            if (documentId == null || name == null) continue;
                            boolean directory = DocumentsContract.Document.MIME_TYPE_DIR.equals(mime);
                            if (!directory && extension(name) == null) continue;
                            String key = (directory ? "D:" : "F:") + documentId;
                            if (p.scheduled.contains(key)) continue;
                            if (p.scheduled.size() >= MAX_WORK_ITEMS) {
                                p.truncated = true;
                                continue;
                            }
                            p.scheduled.add(key);
                            long size = cursor.isNull(3) ? -1L : cursor.getLong(3);
                            p.queue.addLast(new ScanEntry(documentId, name, directory, size));
                        }
                    } catch (SecurityException security) {
                        throw security;
                    } catch (Exception badFolder) {
                        p.skipped++;
                        Log.w(TAG, "Unable to enumerate shared font folder " + entry.documentId, badFolder);
                    }
                    continue;
                }

                // A known-size file that cannot fit this pass is put back at
                // the head and retried with a fresh batch byte allowance.
                if (entry.reportedSize > 0
                        && entry.reportedSize <= MAX_FONT
                        && entry.reportedSize > MAX_SCAN_BATCH_BYTES - budget[0]) {
                    p.queue.addFirst(entry);
                    break;
                }
                filesThisPass++;
                p.attempted++;
                if (entry.reportedSize > MAX_FONT
                        || entry.reportedSize > MAX_SCAN_BYTES - budget[1]) {
                    p.skipped++;
                    continue;
                }
                Uri document = DocumentsContract.buildDocumentUriUsingTree(treeUri, entry.documentId);
                String nameHash = UUID.nameUUIDFromBytes(
                        entry.documentId.getBytes(StandardCharsets.UTF_8)).toString();
                File target = new File(staging, "font-" + nameHash + extension(entry.name));
                long before = budget[0];
                try {
                    // Unknown-size SAF files (0/-1/null) are validated from
                    // their actual TTF/OTF/TTC header while streaming.
                    copyValidated(activity.getContentResolver().openInputStream(document), target, budget);
                } catch (Exception unreadableFont) {
                    String why = String.valueOf(unreadableFont.getMessage());
                    if (why.contains("Safe font-scan batch budget reached")
                            && before > 0 && entry.reportedSize <= 0) {
                        p.queue.addFirst(entry);
                        p.attempted--;
                        filesThisPass--;
                        break;
                    }
                    p.skipped++;
                    Log.w(TAG, "Skipped unreadable font " + entry.name, unreadableFont);
                }
            }
            p.bytes = budget[1];

            // Merge into the previously approved private font cache; never
            // evict older fonts because a partial SAF scan is incomplete.
            File shared = new File(fonts(), "Shared");
            if (!shared.isDirectory() && !shared.mkdirs())
                throw new java.io.IOException("Cannot create Shared font cache");
            File[] ready = staging.listFiles();
            if (ready != null) for (File file : ready) {
                String ext = extension(file.getName());
                if (ext == null) continue;
                File target = new File(shared, "font-" + fontDigest(file) + ext);
                if (target.exists()) continue;
                try {
                    try {
                        java.nio.file.Files.move(file.toPath(), target.toPath(),
                                java.nio.file.StandardCopyOption.ATOMIC_MOVE);
                    } catch (java.nio.file.AtomicMoveNotSupportedException unsupported) {
                        java.nio.file.Files.move(file.toPath(), target.toPath());
                    }
                    p.added++;
                } catch (Exception error) {
                    p.skipped++;
                    Log.w(TAG, "Cannot cache shared font " + file.getName(), error);
                }
            }

            boolean reachedLimit = p.attempted >= MAX_FONTS || p.folders >= MAX_FOLDERS
                    || p.bytes >= MAX_SCAN_BYTES;
            boolean continueScan = !p.queue.isEmpty() && !reachedLimit;
            if (continueScan) saveScanState(p);
            else clearScanState();

            String summary = "Indexed " + p.attempted + " / 5000 font files; "
                    + p.folders + " folders; cached " + p.added + " new fonts; skipped " + p.skipped
                    + "; read " + (p.bytes / (1024 * 1024)) + " / 4096 MiB"
                    + (p.truncated ? "; work queue capped at 10,000 entries" : "")
                    + (reachedLimit ? "; configured scan limit reached" : "");
            if (continueScan) {
                report(id, "font_folder", "progress", summary + "; continuing in background…", 0);
                // Automatic bounded chaining: no user refresh is required.
                scanFontFolder(id, treeUri);
            } else {
                report(id, "font_folder", "ok", summary + "; font catalog updating.", p.added);
            }
        } catch (Exception error) {
            report(id, "font_folder", "error", error.toString(), 0);
        } finally {
            deleteTree(staging);
        }
    }

    private static void deleteTree(File folder) {
        if (!folder.exists()) return;
        File[] children = folder.listFiles();
        if (children != null) for (File child : children) deleteTree(child);
        if (!folder.delete()) Log.w(TAG, "Could not clear temporary font file " + folder);
    }

    void checkForUpdates() {
        updateIo.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(RELEASES_API).openConnection();
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(8000);
                connection.setRequestMethod("GET");
                connection.setRequestProperty("Accept", "application/vnd.github+json");
                connection.setRequestProperty("User-Agent", "VectorCraft-Android-Updater");
                if (connection.getResponseCode() != 200)
                    throw new java.io.IOException("GitHub API error HTTP " + connection.getResponseCode());
                byte[] data;
                try (InputStream in = connection.getInputStream();
                     ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                    byte[] block = new byte[8192];
                    int n;
                    while ((n = in.read(block)) != -1) {
                        if (buffer.size() + n > 1024 * 1024)
                            throw new java.io.IOException("Response too large");
                        buffer.write(block, 0, n);
                    }
                    data = buffer.toByteArray();
                }
                JSONArray releases = new JSONArray(new String(data, StandardCharsets.UTF_8));
                String installed = activity.getPackageManager()
                        .getPackageInfo(activity.getPackageName(), 0).versionName;
                if (installed == null) installed = "0.0.0";
                String latest = null, releaseUrl = null;
                final boolean includePreview = includePreviewUpdates();
                if (releases.length() >= 100)
                    throw new java.io.IOException("Release list incomplete; check GitHub manually");
                for (int i = 0; i < releases.length(); i++) {
                    JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft")
                            || (!includePreview && release.optBoolean("prerelease"))) continue;
                    String tag = release.optString("tag_name", "");
                    if (!tag.startsWith(TAG_PREFIX)) continue;
                    String version = tag.substring(TAG_PREFIX.length());
                    if (!VERSION.matcher(version).matches()) continue;
                    JSONArray assets = release.optJSONArray("assets");
                    boolean apkFound = false;
                    if (assets != null) for (int j = 0; j < assets.length(); j++) {
                        JSONObject asset = assets.optJSONObject(j);
                        if (asset == null) continue;
                        // Check exact same-app ARM64 asset, not an unrelated
                        // test APK or an incomplete upload.
                        String filename = asset.optString("name", "");
                        if (("VectorCraft-v" + version + "-arm64-v8a.apk").equals(filename)
                                && "uploaded".equals(asset.optString("state", ""))
                                && asset.optLong("size", 0L) > 0) apkFound = true;
                    }
                    if (!apkFound) continue;
                    String url = release.optString("html_url", "");
                    if (!url.startsWith(RELEASE_PREFIX)) continue;
                    if (latest == null || compareVersions(version, latest) > 0) {
                        latest = version;
                        releaseUrl = url;
                    }
                }
                JSONObject result = new JSONObject();
                result.put("status", "ok");
                result.put("installed_version", installed);
                result.put("channel", includePreview ? "stable_and_preview" : "stable");
                if (latest == null) {
                    result.put("state", "no_release");
                    result.put("message", "No published VectorCraft Android APK available yet");
                } else {
                    result.put("latest_version", latest);
                    result.put("url", releaseUrl);
                    result.put("state", compareVersions(latest, installed) > 0
                            ? "update_available" : "up_to_date");
                }
                updates.offer(result.toString());
            } catch (Exception error) {
                Log.w(TAG, "VectorCraft update check failed", error);
                try {
                    JSONObject result = new JSONObject();
                    result.put("status", "error");
                    result.put("message", error.toString());
                    updates.offer(result.toString());
                } catch (Exception ignored) { }
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    String pollUpdate() { return updates.poll(); }

    void openRelease(String url) {
        if (url == null || !url.startsWith(RELEASE_PREFIX)) return;
        String version = url.substring(RELEASE_PREFIX.length());
        if (!VERSION.matcher(version).matches()) return;
        activity.runOnUiThread(() -> {
            try {
                activity.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            } catch (Exception error) {
                Log.w(TAG, "Cannot open official release page", error);
            }
        });
    }

    private static int compareVersions(String a, String b) {
        int[] aa = versionParts(a), bb = versionParts(b);
        for (int i = 0; i < 4; i++) {
            if (aa[i] != bb[i]) return Integer.compare(aa[i], bb[i]);
        }
        return 0;
    }

    private static int[] versionParts(String input) {
        int[] parts = new int[4];
        String[] words = input.replace("-android.", ".").split("\\.");
        for (int i = 0; i < Math.min(4, words.length); i++) {
            try { parts[i] = Integer.parseInt(words[i]); }
            catch (Exception ignored) { parts[i] = 0; }
        }
        return parts;
    }
}
