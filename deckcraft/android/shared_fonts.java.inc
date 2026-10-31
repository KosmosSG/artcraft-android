    // Read-only SAF tree; streamed private cache, never a 4 GiB in-memory allocation.
    private static final int DK_FONT_TREE = 0x5072;
    private static final long DK_SCAN_LIMIT = 4L * 1024 * 1024 * 1024;
    private static final long DK_FONT_LIMIT = 20L * 1024 * 1024;
    private final java.util.concurrent.atomic.AtomicBoolean dkScanBusy = new java.util.concurrent.atomic.AtomicBoolean();
    private final java.util.concurrent.ExecutorService dkFontWorker = java.util.concurrent.Executors.newSingleThreadExecutor();

    public void deckChooseFontFolder() {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                startActivityForResult(intent, DK_FONT_TREE);
            } catch (Exception e) { dkFontResult("Could not select shared fonts: " + e.getMessage()); }
        });
    }
    private boolean deckFontFolderResult(int code, int result, Intent data) {
        if (code != DK_FONT_TREE) return false;
        if (result != RESULT_OK || data == null || data.getData() == null) return true;
        try {
            Uri tree = data.getData();
            getContentResolver().takePersistableUriPermission(tree, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            getSharedPreferences("deckcraft_fonts", MODE_PRIVATE).edit().putString("tree", tree.toString()).apply();
            deckRefreshFonts();
        } catch (Exception e) { dkFontResult("Folder permission unavailable: " + e.getMessage()); }
        return true;
    }
    private void dkFontResult(String message) {
        try {
            JSONObject answer = new JSONObject();
            answer.put("id", 0); answer.put("kind", "deck-fonts"); answer.put("status", "ok");
            answer.put("message", message); results.offer(answer.toString());
        } catch (Exception e) { Log.e(TAG, "Font result failed", e); }
    }
    public void deckRefreshFonts() {
        if (!dkScanBusy.compareAndSet(false, true)) return;
        dkFontWorker.execute(() -> {
            int accepted = 0, skipped = 0, entries = 0;
            FontScanBudget budget = new FontScanBudget(); boolean limited = false;
            try {
                String encoded = getSharedPreferences("deckcraft_fonts", MODE_PRIVATE).getString("tree", null);
                if (encoded == null) throw new java.io.IOException("Choose a shared font folder first");
                Uri tree = Uri.parse(encoded);
                boolean allowed = false;
                for (android.content.UriPermission grant : getContentResolver().getPersistedUriPermissions())
                    if (tree.equals(grant.getUri()) && grant.isReadPermission()) allowed = true;
                if (!allowed) throw new java.io.IOException("Folder permission expired; select the folder again");
                File cache = new File(getFilesDir(), "DeckCraft/shared-fonts");
                if (!cache.isDirectory() && !cache.mkdirs()) throw new java.io.IOException("Cannot create font cache");
                long cacheBytes = 0;
                File[] cached = cache.listFiles();
                if (cached != null) for (File file : cached) {
                    if (file.getName().endsWith(".partial")) { file.delete(); continue; }
                    if (file.isFile()) cacheBytes += file.length();
                }
                java.util.ArrayDeque<String> pending = new java.util.ArrayDeque<>();
                java.util.HashSet<String> visited = new java.util.HashSet<>();
                pending.add(DocumentsContract.getTreeDocumentId(tree));
                while (!pending.isEmpty() && budget.used() < DK_SCAN_LIMIT && entries < 50000) {
                    String parent = pending.removeFirst();
                    if (!visited.add(parent)) continue;
                    Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parent);
                    try (Cursor cursor = getContentResolver().query(children, new String[]{
                            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                            DocumentsContract.Document.COLUMN_MIME_TYPE}, null, null, null)) {
                        if (cursor == null) { skipped++; continue; }
                        while (cursor.moveToNext()) {
                            if (++entries > 50000 || budget.used() >= DK_SCAN_LIMIT) { limited = true; break; }
                            String id = cursor.getString(0), name = cursor.getString(1), mime = cursor.getString(2);
                            if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                                if (pending.size() < 4096 && visited.size() < 4096) pending.addLast(id);
                                else limited = true;
                                continue;
                            }
                            String lower = name == null ? "" : name.toLowerCase(java.util.Locale.ROOT);
                            String ext = lower.endsWith(".ttf") ? ".ttf" : lower.endsWith(".otf") ? ".otf" : null;
                            if (ext == null) continue;
                            File temp = File.createTempFile("font-", ".partial", cache);
                            try {
                                java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
                                long count = 0; byte[] header = new byte[4]; int headerSize = 0;
                                try (InputStream in = getContentResolver().openInputStream(DocumentsContract.buildDocumentUriUsingTree(tree, id));
                                     FileOutputStream out = new FileOutputStream(temp)) {
                                    if (in == null) throw new java.io.IOException("No font stream");
                                    byte[] buffer = new byte[65536];
                                    while (true) {
                                        // At an exact boundary, stop rather than reading past the scan budget.
                                        if (budget.used() == DK_SCAN_LIMIT) { limited = true; throw new java.io.IOException("Scan limit reached"); }
                                        int n = in.read(buffer, 0, budget.nextRead(buffer.length));
                                        if (n < 0) break;
                                        if (n == 0) continue;
                                        budget.record(n); count += n;
                                        if (count > DK_FONT_LIMIT) throw new java.io.IOException("Font exceeds 20 MiB");
                                        for (int j = 0; j < n && headerSize < 4; j++) header[headerSize++] = buffer[j];
                                        digest.update(buffer, 0, n); out.write(buffer, 0, n);
                                    }
                                    out.getFD().sync();
                                }
                                boolean sfnt = header[0] == 0 && header[1] == 1 && header[2] == 0 && header[3] == 0;
                                boolean otto = header[0] == 'O' && header[1] == 'T' && header[2] == 'T' && header[3] == 'O';
                                if (count < 12 || !(sfnt || otto)) throw new java.io.IOException("Invalid font header");
                                StringBuilder hex = new StringBuilder();
                                for (byte b : digest.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
                                File dest = new File(cache, "font-" + hex + ext);
                                if (!dest.exists()) {
                                    if (count > DK_SCAN_LIMIT - cacheBytes) { limited = true; throw new java.io.IOException("Font cache full"); }
                                    if (!temp.renameTo(dest)) throw new java.io.IOException("Cannot commit font cache");
                                    cacheBytes += count;
                                }
                                accepted++;
                            } catch (Exception e) { skipped++; Log.w(TAG, "Skipped shared font", e); }
                            finally { temp.delete(); }
                        }
                    } catch (SecurityException e) { throw e; }
                    catch (Exception e) { skipped++; Log.w(TAG, "Unreadable font folder", e); }
                }
                limited |= !pending.isEmpty() || budget.used() >= DK_SCAN_LIMIT || entries >= 50000;
                dkFontResult("Shared fonts cached: " + accepted + "; skipped: " + skipped +
                    (limited ? ". Scan or cache limit reached; partial results retained." : ".") + " Refreshing font list…");
            } catch (Exception e) {
                dkFontResult("Shared font scan stopped: " + e.getMessage() + ". Previously imported fonts preserved.");
            } finally { dkScanBusy.set(false); }
        });
    }
