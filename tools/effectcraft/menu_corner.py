"""EffectCraft-only Android brand-menu patch; fail closed on upstream drift."""
from pathlib import Path

ANCHOR = '''    if bresp.on_hover_text(tr("About EffectCraft")).clicked() {
        app.dialog = Some(Dialog::About);
    }'''

REPLACEMENT = '''    #[cfg(target_os = "android")]
    {
        // The existing Ec badge opens a compact, touch-friendly Android menu.
        // Keep the popup bounded so physical trackpad wheel gestures can scroll it.
        let _ = egui::Popup::menu(&bresp)
            .style(crate::widgets::menu_style)
            .show(|ui| {
                // Compact Ec popup: don't expand to the tablet's available width.
                ui.set_width(268.0);
                ui.set_min_width(252.0);
                ui.set_max_width(278.0);
                egui::ScrollArea::vertical()
                    .id_salt("effectcraft.android.ec_menu_scroll")
                    .max_height(236.0)
                    .auto_shrink([true, true])
                    .show(ui, |ui| {
                        for (title, key) in [
                            ("Import Fonts…", "artcraft.effectcraft.import_font"),
                            ("Select Font Folder…", "artcraft.effectcraft.select_fonts"),
                            ("Refresh Fonts Folder", "artcraft.effectcraft.refresh_fonts"),
                        ] {
                            if ui.button(title).clicked() {
                                ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new(key), true));
                                ui.close();
                            }
                        }
                        ui.separator();
                        for (title, key) in [
                            ("Check for Updates", "artcraft.effectcraft.check_updates_requested"),
                            ("Startup Update Check", "artcraft.effectcraft.update_settings_requested"),
                        ] {
                            if ui.button(title).clicked() {
                                ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new(key), true));
                                ui.close();
                            }
                        }
                        ui.separator();
                        // Like GridCraft: one nested Appearance menu, no extra toolbar.
                        // Use EffectCraft's existing persistent appearance preferences.
                        ui.menu_button("Appearance", |ui| {
                            ui.set_min_width(165.0);
                            let current = app.session.prefs.appearance.appearance_mode.clone();
                            for (label, value) in [
                                ("System", "auto"),
                                ("Light", "light"),
                                ("Dark", "dark"),
                            ] {
                                if ui.selectable_label(current == value, label).clicked() {
                                    if let Err(error) = app.set_pref(
                                        "appearance.appearanceMode",
                                        serde_json::json!(value),
                                    ) {
                                        app.ui.status = error;
                                    } else {
                                        app.apply_prefs(ui.ctx());
                                    }
                                    ui.close();
                                }
                            }
                        });
                        ui.separator();
                        if ui.button("About EffectCraft").clicked() {
                            app.dialog = Some(Dialog::About);
                            ui.close();
                        }
                    });
            });
    }
    #[cfg(not(target_os = "android"))]
    if bresp.on_hover_text(tr("About EffectCraft")).clicked() {
        app.dialog = Some(Dialog::About);
    }'''

def patch_header(upstream: Path) -> Path:
    path = Path(upstream) / "crates/ui-egui/src/header.rs"
    source = path.read_text(encoding="utf-8")
    if source.count(ANCHOR) != 1 or "artcraft.effectcraft.select_fonts" in source:
        raise RuntimeError("STOP: EffectCraft v0.21 brand icon hook drift")
    path.write_text(source.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    return path
