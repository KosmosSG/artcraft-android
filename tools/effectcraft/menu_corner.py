"""EffectCraft-only Android brand-menu patch; fail closed on upstream drift."""
from pathlib import Path

ANCHOR = '''    if bresp.on_hover_text(tr("About EffectCraft")).clicked() {
        app.dialog = Some(Dialog::About);
    }'''

REPLACEMENT = '''    #[cfg(target_os = "android")]
    {
        // Keep the original header brand mark, but make its tap open Android tools.
        let _ = egui::Popup::menu(&bresp)
            .style(crate::widgets::menu_style)
            .show(|ui| {
                ui.set_min_width(250.0);
                for (title, key) in [
                    ("Import Fonts…", "artcraft.effectcraft.import_font"),
                    ("Select Font Folder…", "artcraft.effectcraft.select_fonts"),
                    ("Refresh Fonts Folder", "artcraft.effectcraft.refresh_fonts"),
                    ("Check for Updates", "artcraft.effectcraft.check_updates_requested"),
                    ("Startup Update Check", "artcraft.effectcraft.update_settings_requested"),
                ] {
                    if ui.button(title).clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new(key), true));
                        ui.close();
                    }
                }
                ui.separator();
                if ui.button("About EffectCraft").clicked() {
                    app.dialog = Some(Dialog::About);
                    ui.close();
                }
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
