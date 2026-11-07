#!/usr/bin/env python3
"""DeckCraft v0.16.0 Android.1 — GridCraft-style Dk menu.

Runs only on a disposable builder checkout after the protected Android.17
overlay and prior DeckCraft updater/menu patches. Fails closed on source drift.
"""
import sys
from pathlib import Path

root=Path(sys.argv[1])
host=root/"source/deckcraft/crates/ui-egui/src/lib.rs"
source=host.read_text(encoding="utf-8")
start='                    let launcher = ui.menu_button("      ", |ui| {'
end='                    dialogs::paint_logo(ui.painter(), launcher.response.rect.shrink(2.0));'
assert source.count(start)==1, "Dk menu start anchor changed"
assert source.count(end)==1, "Dk icon paint anchor changed"
a=source.index(start)
b=source.index(end)
old=source[a:b]
for name in ("app.importFont","app.fontFolder","app.refreshFonts","app.checkUpdates","app.updateSettings"):
    assert old.count(name)==1, f"Owner-approved command missing or duplicated: {name}"
assert 'app.gpuDiagnostics' not in old, "Do not reintroduce duplicate Help diagnostics"
menu='''                    let launcher = ui.menu_button("      ", |ui| {
                        // GridCraft-style: compact left-aligned items and grouped submenus,
                        // not the oversized "DeckCraft · App Menu" heading.
                        ui.set_min_width(260.0);
                        for (label, command) in [
                            ("Import Fonts (TTF/OTF)…", "app.importFont"),
                            ("Choose Shared Font Folder…", "app.fontFolder"),
                            ("Refresh Shared Fonts", "app.refreshFonts"),
                        ] {
                            if ui.add_sized([260.0, 28.0], egui::Button::new("").left_text(label)).clicked() {
                                let _ = self.run(command, serde_json::json!({}));
                                ui.close();
                            }
                        }
                        ui.separator();
                        ui.menu_button("App Updates   ›", |ui| {
                            ui.set_min_width(235.0);
                            for (label, command) in [
                                ("Check for Updates…", "app.checkUpdates"),
                                ("Startup Update Settings…", "app.updateSettings"),
                            ] {
                                if ui.add_sized([235.0, 28.0], egui::Button::new("").left_text(label)).clicked() {
                                    let _ = self.run(command, serde_json::json!({}));
                                    ui.close();
                                }
                            }
                        });
                        ui.menu_button("Appearance   ›", |ui| {
                            if ui.add_sized([235.0, 28.0],
                                egui::Button::new("").left_text("Toggle Dark Theme")).clicked() {
                                let _ = self.run("view.dark", serde_json::json!({}));
                                ui.close();
                            }
                        });
                        ui.menu_button("Presentation Shortcuts   ›", |ui| {
                            ui.set_min_width(235.0);
                            ui.label("Ctrl+W · Close document");
                            ui.label("Ctrl+S · Save");
                            ui.label("Ctrl+Shift+S · Save As");
                            ui.label("Ctrl+C / X / V · Copy / Cut / Paste");
                            ui.label("Esc · Leave text editing");
                        });
                        ui.menu_button("About DeckCraft   ›", |ui| {
                            if ui.add_sized([235.0, 28.0],
                                egui::Button::new("").left_text("About DeckCraft")).clicked() {
                                let _ = self.run("app.about", serde_json::json!({}));
                                ui.close();
                            }
                        });
                    });
                    // Keep exactly the same owner-approved glossy Dk mark.
'''
host.write_text(source[:a]+menu+source[b:], encoding="utf-8")
assert 'dialogs::paint_logo(ui.painter(), launcher.response.rect.shrink(2.0));' in host.read_text()
print("PASS: GridCraft-style nested DeckCraft menu, font controls, updater, appearance and About preserved")
