#[cfg(test)]
mod android_font_montserrat {
    use super::*;
    #[test]
    fn ttf_otf_apply_render_save_reopen() {
        let dir = std::path::PathBuf::from(std::env::var("DECKCRAFT_TEST_FONTS").expect("CI font fixtures required"));
        let mut app = SlideApp::new(Session::with_new(), Services::default());
        app.session.execute("shape.insert", &serde_json::json!({
            "preset": "rect", "rect": [40.0, 40.0, 500.0, 120.0], "text": "Montserrat Aa 123"
        })).unwrap();
        let render = |app: &SlideApp| deckcraft_render::render_slide(
            &app.session.active().unwrap().doc, 0, &Default::default()).pixels;
        app.run("format.font", serde_json::json!({"family":"Montserrat"})).unwrap();
        let fallback = render(&app);
        for name in ["Montserrat-Regular.ttf", "Montserrat-SemiBold.ttf", "Montserrat-Medium.otf"] {
            app.import_font_bytes(name, &std::fs::read(dir.join(name)).unwrap());
        }
        let db = deckcraft_fonts::FontDb::global();
        let regular = render(&app);
        assert_ne!(fallback, regular, "Import must change actual rendered pixels");
        for (family, style) in [("Montserrat", "Regular"), ("Montserrat SemiBold", "SemiBold"), ("Montserrat Medium", "Medium")] {
            assert!(db.families().iter().any(|f| f == family), "Dropdown family {family}");
            let face = db.face(family, "Regular");
            assert_eq!(face.family, "Montserrat");
            assert_eq!(face.style, style);
            app.run("format.font", serde_json::json!({"family":family})).unwrap();
            let pixels = render(&app);
            if style != "Regular" { assert_ne!(pixels, regular, "Selected weight must change pixels"); }
            let bytes = deckcraft_engine::cmd::file::save_bytes(&app.session.active().unwrap().doc, "deckcraft").unwrap();
            let reopened = deckcraft_engine::cmd::file::open_presentation("font.deckcraft", &bytes).unwrap();
            assert_eq!(pixels, deckcraft_render::render_slide(&reopened, 0, &Default::default()).pixels);
        }
    }
}
