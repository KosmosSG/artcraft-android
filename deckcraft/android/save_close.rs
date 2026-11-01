
impl SlideApp {
    /// Android's asynchronous SAF export must acknowledge the provider write before closing.
    pub fn android_save_and_close(&mut self, quit: bool) {
        if self.android_pending_close.is_some() { return; }
        if quit {
            if let Some(index) = self.session.documents().iter().position(|d| d.is_dirty()) {
                self.session.set_active(index);
            } else {
                self.dialog = Some(dialogs::Dialog::new("quit"));
                return;
            }
        }
        let Some(doc) = self.session.active() else { return };
        let uid = doc.uid;
        let snapshot = doc.doc.clone();
        let name = format!("{}.deckcraft", doc.title());
        let bytes = match deckcraft_engine::cmd::file::save_bytes(&snapshot, "deckcraft") {
            Ok(bytes) => bytes,
            Err(error) => { self.set_status(error.to_string()); return; }
        };
        let id = self.next_file_id;
        self.next_file_id = self.next_file_id.wrapping_add(1).max(1);
        if let Some(save) = self.services.android_save_close.as_mut() {
            self.android_pending_close = Some((id, uid, snapshot, quit));
            save(id, &name, &bytes);
        }
    }

    fn android_save_finished(&mut self, id: u64, success: bool) {
        if !self.android_pending_close.as_ref().is_some_and(|(pending, ..)| *pending == id) { return; }
        let Some((_, uid, snapshot, quit)) = self.android_pending_close.take() else { return; };
        if !success {
            self.set_status("Save cancelled or failed; the presentation remains open.");
            return;
        }
        // A late reply must never close a different presentation or discard newer edits.
        let Some(doc) = self.session.active_mut().filter(|d| d.uid == uid) else { return; };
        if !std::sync::Arc::ptr_eq(&doc.doc, &snapshot) {
            self.set_status("Saved the earlier version; newer changes remain open.");
            return;
        }
        doc.saved_doc = snapshot;
        if quit {
            self.android_save_and_close(true);
        } else {
            let _ = self.run("file.close", serde_json::json!({}));
        }
    }
}
