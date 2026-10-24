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
        let bytes = serde_json::to_vec(&app.session.active().unwrap().doc).unwrap();
        let reopened: deckcraft_model::Presentation = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(after, deckcraft_render::render_slide(&reopened, 0, &Default::default()).pixels);
        app.run("view.tabletTools", serde_json::json!({})).unwrap();
        let prefs = serde_json::to_vec(&app.ui).unwrap();
        let restored: UiState = serde_json::from_slice(&prefs).unwrap();
        assert!(restored.tablet_tools);
    }
}
''')
