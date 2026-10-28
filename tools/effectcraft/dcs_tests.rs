#[cfg(test)]
mod android_dcs_regression {
    use super::*;

    fn key(key: egui::Key, modifiers: egui::Modifiers, repeat: bool) -> egui::Event {
        egui::Event::Key { key, physical_key: Some(key), pressed: true, repeat, modifiers }
    }
    fn press(app: &mut EffectcraftApp, ctx: &egui::Context, event: egui::Event) {
        let mut raw = egui::RawInput::default();
        raw.events.push(event);
        let _ = ctx.run_ui(raw, |ui| {
            app.android_capture_unsaved_dcs(ui.ctx());
            crate::panels::dialogs::show(app, ui.ctx());
        });
    }
    fn dirty() -> (EffectcraftApp, egui::Context) {
        let ctx = egui::Context::default();
        let mut app = EffectcraftApp::new(effectcraft_engine::Session::default());
        crate::theme::install(&ctx, &app.tokens, crate::i18n::language(&app));
        app.session.execute("comp.new", json!({"name":"Main","width":64,"height":64})).unwrap();
        (app, ctx)
    }
    #[test]
    fn dcs_cancel_discard_and_inactive_guard() {
        let (mut app, ctx) = dirty();
        assert!(!app.android_unsaved_dcs_active());
        crate::menus::invoke(&mut app, &ctx, "file.closeProject", json!({})).unwrap();
        press(&mut app, &ctx, key(egui::Key::C, egui::Modifiers::NONE, false));
        assert!(app.dialog.is_none() && app.session.is_dirty());
        assert_eq!(app.session.project.comps().count(), 1);
        crate::menus::invoke(&mut app, &ctx, "file.closeProject", json!({})).unwrap();
        press(&mut app, &ctx, key(egui::Key::D, egui::Modifiers::NONE, false));
        assert!(app.dialog.is_none() && !app.session.is_dirty());
        assert_eq!(app.session.project.comps().count(), 0);
    }
    #[test]
    fn dcs_modified_keys_do_not_answer() {
        for mods in [egui::Modifiers::CTRL, egui::Modifiers::SHIFT, egui::Modifiers::ALT, egui::Modifiers::COMMAND] {
            let (mut app, ctx) = dirty();
            crate::menus::invoke(&mut app, &ctx, "file.closeProject", json!({})).unwrap();
            press(&mut app, &ctx, key(egui::Key::D, mods, false));
            assert!(app.android_unsaved_dcs_active() && app.session.is_dirty());
        }
    }
    #[test]
    fn dcs_save_writes_before_closing() {
        let (mut app, ctx) = dirty();
        let path = std::env::temp_dir().join(format!("effectcraft-dcs-{}.ecproj",std::process::id()));
        app.session.execute("file.saveAs", json!({"path":path.to_string_lossy()})).unwrap();
        app.session.execute("layer.newNull", json!({})).unwrap();
        crate::menus::invoke(&mut app, &ctx, "file.closeProject", json!({})).unwrap();
        press(&mut app, &ctx, key(egui::Key::S, egui::Modifiers::NONE, false));
        assert!(app.dialog.is_none() && app.session.project.comps().count() == 0);
        app.session.execute("file.open", json!({"path":path.to_string_lossy()})).unwrap();
        assert_eq!(app.session.active_comp().unwrap().layers.len(), 1);
        let _ = std::fs::remove_file(path);
    }
}
