#[cfg(test)]
mod android_dcs_regression {
    use super::*;
    fn app() -> (WordApp, egui::Context) {
        let mut app = WordApp::new(wordcraft_engine::Session::new(wordcraft_doc::Document::new()), crate::Services::default());
        app.run("text.insert", json!({"text":"Keep this draft"})).unwrap();
        app.run("file.close", json!({})).unwrap();
        assert!(app.android_unsaved_dcs_active());
        (app, egui::Context::default())
    }
    fn press(app: &mut WordApp, ctx: &egui::Context, key: egui::Key, mods: egui::Modifiers, repeat: bool) {
        let raw = egui::RawInput { events: vec![egui::Event::Key { key, physical_key: Some(key), pressed:true, repeat, modifiers:mods }], ..Default::default() };
        let mut out = ctx.run_ui(raw, |ui| {
            app.android_capture_unsaved_dcs(ui.ctx());
            show(app, ui.ctx());
        });
        out.textures_delta.clear();
    }
    #[test]
    fn cancel_preserves_and_discard_closes_document() {
        let (mut app, ctx) = app();
        press(&mut app, &ctx, egui::Key::C, egui::Modifiers::NONE, false);
        assert!(app.has_document() && app.session.dirty && !app.android_unsaved_dcs_active());
        app.run("file.close", json!({})).unwrap();
        press(&mut app, &ctx, egui::Key::D, egui::Modifiers::NONE, false);
        assert!(!app.has_document());
    }
    #[test]
    fn cancelled_save_as_preserves_document() {
        let (mut app, ctx) = app();
        app.services.pick_save = Some(Box::new(|_| None));
        press(&mut app, &ctx, egui::Key::S, egui::Modifiers::NONE, false);
        assert!(app.has_document() && app.session.dirty && !app.quit_requested);
    }
    #[test]
    fn repeats_modifiers_and_outside_modal_do_not_discard() {
        for (mods, repeat) in [(egui::Modifiers::CTRL,false),(egui::Modifiers::SHIFT,false),(egui::Modifiers::NONE,true)] {
            let (mut app, ctx) = app();
            press(&mut app, &ctx, egui::Key::D, mods, repeat);
            assert!(app.has_document() && app.session.dirty && app.android_unsaved_dcs_active());
        }
        let (mut app, ctx) = app();
        app.dialog = None;
        press(&mut app, &ctx, egui::Key::D, egui::Modifiers::NONE, false);
        assert!(app.has_document() && app.session.dirty);
    }
}
