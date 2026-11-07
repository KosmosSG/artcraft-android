#[cfg(test)]
mod android_stability_tests {
    use super::*;
    use crate::{Services,VectorcraftApp};
    use vectorcraft_engine::Session;
    fn app()->VectorcraftApp {
        VectorcraftApp::new(Session::new(),Services {
            pick_save:Some(Box::new(|_:&crate::FilePick|Some("test.vectorcraft".into()))),
            write:Some(Box::new(|_:&str,_:&[u8]|Ok(()))), ..Default::default()
        })
    }
    fn dirty(app:&mut VectorcraftApp) {
        app.run("file.new",json!({"width":100,"height":100})).unwrap();
        app.run("shape.rectangle",json!({"x":0,"y":0,"width":10,"height":10})).unwrap();
    }
    fn press(app:&mut VectorcraftApp,key:Key) {
        let ctx=egui::Context::default();
        let mut output=ctx.run_ui(egui::RawInput {events:vec![egui::Event::Key {
            key,physical_key:Some(key),pressed:true,repeat:false,modifiers:Modifiers::NONE
        }],..Default::default()},|_|{android_save_changes_key(app,&ctx);});
        // This headless command test has no renderer to apply texture updates.
        output.textures_delta.clear();
    }
    #[test]
    fn android_stability_repeated_cancel_save_discard() {
        let mut app=app();
        for _ in 0..20 {
            dirty(&mut app);
            for _ in 0..3 {
                app.run("file.close",json!({})).unwrap(); press(&mut app,Key::C);
                assert_eq!(app.session.documents().len(),1);
                assert!(app.session.active().unwrap().is_dirty());
                assert!(app.ui.dialog.is_none());
            }
            app.run("file.close",json!({})).unwrap();press(&mut app,Key::S);
            assert!(app.session.documents().is_empty());
            dirty(&mut app);app.run("file.close",json!({})).unwrap();press(&mut app,Key::D);
            assert!(app.session.documents().is_empty());
        }
    }
    #[test]
    fn android_stability_failed_or_cancelled_save_retains_work() {
        for cancel in [true,false] {
            let mut app=app();
            if cancel {app.services.pick_save=Some(Box::new(|_:&crate::FilePick|None));}
            else {app.services.write=Some(Box::new(|_:&str,_:&[u8]|Err("provider failure".into())));}
            dirty(&mut app);app.run("app.quit",json!({})).unwrap();
            assert!(app.ui.dialog.as_ref().is_some_and(|d| d.kind == crate::unsaved::KIND));
            press(&mut app,Key::S);
            // Do not permit a vacuous pass when the key handler was never called.
            assert!(app.ui.dialog.is_none(), "S must attempt Save, even when the picker or provider fails");
            assert_eq!(app.session.documents().len(),1);
            assert!(app.session.active().unwrap().is_dirty()); assert_ne!(app.ui.status,"quit");
        }
    }
    #[test]
    fn android_stability_multi_document_quit_cancel() {
        let mut app=app();dirty(&mut app);dirty(&mut app);
        app.run("app.quit",json!({})).unwrap();press(&mut app,Key::C);
        assert_eq!(app.session.documents().len(),2);assert_ne!(app.ui.status,"quit");
        app.run("app.quit",json!({})).unwrap();press(&mut app,Key::D);
        assert_eq!(app.session.documents().len(),1);assert_ne!(app.ui.status,"quit");
        press(&mut app,Key::D);assert!(app.session.documents().is_empty());assert_eq!(app.ui.status,"quit");
    }
    #[test]
    fn android_stability_no_modal_no_action() {
        let mut app=app();dirty(&mut app);
        for key in [Key::D,Key::C,Key::S] {press(&mut app,key);}
        assert_eq!(app.session.documents().len(),1);assert!(app.session.active().unwrap().is_dirty());
    }
}
