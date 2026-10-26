"""Android-only visible menus, docked tools and font cache invalidation, v0.9.0."""
from pathlib import Path
import sys
p = Path(sys.argv[1]) / 'crates/ui-egui/src/lib.rs'
s = p.read_text()
def change(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new, 1)
change('    pub ribbon_collapsed: bool,', '    pub ribbon_collapsed: bool,\n    #[serde(default)]\n    pub tablet_tools: bool,')
change('            ribbon_collapsed: false,', '            ribbon_collapsed: false,\n            tablet_tools: false,')
change('        ribbon::title_bar(self, ui);', '        self.tablet_controls(ui);\n        ribbon::title_bar(self, ui);')
change('                self.open_url("https://github.com/KosmosSG/artcraft-android/releases?q=deckcraft");\n                self.notify("Opened DeckCraft release listings; install only verified signed APK updates");', '''                if let Some(open) = self.services.open_async.as_mut() {
                    open("deckcraft-updates", 0);
                } else { self.notify("Update checks require the Android host"); }''')
change('            "app.importFont" => self.import_font_dialog(),', '''            "app.importFont" => self.import_font_dialog(),
            "view.tabletTools" => self.ui.tablet_tools = !self.ui.tablet_tools,''')
change('    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),', '''    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),
    ("view.tabletTools", "Tablet Tools", None, "{}"),''')
anchor = '    /// On Android the launcher provides private, update-persistent app storage.'
change(anchor, '''    fn tablet_controls(&mut self, ui: &mut egui::Ui) {
        #[cfg(target_os = "android")]
        {
            egui::Panel::top("deckcraft-tablet-menu").show(ui, |ui| {
                egui::MenuBar::new().ui(ui, |ui| {
                    let (_, rect) = ui.allocate_space(egui::vec2(24.0, 24.0));
                    dialogs::paint_logo(ui.painter(), rect);
                    for (name, entries) in menus::menu_tree() {
                        ui.menu_button(name, |ui| {
                            for (label, command) in entries {
                                if label == "-" { ui.separator(); continue; }
                                let label = if command == "view.tabletTools" && self.ui.tablet_tools {
                                    "✓ Tablet Tools"
                                } else { label };
                                if ui.add_sized([190.0, 32.0], egui::Button::new(label)).clicked() {
                                    let _ = self.run(command, serde_json::json!({}));
                                    ui.close();
                                }
                            }
                        });
                    }
                });
            });
            if self.ui.tablet_tools {
                egui::Panel::right("deckcraft-tablet-tools").default_size(220.0).show(ui, |ui| {
                    ui.heading("Tablet Tools");
                    if ui.button("Import Font…").clicked() { self.import_font_dialog(); }
                    if ui.button("Check for Updates…").clicked() {
                        let _ = self.run("app.checkUpdates", serde_json::json!({}));
                    }
                    ui.separator();
                    ui.label("Detected font families / styles");
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        let db = deckcraft_fonts::FontDb::global();
                        for family in db.families() {
                            ui.label(format!("{} — {}", family, db.styles(&family).join(", ")));
                        }
                    });
                });
            }
        }
        #[cfg(not(target_os = "android"))]
        let _ = ui;
    }

''' + anchor)
start = s.index('    pub fn import_font_dialog(')
end = s.index('    pub fn open_or_insert_bytes', start)
piece = s[start:end].replace('self.set_status(', 'self.notify(')
piece = piece.replace('        let added = deckcraft_fonts::FontDb::global().add_font(bytes.to_vec());', '''        let db = deckcraft_fonts::FontDb::global();
        let before: Vec<_> = db.families().into_iter().map(|f| {
            let styles = db.styles(&f); (f, styles)
        }).collect();
        let added = db.add_font(bytes.to_vec());
        // Font registration does not change the slide/master Arc used as texture keys.
        self.textures = textures::Textures::default();
        let detected = db.families().into_iter().filter_map(|family| {
            let styles = db.styles(&family);
            if before.iter().any(|(f, st)| f == &family && st == &styles) { None }
            else { Some(format!("{} ({})", family, styles.join(", "))) }
        }).collect::<Vec<_>>().join("; ");''')
piece = piece.replace('Imported {added} font face(s) from {name}; saved across updates', 'Detected {detected}; imported {added} face(s), saved across restarts and updates')
s = s[:start] + piece + s[end:]
p.write_text(s)
p = Path(sys.argv[1]) / 'crates/ui-egui/src/menus.rs'
s = p.read_text()
assert s.count('("Normal", "view.normal"),') == 1
p.write_text(s.replace('("Normal", "view.normal"),', '("Tablet Tools", "view.tabletTools"),\n                ("Normal", "view.normal"),'))
p = Path(sys.argv[1]) / 'crates/ui-egui/src/lib.rs'
p.write_text(p.read_text() + r'''
#[cfg(test)]
mod android_font_regression {
    use super::*;
    #[test]
    fn import_apply_render_and_document_roundtrip() {
        let mut app = SlideApp::new(Session::with_new(), Services::default());
        app.session.execute("shape.insert", &serde_json::json!({
            "preset": "rect", "rect": [40.0, 40.0, 240.0, 80.0], "text": "AAA"
        })).unwrap();
        app.run("format.font", serde_json::json!({"family": "DeckCraft Legacy"})).unwrap();
        let render = |app: &SlideApp| {
            deckcraft_render::render_slide(&app.session.active().unwrap().doc, 0, &Default::default()).pixels
        };
        let before = render(&app);
        app.import_font_bytes("legacy-regular.ttf", include_bytes!("../../fonts/tests/fixtures/legacy-regular.ttf"));
        app.import_font_bytes("legacy-semibold.ttf", include_bytes!("../../fonts/tests/fixtures/legacy-semibold.ttf"));
        let db = deckcraft_fonts::FontDb::global();
        assert!(db.families().iter().any(|f| f == "DeckCraft Legacy"));
        assert_eq!(db.face("DeckCraft Legacy", "Regular").family, "DeckCraft Legacy");
        assert!(db.styles("DeckCraft Legacy").len() >= 2);
        let after = render(&app);
        assert_ne!(before, after, "Imported font must change rendered slide pixels");
        assert!(db.families().iter().any(|f| f == "DeckCraft Legacy Semibold"));
        assert_eq!(db.face("DeckCraft Legacy Semibold", "Regular").style, "Semibold");
        let bytes = deckcraft_engine::cmd::file::save_bytes(&app.session.active().unwrap().doc, "deckcraft").unwrap();
        let reopened = deckcraft_engine::cmd::file::open_presentation("font-test.deckcraft", &bytes).unwrap();
        assert_eq!(after, deckcraft_render::render_slide(&reopened, 0, &Default::default()).pixels);
        app.run("view.tabletTools", serde_json::json!({})).unwrap();
        let prefs = serde_json::to_vec(&app.ui).unwrap();
        let restored: UiState = serde_json::from_slice(&prefs).unwrap();
        assert!(restored.tablet_tools);
    }
}
''')
# Imported faces must expose the same legacy weight-family aliases as disk-scanned fonts.
p = Path(sys.argv[1]) / 'crates/fonts/src/fontdb.rs'
s = p.read_text()
a = '        let mut v: Vec<String> = self.read_faces().iter().map(|f| f.family.clone()).collect();'
b = '''        let mut v: Vec<String> = self.read_faces().iter().flat_map(|f| {
            std::iter::once(f.family.clone()).chain(f.legacy.as_ref().map(|(family, _)| family.clone()))
        }).collect();'''
assert s.count(a) == 1
s = s.replace(a, b)
a = '''            .filter(|f| f.family.eq_ignore_ascii_case(family) && !f.style.contains('{'))
            .map(|f| (f.italic, f.weight, f.style.clone()))'''
b = '''            .filter_map(|f| {
                if f.style.contains('{') { return None; }
                if f.family.eq_ignore_ascii_case(family) {
                    Some((f.italic, f.weight, f.style.clone()))
                } else {
                    f.legacy.as_ref().filter(|(name, _)| name.eq_ignore_ascii_case(family))
                        .map(|(_, style)| (f.italic, f.weight, style.clone()))
                }
            })'''
assert s.count(a) == 1
p.write_text(s.replace(a, b))

# Reuse the approved Dk artwork in Android in-app branding as well as the launcher.
import base64, zlib
rgba = zlib.decompress(base64.b64decode('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'))
assert len(rgba) == 48 * 48 * 4
p = Path(sys.argv[1]) / 'crates/ui-egui/src/dialogs.rs'
s = p.read_text()
anchor = 'pub fn paint_logo(p: &egui::Painter, r: Rect) {'
assert s.count(anchor) == 1
pixels = ','.join(str(v) for v in rgba)
code = """
    #[cfg(target_os = "android")]
    {
        let id = egui::Id::new("deckcraft-approved-brand");
        let cached = p.ctx().data_mut(|data| data.get_temp::<egui::TextureHandle>(id));
        let texture = cached.unwrap_or_else(|| {
            let image = egui::ColorImage::from_rgba_unmultiplied([48, 48], &[PIXELS]);
            let texture = p.ctx().load_texture("deckcraft-approved-brand", image, egui::TextureOptions::LINEAR);
            p.ctx().data_mut(|data| data.insert_temp(id, texture.clone()));
            texture
        });
        p.image(texture.id(), r, Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)), Color32::WHITE);
        return;
    }
""".replace('PIXELS', pixels)
# The original desktop mark remains in the non-Android build only.
a = s.index(anchor) + len(anchor)
b = s.index('\n}\n', a)
s = s[:a] + code + '\n    #[cfg(not(target_os = "android"))]\n    {' + s[a:b] + '\n    }' + s[b:]
p.write_text(s)
