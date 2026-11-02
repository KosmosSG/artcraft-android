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

    fn key_event(key: egui::Key, pressed: bool, repeat: bool, modifiers: egui::Modifiers) -> egui::Event {
        egui::Event::Key { key, physical_key: None, pressed, repeat, modifiers }
    }
    #[test]
    fn dcs_raw_keyboard_repeats_and_does_not_leak_text_into_canvas() {
        let mut app = app();
        app.dialog = Some(dialogs::Dialog::new("close"));
        let ctx = egui::Context::default();
        for (key, letter, action) in [
            (egui::Key::D, "d", 1_u8),
            (egui::Key::C, "C", 2_u8),
            (egui::Key::S, "s", 3_u8),
            (egui::Key::D, "D", 1_u8),
        ] {
            let mut raw = egui::RawInput::default();
            raw.events = vec![
                key_event(key, true, false, egui::Modifiers::NONE),
                egui::Event::Text(letter.to_owned()),
                key_event(key, false, false, egui::Modifiers::NONE),
            ];
            app.android_capture_unsaved_dcs_raw(&ctx, &mut raw);
            assert!(raw.events.is_empty(), "Modal must consume D/C/S key-down, text and key-up");
            assert_eq!(
                ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))),
                Some(action)
            );
        }
    }
    #[test]
    fn dcs_raw_shortcuts_require_modal_and_ignore_ctrl_key_repeats() {
        let mut app = app();
        let ctx = egui::Context::default();
        let mut raw = egui::RawInput::default();
        raw.events = vec![key_event(egui::Key::D, true, false, egui::Modifiers::NONE)];
        app.android_capture_unsaved_dcs_raw(&ctx, &mut raw);
        assert_eq!(raw.events.len(), 1, "Non-modal text input must remain untouched");
        assert_eq!(ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))), None);

        app.dialog = Some(dialogs::Dialog::new("quit"));
        let mut ctrl = egui::Modifiers::NONE;
        ctrl.ctrl = true;
        ctrl.command = true;
        let mut raw = egui::RawInput::default();
        raw.events = vec![key_event(egui::Key::S, true, false, ctrl), egui::Event::Text("s".into())];
        app.android_capture_unsaved_dcs_raw(&ctx, &mut raw);
        assert_eq!(raw.events.len(), 2, "Ctrl+S must not become bare Save in dialog");
        assert_eq!(ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))), None);

        let mut raw = egui::RawInput::default();
        raw.events = vec![key_event(egui::Key::C, true, true, egui::Modifiers::NONE)];
        app.android_capture_unsaved_dcs_raw(&ctx, &mut raw);
        assert!(raw.events.is_empty(), "Repeated modal keystrokes must not reach the canvas");
        assert_eq!(ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))), None);
    }
    #[test]
    fn ctrl_w_is_detected_during_text_edit_without_stealing_other_shortcuts() {
        let mut app = app();
        let mut ctrl = egui::Modifiers::NONE;
        ctrl.ctrl = true;
        ctrl.command = true;
        assert!(SlideApp::android_editing_ctrl_w(&[key_event(egui::Key::W, true, false, ctrl)]));
        assert!(!SlideApp::android_editing_ctrl_w(&[key_event(egui::Key::W, false, false, ctrl)]));
        assert!(!SlideApp::android_editing_ctrl_w(&[key_event(egui::Key::W, true, true, ctrl)]));
        assert!(!SlideApp::android_editing_ctrl_w(&[key_event(egui::Key::W, true, false, egui::Modifiers::NONE)]));
        assert!(!SlideApp::android_editing_ctrl_w(&[key_event(egui::Key::S, true, false, ctrl)]));
        let mut modified = ctrl;
        modified.shift = true;
        assert!(!SlideApp::android_editing_ctrl_w(&[key_event(egui::Key::W, true, false, modified)]));
        // The shortcut must use the standard unsaved-change confirmation.
        // No document is silently closed or saved.
        assert!(app.session.active().unwrap().is_dirty());
        app.close_presentation();
        assert!(app.dialog.as_ref().is_some_and(|d| d.id == "close"));
        assert!(app.session.active().unwrap().is_dirty());
    }

    #[test]
    fn ctrl_w_raw_shortcut_survives_editor_focus_and_routes_to_safe_close() {
        let app = app();
        let ctx = egui::Context::default();
        let mut ctrl = egui::Modifiers::NONE;
        ctrl.ctrl = true;
        ctrl.command = true;
        let mut raw = egui::RawInput::default();
        raw.events = vec![key_event(egui::Key::W, true, false, ctrl)];
        app.android_capture_editor_close_raw(&ctx, &mut raw);
        assert!(raw.events.is_empty(), "Ctrl+W must not reach active text editor");
        assert_eq!(
            ctx.data_mut(|d| d.remove_temp::<bool>(egui::Id::new("deckcraft.android.ctrl_w"))),
            Some(true),
        );
        // Ordinary keys, including clipboard shortcuts, remain untouched.
        let mut raw = egui::RawInput::default();
        raw.events = vec![key_event(egui::Key::C, true, false, ctrl)];
        app.android_capture_editor_close_raw(&ctx, &mut raw);
        assert_eq!(raw.events.len(), 1);
        assert_eq!(
            ctx.data_mut(|d| d.remove_temp::<bool>(egui::Id::new("deckcraft.android.ctrl_w"))),
            None,
        );
    }

    #[test]
    fn import_font_is_help_only_no_duplicate_file_menu() {
        let tree = crate::menus::menu_tree();
        let file = tree.iter().find(|(name, _)| *name == "File").unwrap();
        let help = tree.iter().find(|(name, _)| *name == "Help").unwrap();
        assert_eq!(
            file.1.iter().filter(|(_, id)| *id == "app.importFont").count(), 0
        );
        assert_eq!(
            help.1.iter().filter(|(_, id)| *id == "app.importFont").count(), 1
        );
    }

    #[test]
    fn android_clipboard_and_select_all_capture_only_when_canvas_text_is_editing() {
        let mut app = app();
        let ctx = egui::Context::default();
        let mut mods = egui::Modifiers::NONE;
        mods.ctrl = true;
        mods.command = true;
        let mut plain = egui::RawInput::default();
        plain.events = vec![key_event(egui::Key::A, true, false, mods)];
        app.android_capture_editor_clipboard_raw(&ctx, &mut plain);
        assert_eq!(plain.events.len(), 1, "Ctrl+A outside text must not be swallowed");
        assert!(ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.android.clip_action"))).is_none());

        app.session.execute("shape.insert", &json!({
            "preset":"rect", "rect":[40.0,40.0,240.0,90.0], "text":"Example text"
        })).unwrap();
        app.session.execute("text.edit", &json!({})).unwrap();
        assert!(app.session.active().unwrap().selection.text.is_some());
        for (key, action) in [
            (egui::Key::A,1_u8), (egui::Key::C,2_u8),
            (egui::Key::X,3_u8), (egui::Key::V,4_u8)
        ] {
            let mut raw = egui::RawInput::default();
            raw.events = vec![key_event(key, true, false, mods)];
            if action == 4 { raw.events.push(egui::Event::Paste("Hello".into())); }
            app.android_capture_editor_clipboard_raw(&ctx, &mut raw);
            assert!(raw.events.is_empty(), "Shortcut must not leak to custom text editor");
            assert_eq!(ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.android.clip_action"))), Some(action));
            if action == 4 {
                assert_eq!(ctx.data_mut(|d| d.remove_temp::<String>(egui::Id::new("deckcraft.android.clip_text"))), Some("Hello".into()));
            }
        }
        let mut raw = egui::RawInput::default();
        raw.events = vec![key_event(egui::Key::A, true, false, egui::Modifiers::NONE)];
        app.android_capture_editor_clipboard_raw(&ctx, &mut raw);
        assert_eq!(raw.events.len(), 1, "Plain typing is not Ctrl+A");
    }

    #[test]
    fn editor_select_all_command_targets_text_not_slides() {
        let mut app = app();
        app.session.execute("shape.insert", &json!({
            "preset":"rect", "rect":[30.0,30.0,250.0,75.0], "text":"Select me"
        })).unwrap();
        app.session.execute("text.edit", &json!({})).unwrap();
        app.session.execute("text.selectAll", &json!({})).unwrap();
        assert!(app.session.active().unwrap().selection.text.as_ref().unwrap().is_range());
    }

    #[test]
    fn escape_remains_in_raw_input_for_deckcraft_text_editing() {
        let mut app = app();
        app.dialog = Some(dialogs::Dialog::new("close"));
        let ctx = egui::Context::default();
        let mut raw = egui::RawInput::default();
        raw.events = vec![key_event(egui::Key::Escape, true, false, egui::Modifiers::NONE)];
        app.android_capture_unsaved_dcs_raw(&ctx, &mut raw);
        assert_eq!(raw.events.len(), 1, "Esc must reach DeckCraft to exit typing or cancel");
        assert_eq!(ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))), None);
    }

}
