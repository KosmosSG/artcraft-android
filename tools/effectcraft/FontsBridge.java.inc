    private static final long EC_FONT_MAX = 64L * 1024 * 1024;
    private static final long EC_SCAN_MAX = 2L * 1024 * 1024 * 1024;
    private static final int EC_SCAN_FILES = 5000, EC_SCAN_FOLDERS = 5000;
    private static boolean ecFontName(String name) {
        String lower = name == null ? "" : name.toLowerCase(java.util.Locale.ROOT);
        return lower.endsWith(".ttf") || lower.endsWith(".otf") || lower.endsWith(".ttc");
    }
    private static final int EC_FONT_PICK = 0x6541, EC_FONT_TREE = 0x6542;
    private final java.util.concurrent.ConcurrentLinkedQueue<String> ecFontPaths = new java.util.concurrent.ConcurrentLinkedQueue<>();
    private final java.util.concurrent.atomic.AtomicBoolean ecFontBusy = new java.util.concurrent.atomic.AtomicBoolean();
    private File ecFontDir() { return new File(getFilesDir(), "custom-fonts"); }
    public String ecPollFontPath() { return ecFontPaths.poll(); }
    public void ecFontMessage(String message) {
        runOnUiThread(() -> android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show());
    }
    public void ecInitialize() {
        io.execute(() -> {
            ecFontDir().mkdirs();
            File[] files = ecFontDir().listFiles();
            if (files != null) for (File f : files) {
                if (f.isFile() && ecFontName(f.getName()))
                    ecFontPaths.offer(f.getAbsolutePath());
            }
        });
        ecRefreshSharedFonts(false);
        if (ecStartupUpdatesEnabled()) ecCheckUpdates(false);
    }
    public void ecImportFont() {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                startActivityForResult(intent, EC_FONT_PICK);
            } catch (Exception e) { ecFontMessage("Cannot open font picker: " + e.getMessage()); }
        });
    }
    public void ecSelectSharedFonts() {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                startActivityForResult(intent, EC_FONT_TREE);
            } catch (Exception e) { ecFontMessage("Cannot open folder picker: " + e.getMessage()); }
        });
    }
    private boolean ecFontActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != EC_FONT_PICK && requestCode != EC_FONT_TREE) return false;
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return true;
        Uri uri = data.getData();
        if (requestCode == EC_FONT_PICK) {
            io.execute(() -> {
                try {
                    String name = null;
                    try (Cursor c = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                        if (c != null && c.moveToFirst()) name = c.getString(0);
                    }
                    ecCopyFont(uri, name, new long[]{0}, true);
                    ecFontMessage("Font stored; checking font faces…");
                } catch (Exception e) { ecFontMessage("Font import failed: " + e.getMessage()); }
            });
        } else {
            try {
                int flags = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
                if (flags == 0) throw new SecurityException("No read access was granted");
                getContentResolver().takePersistableUriPermission(uri, flags);
                getSharedPreferences("effectcraft_fonts", MODE_PRIVATE).edit().putString("tree", uri.toString()).apply();
                ecRefreshSharedFonts(true);
            } catch (Exception e) { ecFontMessage("Cannot retain shared folder: " + e.getMessage()); }
        }
        return true;
    }
    private void ecCopyFont(Uri uri, String name, long[] budget, boolean manual) throws Exception {
        String lower = name == null ? "" : name.toLowerCase(java.util.Locale.ROOT);
        if (!ecFontName(name)) throw new java.io.IOException("Choose a TTF, OTF or TTC font");
        File dir = ecFontDir();
        if (!dir.isDirectory() && !dir.mkdirs()) throw new java.io.IOException("Cannot create font storage");
        File staged = File.createTempFile("import-", ".pending", dir);
        try {
            java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
            long size = 0;
            try (InputStream input = getContentResolver().openInputStream(uri); FileOutputStream out = new FileOutputStream(staged)) {
                if (input == null) throw new java.io.IOException("Cannot read font");
                byte[] header = new byte[4];
                new java.io.DataInputStream(input).readFully(header);
                boolean valid = (header[0] == 0 && header[1] == 1 && header[2] == 0 && header[3] == 0)
                    || (header[0] == 'O' && header[1] == 'T' && header[2] == 'T' && header[3] == 'O')
                    || (header[0] == 't' && header[1] == 't' && header[2] == 'c' && header[3] == 'f');
                if (!valid) throw new java.io.IOException("Invalid TTF/OTF/TTC header");
                out.write(header); digest.update(header); size = 4; budget[0] += 4;
                byte[] buffer = new byte[32768]; int n;
                while ((n = input.read(buffer)) != -1) {
                    size += n; budget[0] += n;
                    if (size > EC_FONT_MAX) throw new java.io.IOException("Font exceeds 64 MiB");
                    if (budget[0] > EC_SCAN_MAX) throw new java.io.IOException("Refresh exceeds 2 GiB");
                    out.write(buffer, 0, n); digest.update(buffer, 0, n);
                }
                if (size < 12) throw new java.io.IOException("Truncated font");
                out.getFD().sync();
            }
            StringBuilder hash = new StringBuilder();
            for (byte b : digest.digest()) hash.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            File target = new File(dir, hash + (lower.endsWith(".otf") ? ".otf" : lower.endsWith(".ttc") ? ".ttc" : ".ttf"));
            if (!target.exists()) {
                try { java.nio.file.Files.move(staged.toPath(), target.toPath(), java.nio.file.StandardCopyOption.ATOMIC_MOVE); }
                catch (java.nio.file.AtomicMoveNotSupportedException error) {
                    java.nio.file.Files.move(staged.toPath(), target.toPath());
                }
            }
            ecFontPaths.offer((manual ? "manual|" : "") + target.getAbsolutePath());
        } finally { staged.delete(); }
    }
    public void ecRefreshFonts() { ecRefreshSharedFonts(true); }
    private void ecRefreshSharedFonts(boolean manual) {
        String saved = getSharedPreferences("effectcraft_fonts", MODE_PRIVATE).getString("tree", null);
        if (!ecFontBusy.compareAndSet(false, true)) { if (manual) ecFontMessage("Font refresh is already running"); return; }
        if (manual) ecFontMessage("Scanning fonts in the background…");
        io.execute(() -> {
            int detected = 0, skipped = 0, visited = 0;
            long[] budget = {0};
            boolean limited = false;
            try {
                // Read system files directly: never copy Android's font library.
                java.util.ArrayDeque<File> folders = new java.util.ArrayDeque<>();
                java.util.HashSet<String> diskSeen = new java.util.HashSet<>();
                folders.add(new File("/system/fonts"));
                folders.add(new File("/product/fonts"));
                folders.add(new File("/system/product/fonts"));
                while (!folders.isEmpty() && visited < EC_SCAN_FOLDERS && detected < EC_SCAN_FILES && budget[0] < EC_SCAN_MAX) {
                    File folder = folders.removeFirst();
                    if (!diskSeen.add(folder.getCanonicalPath())) continue;
                    visited++;
                    File[] files = folder.listFiles();
                    if (files == null) { skipped++; continue; }
                    for (File f : files) {
                        if (f.isDirectory()) {
                            if (visited + folders.size() < EC_SCAN_FOLDERS) folders.addLast(f);
                            else limited = true;
                        } else if (ecFontName(f.getName())) {
                            long size = f.length();
                            if (detected >= EC_SCAN_FILES) { limited = true; break; }
                            detected++;
                            if (!f.canRead() || size < 12 || size > EC_FONT_MAX) { skipped++; continue; }
                            if (size > EC_SCAN_MAX - budget[0]) { limited = true; break; }
                            budget[0] += size;
                            ecFontPaths.offer("system|" + f.getCanonicalPath());
                        }
                    }
                }
                if (!folders.isEmpty()) limited = true;
                if (saved != null) {
                    Uri tree = Uri.parse(saved);
                    boolean granted = false;
                    for (android.content.UriPermission p : getContentResolver().getPersistedUriPermissions())
                        if (tree.equals(p.getUri()) && p.isReadPermission()) granted = true;
                    if (!granted) throw new SecurityException("Folder permission expired; select it again");
                    java.util.ArrayDeque<String> pending = new java.util.ArrayDeque<>();
                    java.util.HashSet<String> seen = new java.util.HashSet<>();
                    pending.add(DocumentsContract.getTreeDocumentId(tree));
                    while (!pending.isEmpty() && visited < EC_SCAN_FOLDERS && detected < EC_SCAN_FILES && budget[0] < EC_SCAN_MAX) {
                        String parent = pending.removeFirst();
                        if (!seen.add(parent)) continue;
                        visited++;
                        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parent);
                        try (Cursor c = getContentResolver().query(children, new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE,
                                DocumentsContract.Document.COLUMN_SIZE}, null, null, null)) {
                            if (c == null) { skipped++; continue; }
                            while (c.moveToNext() && detected < EC_SCAN_FILES && budget[0] < EC_SCAN_MAX) {
                                String id = c.getString(0), name = c.getString(1), mime = c.getString(2);
                                if (id == null || name == null) continue;
                                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                                    if (pending.size() + visited < EC_SCAN_FOLDERS) pending.addLast(id);
                                    else limited = true;
                                    continue;
                                }
                                if (!ecFontName(name)) continue;
                                detected++; // Failed/rejected fonts also consume the file limit.
                                if (!c.isNull(3) && (c.getLong(3) < 12 || c.getLong(3) > EC_FONT_MAX)) { skipped++; continue; }
                                try { ecCopyFont(DocumentsContract.buildDocumentUriUsingTree(tree, id), name, budget, false); }
                                catch (Exception error) { skipped++; }
                            }
                        } catch (SecurityException error) { throw error; }
                        catch (Exception error) { skipped++; }
                    }
                    if (!pending.isEmpty() || detected >= EC_SCAN_FILES || budget[0] >= EC_SCAN_MAX) limited = true;
                }
                // Queue a barrier: Rust reports actual registration, not just detected files.
                ecFontPaths.offer("summary|Detected " + detected + "; skipped " + skipped + "; folders " + visited
                    + "; bytes " + budget[0] + (limited ? "; scan limit reached" : "")
                    + (saved == null ? "; no shared folder selected" : ""));
            } catch (Exception e) { ecFontPaths.offer("summary|Scan incomplete: " + e.getMessage() + ". Existing fonts kept"); }
            finally { ecFontBusy.set(false); }
        });
    }
