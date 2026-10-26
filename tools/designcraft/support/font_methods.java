    /** Ask Android for read-only access to a user-selected shared font directory. */
    public void dcRequestFontFolder(long id) {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                requestIds.put(REQ_FONT_FOLDER, id);
                startActivityForResult(intent, REQ_FONT_FOLDER);
            } catch (Exception error) {
                requestIds.remove(REQ_FONT_FOLDER);
                enqueueError(id, "font_folder", error.toString());
            }
        });
    }

    /** Refresh the previously selected folder, without prompting again. */
    public void dcRefreshFontFolder(long id) {
        String stored = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(FONT_FOLDER_PREF, null);
        if (stored == null) {
            enqueueError(id, "font_folder", "Select Shared Font Folder first");
            return;
        }
        scanFontFolder(id, Uri.parse(stored));
    }

    private void scanFontFolder(long id, Uri treeUri) {
        io.execute(() -> {
            try {
                boolean granted = false;
                for (android.content.UriPermission permission :
                        getContentResolver().getPersistedUriPermissions()) {
                    if (treeUri.equals(permission.getUri()) && permission.isReadPermission()) {
                        granted = true;
                        break;
                    }
                }
                if (!granted) throw new SecurityException("Folder access expired; select the folder again");

                File cache = new File(getFilesDir(), "home/.local/share/fonts/shared");
                if (!cache.isDirectory() && !cache.mkdirs())
                    throw new Exception("Could not create shared font cache");

                JSONArray paths = new JSONArray();
                int count = 0;
                long totalBytes = 0;
                int visitedFolders = 0;
                // Breadth-first scan. Bounded to avoid loops, huge providers and slow scans.
                java.util.ArrayDeque<String> pending = new java.util.ArrayDeque<>();
                java.util.HashSet<String> seen = new java.util.HashSet<>();
                pending.add(DocumentsContract.getTreeDocumentId(treeUri));
                while (!pending.isEmpty() && count < 200 && visitedFolders < 1000) {
                    String parentId = pending.removeFirst();
                    if (!seen.add(parentId)) continue;
                    visitedFolders++;
                    Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentId);
                    try (Cursor cursor = getContentResolver().query(children,
                            new String[] {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                    DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                                    DocumentsContract.Document.COLUMN_MIME_TYPE,
                                    DocumentsContract.Document.COLUMN_SIZE}, null, null, null)) {
                        if (cursor == null) {
                            Log.w(TAG, "Cannot list font subfolder: " + parentId);
                            continue;
                        }
                        while (cursor.moveToNext() && count < 200) {
                            String documentId = cursor.getString(0);
                            String name = cursor.getString(1);
                            String mime = cursor.getString(2);
                            if (documentId == null || name == null) continue;
                            if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                                if (seen.size() + pending.size() < 1000) pending.addLast(documentId);
                                continue;
                            }
                            String lower = name.toLowerCase(java.util.Locale.ROOT);
                            if (!lower.endsWith(".ttf") && !lower.endsWith(".otf")) continue;
                            if (!cursor.isNull(3)) {
                                long size = cursor.getLong(3);
                                if (size <= 0 || size > 32L * 1024 * 1024) continue;
                            }
                            Uri fontUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, documentId);
                            String extension = lower.endsWith(".ttf") ? ".ttf" : ".otf";
                            // Use the full document ID for cache naming, including subfolder path.
                            String hash = java.util.UUID.nameUUIDFromBytes(
                                    documentId.getBytes(java.nio.charset.StandardCharsets.UTF_8))
                                    .toString();
                            File target = new File(cache, "font-" + hash + extension);
                            try (InputStream input = getContentResolver().openInputStream(fontUri);
                                 OutputStream output = new FileOutputStream(target)) {
                                if (input == null) throw new Exception("Cannot read font " + name);
                                byte[] buffer = new byte[64 * 1024];
                                int n;
                                long total = 0;
                                while ((n = input.read(buffer)) != -1) {
                                    total += n;
                                    if (total > 32L * 1024 * 1024)
                                        throw new Exception("Font too large: " + name);
                                    totalBytes += n;
                                    if (totalBytes > 128L * 1024 * 1024) throw new Exception("Shared font refresh reached the 128 MB limit");
                                    output.write(buffer, 0, n);
                                }
                                if (total == 0) throw new Exception("Empty font: " + name);
                            } catch (Exception fontError) {
                                target.delete();
                                Log.w(TAG, "Skipping shared font " + name, fontError);
                                continue;
                            }
                            paths.put(target.getAbsolutePath());
                            count++;
                        }
                    } catch (SecurityException securityError) {
                        throw securityError;
                    } catch (Exception folderError) {
                        Log.w(TAG, "Skipping unreadable font subfolder: " + parentId, folderError);
                    }
                }
                JSONObject result = base(id, "font_folder", "ok");
                result.put("paths", paths);
                result.put("count", count);
                results.offer(result.toString());
            } catch (Exception error) {
                enqueueError(id, "font_folder", error.toString());
            }
        });
    }
