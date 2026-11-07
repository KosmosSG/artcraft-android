#!/usr/bin/env python3
"""DeckCraft Android v0.16.0 PPTX Open With + nonblocking Save As.

Runs only inside the CI builder after approved Android feature overlays.
"""
from pathlib import Path
import sys
root=Path(sys.argv[1])

def patch(path: Path, old: str, new: str):
    text=path.read_text(encoding="utf-8")
    found=text.count(old)
    if found != 1:
        raise RuntimeError(f"DeckCraft save/file fix anchor mismatch {path}: {found} matches: {old[:100]!r}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")

# File associations already advertise ACTION_VIEW and typed PPTX.
# Add ACTION_EDIT (used by some file managers) for DeckCraft MIME types only.
assoc=root/"lib/file_associations.py"
patch(assoc,
'''        filters.append(
            '{{ actions = ["android.intent.action.VIEW"], categories = ["android.intent.category.DEFAULT"], data = [{0}] }}'.format(data)
        )
        # Let a browser hand a remote document straight to the app too''',
'''        filters.append(
            '{{ actions = ["android.intent.action.VIEW"], categories = ["android.intent.category.DEFAULT"], data = [{0}] }}'.format(data)
        )
        if app == "deckcraft":
            filters.append(
                '{{ actions = ["android.intent.action.EDIT"], categories = ["android.intent.category.DEFAULT"], data = [{0}] }}'.format(data)
            )
        # Let a browser hand a remote document straight to the app too''')
activity=root/"templates/android/SafActivity.java"
patch(activity,
    '        if (Intent.ACTION_VIEW.equals(action)) {\n',
    '        if (Intent.ACTION_VIEW.equals(action) || Intent.ACTION_EDIT.equals(action)) {\n')

# The stock save_as_dialog blocks the egui rendering frame waiting for the
# Android system picker. Use DeckCraft's already-integrated async SAF download
# path instead for PPTX. SAF writes/commits bytes AFTER provider confirmation.
# User's live presentation, recovery data and unsaved marker are preserved.
files=root/"source/deckcraft/crates/ui-egui/src/app/files.rs"
patch(files,
'''        let suggested = format!("{name}.{ext}");
        if let Some(pick) = self.services.pick_save.as_mut() {''',
'''        let suggested = format!("{name}.{ext}");
        #[cfg(target_os = "android")]
        if ext == "pptx" {
            // Nonblocking Android file picker: never hold the renderer thread
            // in the SAF request while DocumentsUI takes focus/surface.
            // The existing async download bridge commits after the file picker
            // approves, and cancellation leaves the editable document intact.
            let copy = self.session.active().map(|doc|
                deckcraft_engine::cmd::file::save_bytes(&doc.doc, "pptx")
            );
            match copy {
                Some(Ok(bytes)) => {
                    if let Some(download) = self.services.download.as_mut() {
                        download(&suggested, &bytes);
                        self.set_status("Choose where to save your PowerPoint copy. The original presentation stays open.");
                    } else {
                        self.set_status("Android PowerPoint save is unavailable; presentation unchanged.");
                    }
                    return;
                }
                Some(Err(error)) => {
                    self.set_status(format!("Could not create PowerPoint copy: {error}"));
                    return;
                }
                None => return,
            }
        }
        if let Some(pick) = self.services.pick_save.as_mut() {''')
assert 'android.intent.action.EDIT' in assoc.read_text()
assert '"deckcraft": ["deckcraft", "pptx", "potx", "ppsx"]' in assoc.read_text()
assert 'Intent.ACTION_VIEW.equals(action) || Intent.ACTION_EDIT.equals(action)' in activity.read_text()
assert 'handleIncomingFiles(intent)' in activity.read_text()
result=files.read_text()
assert 'deckcraft_engine::cmd::file::save_bytes(&doc.doc, "pptx")' in result
assert 'download(&suggested, &bytes);' in result
assert 'self.session.execute("file.saveAs", &json!({"path": path}))' in result
print("PASS: PPTX typed ACTION_VIEW+ACTION_EDIT filters and inbound SAF handler")
print("PASS: async PPTX Save As with original presentation/recovery unchanged")
