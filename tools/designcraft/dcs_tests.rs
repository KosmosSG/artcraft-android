#[cfg(test)]
mod android_dcs_regression {
    use super::*;
    use std::{cell::RefCell,rc::Rc};
    #[test]
    fn saf_cancel_keeps_document_and_success_closes_only_after_ack() {
        for success in [false,true] {
            let mut app=DesignApp::new(designcraft_engine::Session::new(),Services::default());
            app.run("file.new",json!({})).unwrap();
            let uid=app.session.active().unwrap().uid;
            let reply=Rc::new(RefCell::new(None));let sent=reply.clone();
            app.services.android_save_close=Some(Box::new(move |_,_,tx|*sent.borrow_mut()=Some(tx)));
            app.android_save_and_close(uid,false).unwrap();
            assert!(app.session.active().is_some());
            reply.borrow_mut().take().unwrap().send(success).unwrap();
            app.android_poll_save_close(&egui::Context::default());
            assert_eq!(app.session.active().is_none(),success);
        }
    }
}
