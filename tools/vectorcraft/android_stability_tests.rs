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
        use std::sync::Arc;
        use std::sync::atomic::{AtomicUsize, Ordering};

        // Both paths must really invoke the Save service, but a failed write
        // intentionally opens the upstream "Can't save" message dialog.
        // Requiring dialog.is_none() here erroneously panicked on a valid UI.
        for cancel in [true, false] {
            let mut app = app();
            let attempted = Arc::new(AtomicUsize::new(0));
            let attempt = Arc::clone(&attempted);
            if cancel {
                app.services.pick_save = Some(Box::new(move |_: &crate::FilePick| {
                    attempt.fetch_add(1, Ordering::SeqCst);
                    None // User cancelled the SAF / Save As picker.
                }));
            } else {
                app.services.write = Some(Box::new(move |_: &str, _: &[u8]| {
                    attempt.fetch_add(1, Ordering::SeqCst);
                    Err("provider failure".into())
                }));
            }

            dirty(&mut app);
            app.run("app.quit", json!({})).unwrap();
            assert!(app.ui.dialog.as_ref().is_some_and(|d| d.kind == crate::unsaved::KIND));
            press(&mut app, Key::S);

            assert!(
                attempted.load(Ordering::SeqCst) > 0,
                "Save must call the picker or writer even if that service fails"
            );
            assert_eq!(app.session.documents().len(), 1, "Failed Save must not close the document");
            assert!(app.session.active().is_some_and(|doc| doc.is_dirty()));
            assert_ne!(app.ui.status, "quit", "Failed Save must not exit the app");

            if cancel {
                // A cancelled file picker does not create a separate error message.
                assert!(app.ui.dialog.is_none(), "Cancel should leave no modal behind");
            } else {
                // Upstream write_reporting() deliberately displays a nonfatal
                // error dialog. Its presence PROVES failure reporting, not a
                // missing Save attempt; the unsaved document remains editable.
                assert!(
                    app.ui.dialog.as_ref().is_some_and(|d| d.kind == crate::dialogs::confirm::MESSAGE),
                    "A failed storage write should show the error-message dialog"
                );
            }
        }
    }
    #[test]
    fn android_stability_unavailable_save_intent_keeps_unsaved_work() {
        let mut app = app();
        // No Android picker is registered (e.g. the external SAF intent cannot start).
        app.services.pick_save = None;
        dirty(&mut app);
        app.run("app.quit", json!({})).unwrap();
        press(&mut app, Key::S);
        assert_eq!(app.session.documents().len(), 1);
        assert!(app.session.active().is_some_and(|doc| doc.is_dirty()));
        assert_ne!(app.ui.status, "quit");
        assert!(app.ui.dialog.is_none());
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
    fn android_stability_unfocused_modal_still_receives_physical_discard() {
        // The hidden Android EditText may leave egui's viewport unfocused.
        // A Save Changes modal must still accept physical D/C/S key presses.
        let mut app = app();
        dirty(&mut app);
        app.run("file.close", json!({})).unwrap();
        assert!(app.ui.dialog.as_ref().is_some_and(|d| d.kind == crate::unsaved::KIND));
        let ctx = egui::Context::default();
        let mut output = ctx.run_ui(egui::RawInput {
            focused: false,
            events: vec![egui::Event::Key {
                key: Key::D, physical_key: Some(Key::D), pressed: true,
                repeat: false, modifiers: Modifiers::NONE,
            }],
            ..Default::default()
        }, |_| { handle(&mut app, &ctx); });
        output.textures_delta.clear();
        assert!(app.session.documents().is_empty());
        assert!(app.ui.dialog.is_none());
    }

    #[test]
    fn android_stability_direct_owner_key_bridge_handles_save_cancel_discard() {
        // This is the same method called by the Android raw input hook,
        // not a substitute headless helper or a test-only assert.
        for key in [Key::S, Key::C, Key::D] {
            let mut app = app();
            dirty(&mut app);
            app.run("app.quit", json!({})).unwrap();
            assert_eq!(app.session.documents().len(), 1);
            assert!(app.android_owner_unsaved_key(key));
            match key {
                Key::S | Key::D => {
                    assert!(app.session.documents().is_empty());
                    assert_eq!(app.ui.status, "quit");
                }
                Key::C => {
                    assert_eq!(app.session.documents().len(), 1);
                    assert!(app.session.active().is_some_and(|d| d.is_dirty()));
                    assert_ne!(app.ui.status, "quit");
                }
                _ => unreachable!(),
            }
            assert!(app.ui.dialog.is_none());
        }
    }

    #[test]
    fn android_stability_native_owner_key_bridge_never_drops_failed_save() {
        let mut app = app();
        app.services.write = Some(Box::new(|_, _| Err("temporary SAF failure".into())));
        dirty(&mut app);
        app.run("app.quit", json!({})).unwrap();
        assert!(app.android_owner_unsaved_key(Key::S));
        assert_eq!(app.session.documents().len(), 1);
        assert!(app.session.active().is_some_and(|d| d.is_dirty()));
        assert_ne!(app.ui.status, "quit");
    }
    #[test]
    fn android_stability_no_modal_no_action() {
        let mut app=app();dirty(&mut app);
        for key in [Key::D,Key::C,Key::S] {press(&mut app,key);}
        assert_eq!(app.session.documents().len(),1);assert!(app.session.active().unwrap().is_dirty());
    }
}
