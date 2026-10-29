
impl DesignApp {
    pub fn android_save_and_close(&mut self, uid: u64, quit: bool) -> Result<Value,String> {
        if self.android_pending_close.is_some() {return Ok(Value::Null);}
        let index=self.session.documents().iter().position(|d|d.uid==uid).ok_or("Document closed")?;
        self.run("file.activate",json!({"index":index}))?;
        let ser=self.run("file.serialize",json!({}))?;
        let bytes=designcraft_engine::cmd::base64_decode(ser.get("base64").and_then(Value::as_str).ok_or("Save returned no document bytes")?);
        let doc=self.session.active().ok_or("No document")?;
        let revision=doc.revision;
        let name=format!("{}.designcraft",doc.doc.title);
        let (tx,rx)=std::sync::mpsc::channel();
        let save=self.services.android_save_close.as_mut().ok_or("Android save service unavailable")?;
        save(&name,&bytes,tx);
        self.android_pending_close=Some((uid,revision,rx,quit));
        Ok(Value::Null)
    }
    fn android_poll_save_close(&mut self, ctx:&egui::Context) {
        let Some((_,_,rx,_))=&self.android_pending_close else{return;};
        let success=match rx.try_recv(){
            Ok(success)=>success,
            Err(std::sync::mpsc::TryRecvError::Empty)=>{ctx.request_repaint_after(std::time::Duration::from_millis(16));return;},
            Err(_)=>false,
        };
        let Some((uid,revision,_,quit))=self.android_pending_close.take() else{return;};
        if !success {self.cancel_quit();self.status("Save cancelled or failed; the document remains open.");return;}
        if !self.session.active().is_some_and(|d|d.uid==uid && d.revision==revision){
            self.cancel_quit();self.status("Saved the earlier version; current work remains open.");return;
        }
        if let Some(doc)=self.session.active_mut(){doc.saved_doc=doc.doc.clone();doc.saved_revision=revision;}
        if quit {
            if let Err(error)=self.confirm_quit_document(uid,true){self.cancel_quit();self.status(error);}
        } else if let Some(index)=self.session.documents().iter().position(|d|d.uid==uid){
            let _=self.run("file.close",json!({"index":index}));
        }
    }
}
