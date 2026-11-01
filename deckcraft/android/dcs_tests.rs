#[cfg(test)]
mod android_dcs_regression {
    use super::*;
    use std::{cell::RefCell,rc::Rc};
    fn app() -> SlideApp {
        let mut app=SlideApp::new(deckcraft_engine::Session::new(),crate::Services::default());
        app.run("file.new",json!({})).unwrap();
        app.run("slide.new",json!({})).unwrap();
        assert!(app.session.active().unwrap().is_dirty());
        app
    }
    #[test]
    fn saf_cancel_failure_and_late_reply_preserve_dirty_document() {
        let mut app=app();
        let request=Rc::new(RefCell::new(0));let sent=request.clone();
        app.services.android_save_close=Some(Box::new(move |id,_,_|*sent.borrow_mut()=id));
        app.android_save_and_close(false);
        let id=*request.borrow();
        app.android_save_finished(id+1,true);
        assert!(app.session.active().unwrap().is_dirty());
        app.android_save_finished(id,false);
        assert!(app.session.active().unwrap().is_dirty());
        app.android_save_and_close(false);
        let id=*request.borrow();
        app.run("slide.new",json!({})).unwrap();
        app.android_save_finished(id,true);
        assert!(app.session.active().unwrap().is_dirty());
    }
    #[test]
    fn successful_matching_saf_write_closes_only_after_ack() {
        let mut app=app();
        let request=Rc::new(RefCell::new(0));let sent=request.clone();
        app.services.android_save_close=Some(Box::new(move |id,_,_|*sent.borrow_mut()=id));
        app.android_save_and_close(false);
        assert!(app.session.active().is_some());
        app.android_save_finished(*request.borrow(),true);
        assert!(app.session.active().is_none());
    }
}
