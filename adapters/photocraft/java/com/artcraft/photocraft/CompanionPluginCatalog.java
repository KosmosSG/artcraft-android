package com.artcraft.photocraft;

import android.util.JsonReader;
import android.util.JsonToken;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.StringReader;
import java.nio.charset.CharacterCodingException;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Strict, read-only PhotoCraft Companion plugin manifest preflight for SAF import.
 *
 * This class never writes or extracts the .pcpl package, imports executable code,
 * evaluates Rhai, installs plugins, accesses the canvas, or downloads models.
 * The returned JSON is display-only metadata and is never an execution permit.
 */
public final class CompanionPluginCatalog {
    private CompanionPluginCatalog() {}

    private static final int MAX_ZIP_BYTES = 512 * 1024;
    private static final int MAX_ENTRIES = 64;
    private static final int MAX_MEMBER_BYTES = 128 * 1024;
    private static final int MAX_UNCOMPRESSED_BYTES = 1024 * 1024;
    private static final int MAX_COMPRESSION_RATIO = 250;
    private static final int MAX_NESTING = 32;
    private static final int MAX_JSON_TOKENS = 8192;

    private static final Set<String> ALLOWED_TYPES = new HashSet<>();
    static {
        ALLOWED_TYPES.add("no_code");
        ALLOWED_TYPES.add("native_ai");
        ALLOWED_TYPES.add("native_algorithm");
        ALLOWED_TYPES.add("interactive_ui");
        ALLOWED_TYPES.add("script");
        ALLOWED_TYPES.add("external_cli");
        ALLOWED_TYPES.add("dynamic_lib");
    }

    /** Limit even unknown-length streams supplied by Android document providers. */
    private static final class LimitedStream extends InputStream {
        private final InputStream upstream;
        private int count = 0;

        LimitedStream(InputStream upstream) { this.upstream = upstream; }

        @Override public int read() throws IOException {
            if (count >= MAX_ZIP_BYTES) {
                int next = upstream.read();
                if (next == -1) return -1;
                throw new IOException("Plugin ZIP exceeds 512 KiB");
            }
            int next = upstream.read();
            if (next != -1) count++;
            return next;
        }

        @Override public int read(byte[] b, int off, int len) throws IOException {
            if (len == 0) return 0;
            if (count >= MAX_ZIP_BYTES) {
                int next = upstream.read();
                if (next == -1) return -1;
                throw new IOException("Plugin ZIP exceeds 512 KiB");
            }
            // Reading at most one extra byte past the cap detects oversized streams.
            int got = upstream.read(b, off, Math.min(len, MAX_ZIP_BYTES - count + 1));
            if (got > 0) {
                count += got;
                if (count > MAX_ZIP_BYTES) throw new IOException("Plugin ZIP exceeds 512 KiB");
            }
            return got;
        }
    }

    private static void validatePath(String name) throws IOException {
        if (name == null || name.isEmpty() || name.length() > 240
                || name.startsWith("/") || name.indexOf('\\') >= 0
                || name.indexOf(':') >= 0) {
            throw new IOException("Unsafe plugin ZIP member path");
        }
        String[] components = name.split("/", -1);
        for (String component : components) {
            if (component.isEmpty() || component.equals(".") || component.equals("..")) {
                throw new IOException("Plugin ZIP contains traversal or directory member");
            }
        }
        for (int i = 0; i < name.length(); i++) {
            char c = name.charAt(i);
            if (c < 32 || c == 127) throw new IOException("Plugin ZIP contains control characters");
        }
        String leaf = components[components.length - 1];
        if (leaf.equals("LICENSE") || leaf.equals("LICENSE-MIT") || leaf.equals("NOTICE")) return;
        String lower = leaf.toLowerCase(Locale.ROOT);
        if (!(lower.endsWith(".json") || lower.endsWith(".svg") || lower.endsWith(".md")
                || lower.endsWith(".txt") || lower.endsWith(".rhai"))) {
            throw new IOException("Plugin ZIP contains executable, weight or unsupported file");
        }
    }

    private static String utf8(byte[] content) throws IOException {
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(content)).toString();
        } catch (CharacterCodingException error) {
            throw new IOException("Plugin manifest is not valid UTF-8", error);
        }
    }

    /** Detect nested duplicate JSON keys before JSONObject parsing. */
    private static void validateJson(JsonReader reader, int depth, int[] tokens) throws IOException {
        if (depth > MAX_NESTING || ++tokens[0] > MAX_JSON_TOKENS) {
            throw new IOException("Plugin JSON is too deeply nested or complex");
        }
        JsonToken type = reader.peek();
        switch (type) {
            case BEGIN_OBJECT: {
                reader.beginObject();
                Set<String> names = new HashSet<>();
                while (reader.hasNext()) {
                    String name = reader.nextName();
                    if (!names.add(name)) throw new IOException("Duplicate JSON key");
                    validateJson(reader, depth + 1, tokens);
                }
                reader.endObject();
                break;
            }
            case BEGIN_ARRAY:
                reader.beginArray();
                while (reader.hasNext()) validateJson(reader, depth + 1, tokens);
                reader.endArray();
                break;
            case STRING:
            case NUMBER:
                reader.nextString();
                break;
            case BOOLEAN:
                reader.nextBoolean();
                break;
            case NULL:
                reader.nextNull();
                break;
            default:
                throw new IOException("Invalid plugin manifest JSON token");
        }
    }

    private static String required(JSONObject object, String field, int maxLen) throws Exception {
        Object value = object.opt(field);
        if (!(value instanceof String)) throw new IOException("Missing plugin field: " + field);
        String text = (String) value;
        if (text.trim().isEmpty() || text.length() > maxLen) {
            throw new IOException("Invalid plugin field: " + field);
        }
        for (int i = 0; i < text.length(); i++) {
            if (text.charAt(i) < 32) throw new IOException("Control character in plugin field");
        }
        return text;
    }

    private static JSONObject parseManifest(byte[] raw) throws Exception {
        String json = utf8(raw);
        try (JsonReader reader = new JsonReader(new StringReader(json))) {
            reader.setLenient(false);
            validateJson(reader, 0, new int[] {0});
            if (reader.peek() != JsonToken.END_DOCUMENT) {
                throw new IOException("Trailing plugin manifest JSON");
            }
        }
        JSONObject object = new JSONObject(json);
        String id = required(object, "id", 128);
        String name = required(object, "name", 120);
        String version = required(object, "version", 48);
        String type = required(object, "plugin_type", 48);
        if (!id.matches("[A-Za-z0-9][A-Za-z0-9_.-]{2,127}")) {
            throw new IOException("Invalid plugin id");
        }
        if (!version.matches("[0-9]+(\\.[0-9]+){1,3}(-[0-9A-Za-z.-]+)?")) {
            throw new IOException("Invalid plugin version");
        }
        if (!ALLOWED_TYPES.contains(type)) throw new IOException("Unknown plugin type");
        for (String key : new String[] {"commands", "post_commands", "sub_actions", "models"}) {
            if (object.has(key)) {
                Object value = object.opt(key);
                if (!(value instanceof JSONArray) || ((JSONArray) value).length() > 64) {
                    throw new IOException("Invalid plugin collection: " + key);
                }
            }
        }
        JSONObject metadata = new JSONObject();
        metadata.put("id", id);
        metadata.put("name", name);
        metadata.put("version", version);
        metadata.put("plugin_type", type);
        metadata.put("catalog_status", "metadata_only");
        metadata.put("execution_enabled", false);
        metadata.put("installed", false);
        metadata.put("network_used", false);
        metadata.put("model_downloaded", false);
        metadata.put("declares_models", object.optJSONArray("models") != null
                && object.optJSONArray("models").length() > 0);
        return metadata;
    }

    /**
     * Inspect selected .pcpl bytes directly from ContentResolver, without
     * requesting a persistable URI grant or ever extracting the archive.
     */
    public static JSONObject inspect(InputStream source) throws Exception {
        if (source == null) throw new IOException("Provider did not open plugin file");
        int entries = 0;
        int total = 0;
        byte[] manifest = null;
        String manifestPath = null;
        Set<String> names = new HashSet<>();
        byte[] buffer = new byte[8192];
        try (ZipInputStream zip = new ZipInputStream(new LimitedStream(source))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (++entries > MAX_ENTRIES) throw new IOException("Too many plugin ZIP members");
                String path = entry.getName();
                validatePath(path);
                if (entry.isDirectory() || !names.add(path)) {
                    throw new IOException("Directory or duplicate plugin ZIP member");
                }
                if (entry.getMethod() != ZipEntry.STORED && entry.getMethod() != ZipEntry.DEFLATED) {
                    throw new IOException("Unsupported plugin ZIP compression");
                }
                boolean isManifest = path.endsWith("/plugin.json") || path.equals("plugin.json");
                if (isManifest && manifest != null) {
                    throw new IOException("Multiple plugin manifests");
                }
                int bytes = 0;
                ByteArrayOutputStream manifestBytes = isManifest ? new ByteArrayOutputStream() : null;
                int read;
                while ((read = zip.read(buffer)) != -1) {
                    bytes += read;
                    total += read;
                    if (bytes > MAX_MEMBER_BYTES || total > MAX_UNCOMPRESSED_BYTES) {
                        throw new IOException("Oversized plugin ZIP content");
                    }
                    if (manifestBytes != null) manifestBytes.write(buffer, 0, read);
                }
                long compressed = entry.getCompressedSize();
                if (compressed > 0 && bytes > compressed * MAX_COMPRESSION_RATIO) {
                    throw new IOException("Excessive plugin ZIP compression ratio");
                }
                if (isManifest) {
                    manifest = manifestBytes.toByteArray();
                    manifestPath = path;
                }
                zip.closeEntry();
            }
        }
        if (entries == 0 || manifest == null || manifestPath == null) {
            throw new IOException("Plugin ZIP must contain one plugin.json");
        }
        String root = manifestPath.substring(0, manifestPath.length() - "plugin.json".length());
        for (String path : names) {
            if (!path.startsWith(root)) {
                throw new IOException("Unrelated plugin ZIP roots");
            }
        }
        return parseManifest(manifest);
    }
}
