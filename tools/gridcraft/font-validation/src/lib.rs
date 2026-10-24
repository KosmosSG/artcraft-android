// fonts.rs is copied from the actual patched, pinned upstream checkout by CI.
pub mod fonts;
pub mod ribbon { pub const FONTS: &[&str] = &["Arial", "Calibri"]; }
#[cfg(test)]
mod android_tests {
    use super::fonts;
    #[test]
    fn imported_ttf_otf_reload_dropdown_and_render() {
        let _guard = fonts::TEST_LOCK.lock().unwrap();
        let home = std::env::temp_dir().join(format!("gc-android-e2e-{}", std::process::id()));
        let imported = home.join("ArtCraft-Fonts/artcraft-imported");
        let shared = home.join("ArtCraft-Fonts/artcraft-shared");
        std::fs::create_dir_all(&imported).unwrap();
        std::fs::create_dir_all(&shared).unwrap();
        std::env::set_var("HOME", &home);
        fonts::catalog(); // Reproduce catalog initialized BEFORE SAF import.
        let ttf = imported.join("saf-import.ttf");
        std::fs::write(&ttf, epaint_default_fonts::UBUNTU_LIGHT).unwrap();
        let otf = shared.join("shared-import.otf");
        std::fs::copy("/usr/share/fonts/opentype/freefont/FreeMono.otf", &otf).unwrap();
        std::fs::write(imported.join("broken.ttf"), b"\0\x01\0\0broken").unwrap();
        let generation = fonts::generation();
        fonts::reload_catalog();
        assert!(fonts::generation() > generation);
        let catalog = fonts::catalog();
        for path in [&ttf, &otf] {
            let face = catalog.iter().find(|f| &f.path == path).expect("saved font detected");
            assert!(fonts::families().contains(&face.family), "Home dropdown contains family");
            let mut definitions = egui::FontDefinitions::default();
            let bound = fonts::bind_family(&mut definitions, &face.family);
            assert_eq!(bound.len(), 4, "all worksheet style roles bound");
            let key = fonts::role_key(&face.family, false, false);
            let chain = &definitions.families[&egui::FontFamily::Name(key.clone().into())];
            assert!(chain[0].starts_with("fnt-src:"), "actual imported face precedes fallback");
            let ctx = egui::Context::default();
            ctx.set_fonts(definitions);
            let _ = ctx.run(egui::RawInput::default(), |ctx| {
                egui::CentralPanel::default().show(ctx, |ui| {
                    let galley = ui.painter().layout_no_wrap("GridCraft 123".into(),
                        egui::FontId::new(20.0, egui::FontFamily::Name(key.clone().into())), egui::Color32::BLACK);
                    assert!(galley.size().x > 0.0);
                    assert!(!galley.rows.is_empty());
                });
            });
        }
        assert!(!catalog.iter().any(|f| f.path.ends_with("broken.ttf")));
        std::fs::remove_file(&otf).unwrap();
        fonts::reload_catalog();
        assert!(!fonts::catalog().iter().any(|f| f.path == otf), "removed shared files leave catalog");
        std::fs::remove_dir_all(home).unwrap();
    }
}
