#[cfg(test)]
mod android_dcs_regression {
    use super::*;
    fn app() -> (FilmcraftApp, egui::Context) {
        let mut app = FilmcraftApp::new(filmcraft_engine::Session::default());
        app.session.execute("file.newBin", json!({"name":"Keep me"})).unwrap();
        assert!(app.session.is_dirty());
        let ctx = egui::Context::default();
        crate::theme::install(&ctx, &app.tokens);
        route(&mut app, "file.closeProject", &json!({})).unwrap().unwrap();
        (app, ctx)
    }
    fn press(app: &mut FilmcraftApp, ctx: &egui::Context, key: egui::Key, modifiers: egui::Modifiers) {
        let raw = egui::RawInput { events: vec![egui::Event::Key { key, physical_key: Some(key), pressed:true, repeat:false, modifiers }], ..Default::default() };
        let mut out = ctx.run_ui(raw, |ui| {
            app.android_capture_unsaved_dcs(ui.ctx());
            show(app, ui.ctx());
        });
        out.textures_delta.clear();
    }
    #[test]
    fn cancel_keeps_changes_and_discard_closes() {
        let (mut app, ctx) = app();
        press(&mut app, &ctx, egui::Key::C, egui::Modifiers::NONE);
        assert!(app.ui.clip_dialog.is_none() && app.session.is_dirty());
        route(&mut app, "file.closeProject", &json!({})).unwrap().unwrap();
        press(&mut app, &ctx, egui::Key::D, egui::Modifiers::NONE);
        assert!(app.ui.clip_dialog.is_none() && !app.session.is_dirty());
    }
    #[test]
    fn unavailable_save_and_modified_keys_keep_prompt() {
        for (key, mods) in [(egui::Key::S, egui::Modifiers::NONE), (egui::Key::D, egui::Modifiers::CTRL), (egui::Key::C, egui::Modifiers::SHIFT)] {
            let (mut app, ctx) = app();
            assert!(app.hooks.pick_save.is_none());
            press(&mut app, &ctx, key, mods);
            assert!(app.android_unsaved_dcs_active() && app.session.is_dirty());
        }
    }
    #[test]
    fn unrelated_clip_dialog_is_not_dcs_active() {
        let (mut app, _) = app();
        app.ui.clip_dialog.as_mut().unwrap().command = "clip.speedDuration".into();
        assert!(!app.android_unsaved_dcs_active());
    }
}
