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
    private static final long MAX_FONT = 32L * 1024 * 1024;
    private static final int MAX_FONTS = 200;
    private static final int MAX_FOLDERS = 1000;
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
                    .putString(TREE_URI_KEY, uri.toString()).apply();
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
        return null;
    }

    private static void copyValidated(InputStream input, File target) throws Exception {
        if (input == null) throw new java.io.IOException("Font provider returned no data");
        long total = 0;
        try (InputStream from = input; OutputStream to = new FileOutputStream(target)) {
            byte[] block = new byte[64 * 1024];
            int n;
            while ((n = from.read(block)) != -1) {
                total += n;
                if (total > MAX_FONT) throw new java.io.IOException("Font exceeds 32 MB limit");
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
                    || "OTTO".equals(s) || "true".equals(s) || "typ1".equals(s);
            if (!sfnt) throw new java.io.IOException("File is not a valid TTF/OTF font");
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
            if (ext == null) throw new java.io.IOException("Choose a .ttf or .otf font");
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

    private void scanFontFolder(long id, Uri treeUri) {
        fontIo.execute(() -> {
            File staging = new File(files(), "pending-shared-fonts-" + UUID.randomUUID());
            try {
                boolean granted = false;
                for (android.content.UriPermission permission :
                        activity.getContentResolver().getPersistedUriPermissions()) {
                    if (treeUri.equals(permission.getUri()) && permission.isReadPermission()) {
                        granted = true; break;
                    }
                }
                if (!granted) throw new SecurityException("Shared folder access expired; select again");
                if (!staging.mkdirs()) throw new java.io.IOException("Cannot create font staging folder");
                int count = 0, skipped = 0, folders = 0;
                ArrayDeque<String> pending = new ArrayDeque<>();
                HashSet<String> seen = new HashSet<>();
                pending.add(DocumentsContract.getTreeDocumentId(treeUri));
                while (!pending.isEmpty() && count < MAX_FONTS && folders < MAX_FOLDERS) {
                    String parent = pending.removeFirst();
                    if (!seen.add(parent)) continue;
                    folders++;
                    Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parent);
                    try (Cursor cursor = activity.getContentResolver().query(children,
                            new String[] {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                    DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                                    DocumentsContract.Document.COLUMN_MIME_TYPE,
                                    DocumentsContract.Document.COLUMN_SIZE}, null, null, null)) {
                        if (cursor == null) { skipped++; continue; }
                        while (cursor.moveToNext() && count < MAX_FONTS) {
                            String documentId = cursor.getString(0);
                            String name = cursor.getString(1);
                            String mime = cursor.getString(2);
                            if (documentId == null || name == null) continue;
                            if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                                if (seen.size() + pending.size() < MAX_FOLDERS)
                                    pending.addLast(documentId);
                                continue;
                            }
                            String ext = extension(name);
                            if (ext == null) continue;
                            if (!cursor.isNull(3)) {
                                long bytes = cursor.getLong(3);
                                if (bytes <= 0 || bytes > MAX_FONT) { skipped++; continue; }
                            }
                            Uri document = DocumentsContract.buildDocumentUriUsingTree(treeUri, documentId);
                            String nameHash = UUID.nameUUIDFromBytes(
                                    documentId.getBytes(StandardCharsets.UTF_8)).toString();
                            File target = new File(staging, "font-" + nameHash + ext);
                            try {
                                copyValidated(activity.getContentResolver().openInputStream(document), target);
                                count++;
                            } catch (Exception badFont) {
                                skipped++;
                                Log.w(TAG, "Skipping unreadable shared font " + name, badFont);
                            }
                        }
                    } catch (SecurityException security) {
                        throw security;
                    } catch (Exception unreadableFolder) {
                        skipped++;
                        Log.w(TAG, "Could not scan shared font subfolder", unreadableFolder);
                    }
                }
                // A partial scan must never evict previously usable fonts.
                if (skipped > 0 || !pending.isEmpty() || count >= MAX_FONTS)
                    throw new java.io.IOException("Incomplete shared font scan; previous fonts preserved");
                File allFonts = fonts();
                if (!allFonts.isDirectory() && !allFonts.mkdirs())
                    throw new java.io.IOException("Cannot create Fonts folder");
                File shared = new File(allFonts, "Shared");
                File backup = new File(files(), "previous-shared-fonts-" + UUID.randomUUID());
                if (shared.exists() && !shared.renameTo(backup))
                    throw new java.io.IOException("Cannot preserve previous shared font cache");
                if (!staging.renameTo(shared)) {
                    if (backup.exists()) backup.renameTo(shared);
                    throw new java.io.IOException("Cannot activate new shared font cache");
                }
                deleteTree(backup);
                report(id, "font_folder", "ok",
                        "Shared fonts loaded: " + count + "; skipped: " + skipped, count);
            } catch (Exception error) {
                report(id, "font_folder", "error", error.toString(), 0);
            } finally {
                deleteTree(staging);
            }
        });
    }

    private static void deleteTree(File folder) {
        if (!folder.exists()) return;
        File[] children = folder.listFiles();
        if (children != null) for (File child : children) deleteTree(child);
        if (!folder.delete()) Log.w(TAG, "Could not clear temporary font file " + folder);
    }

    private static final String UPDATE_PREFS = "vectorcraft.android.updates";

    void showUpdateChannelSettings() {
        activity.runOnUiThread(() -> {
            boolean includePreview = activity.getSharedPreferences(UPDATE_PREFS, android.content.Context.MODE_PRIVATE)
                .getBoolean("include_preview_releases", true);
            new android.app.AlertDialog.Builder(activity)
                .setTitle("VectorCraft Update Channel")
                .setSingleChoiceItems(
                    new String[]{"Stable Releases Only", "Stable + Preview Releases"},
                    includePreview ? 1 : 0,
                    (dialog, selected) -> {
                        activity.getSharedPreferences(UPDATE_PREFS, android.content.Context.MODE_PRIVATE)
                            .edit().putBoolean("include_preview_releases", selected == 1).apply();
                        dialog.dismiss();
                    })
                .setNegativeButton("Cancel", null)
                .show();
        });
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
                boolean includePreview = activity.getSharedPreferences(UPDATE_PREFS, android.content.Context.MODE_PRIVATE)
                    .getBoolean("include_preview_releases", true);
                String latest = null, releaseUrl = null;
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
                        String filename = asset.optString("name", "").toLowerCase(Locale.ROOT);
                        if (filename.startsWith("vectorcraft-")
                                && filename.endsWith(".apk")) apkFound = true;
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
