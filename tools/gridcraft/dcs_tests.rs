#[cfg(test)]
mod android_dcs_regression {
    use super::*;
    use std::{cell::RefCell,rc::Rc};
    fn app() -> (SheetApp,Rc<RefCell<Option<std::sync::mpsc::Sender<bool>>>>) {
        let reply=Rc::new(RefCell::new(None));let sent=reply.clone();
        let mut session=Session::new();session.new_workbook();
        let mut app=SheetApp::new(session,Services::default());
        app.run("cell.set",json!({"cell":"A1","input":"Keep me"})).unwrap();
        app.services.android_save_close=Some(Box::new(move |_,_,tx|*sent.borrow_mut()=Some(tx)));
        (app,reply)
    }
    #[test]
    fn saf_success_closes_only_after_ack_and_failure_keeps_work() {
        for success in [false,true] {
            let (mut app,reply)=app();let ctx=egui::Context::default();
            app.android_save_and_close(false);assert!(app.session.active().is_some());
            reply.borrow_mut().take().unwrap().send(success).unwrap();
            app.android_poll_save_close(&ctx);
            assert_eq!(app.session.active().is_none(),success);
        }
    }
    #[test]
    fn pending_editor_draft_survives_successful_earlier_save() {
        let (mut app,reply)=app();let ctx=egui::Context::default();
        app.android_save_and_close(false);
        app.begin_edit(Some("Not saved yet".into()),false);
        reply.borrow_mut().take().unwrap().send(true).unwrap();
        app.android_poll_save_close(&ctx);
        assert!(app.session.active().is_some());
        assert_eq!(app.editor.as_ref().unwrap().text,"Not saved yet");
    }
    #[test]
    fn stale_saf_success_does_not_discard_new_cell_edits() {
        let (mut app,reply)=app();let ctx=egui::Context::default();
        app.android_save_and_close(false);
        app.run("cell.set",json!({"cell":"A1","input":"Newer"})).unwrap();
        reply.borrow_mut().take().unwrap().send(true).unwrap();app.android_poll_save_close(&ctx);
        assert!(app.session.active().unwrap().is_dirty());
    }
}
