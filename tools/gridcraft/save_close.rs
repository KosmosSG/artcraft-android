
impl SheetApp {
    pub fn android_save_and_close(&mut self, quit: bool) {
        if self.android_pending_close.is_some() || !self.commit_edit(0, 0, false, false) { return; }
        let result = match self.run("file.saveBytes", json!({"format":"xlsx"})) {
            Ok(result) => result,
            Err(error) => { self.alert(error); return; }
        };
        let Some(bytes) = result.get("base64").and_then(Json::as_str).and_then(gridcraft_engine::io::base64_decode) else { return; };
        let name = result.get("name").and_then(Json::as_str).unwrap_or("Book.xlsx");
        let Some(doc) = self.session.active() else { return; };
        let (uid, revision) = (doc.uid, doc.revision);
        if let Some(save) = &self.services.android_save_close {
            let (tx,rx) = std::sync::mpsc::channel();
            save(name,&bytes,tx);
            self.android_pending_close=Some((uid,revision,rx,quit));
        }
    }
    fn android_poll_save_close(&mut self, ctx: &egui::Context) {
        let Some((_,_,rx,_)) = &self.android_pending_close else { return; };
        let success = match rx.try_recv() {
            Ok(success) => success,
            Err(std::sync::mpsc::TryRecvError::Empty) => {ctx.request_repaint_after(std::time::Duration::from_millis(16));return;}
            Err(_) => false,
        };
        let Some((uid,revision,_,quit)) = self.android_pending_close.take() else { return; };
        if !success {self.alert("Save cancelled or failed; the workbook remains open.".into());return;}
        // A fresh editor draft may not have advanced the document revision yet.
        if self.editor.is_some() { return; }
        if !self.session.active().is_some_and(|d|d.uid==uid && d.revision==revision) {
            self.alert("Saved the earlier version; current work remains open.".into());return;
        }
        self.run_or_alert("file.close",json!({"force":true}));
        if quit {self.continue_quit(ctx);}
    }
}
