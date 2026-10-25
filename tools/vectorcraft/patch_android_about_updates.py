"""Android-only native About VectorCraft → Updates tab, matching LightCraft UI.

Mutates only the pinned VectorCraft v0.14.0 ui-egui checkout during APK staging.
The Android shell provides transient state and JNI I/O; upstream desktop builds
remain unchanged. This is a one-shot, fail-closed source patch.
"""
import argparse
from pathlib import Path

ORIGINAL_TABS = '[tl!("About"), tl!("Contributors"), tl!("Models")]'
ORIGINAL_MATCH = '''                2 => {
                    ui.set_width(660.0);
                    crate::credits::models_ui(ui);
                }
                _ => about_tab(app, ui),'''
PATCHED_MATCH = '''                2 => {
                    ui.set_width(660.0);
                    crate::credits::models_ui(ui);
                }
                #[cfg(target_os = "android")]
                3 => {
                    ui.set_width(490.0);
                    ui.heading("VectorCraft Updates");
                    let context = ui.ctx().clone();
                    let installed = context.data(|d| d.get_temp::<String>(
                        egui::Id::new("artcraft.vectorcraft.installed_version")))
                        .unwrap_or_else(|| env!("CARGO_PKG_VERSION").to_owned());
                    ui.label(format!("Installed Version: {installed}"));
                    let status = context.data(|d| d.get_temp::<String>(
                        egui::Id::new("artcraft.vectorcraft.update_status")))
                        .unwrap_or_else(|| "Select Check for Updates to query GitHub Releases.".to_owned());
                    ui.label(&status);
                    let checking = context.data(|d| d.get_temp::<bool>(
                        egui::Id::new("artcraft.vectorcraft.update_checking")))
                        .unwrap_or(false);
                    if checking { ui.spinner(); }
                    if ui.add_enabled(!checking, egui::Button::new("Check for Updates")).clicked() {
                        context.data_mut(|d| d.insert_temp(
                            egui::Id::new("artcraft.vectorcraft.check_updates_requested"), true));
                        context.request_repaint();
                    }
                    ui.separator();
                    ui.label("Update Channel");
                    let mut previews = context.data(|d| d.get_temp::<bool>(
                        egui::Id::new("artcraft.vectorcraft.include_preview")))
                        .unwrap_or(true);
                    let stable = ui.radio_value(&mut previews, false, "Stable Releases Only");
                    let all = ui.radio_value(&mut previews, true, "Stable + Preview Releases");
                    if stable.changed() || all.changed() {
                        context.data_mut(|d| {
                            d.insert_temp(egui::Id::new("artcraft.vectorcraft.preview_desired"), previews);
                            d.insert_temp(egui::Id::new("artcraft.vectorcraft.preview_changed"), true);
                        });
                        context.request_repaint();
                    }
                    ui.small("Preview releases may be untested; installing remains your choice.");
                    ui.separator();
                    let mut startup = context.data(|d| d.get_temp::<bool>(
                        egui::Id::new("artcraft.vectorcraft.startup_enabled")))
                        .unwrap_or(false);
                    if ui.checkbox(&mut startup, "Check for updates at startup").changed() {
                        context.data_mut(|d| {
                            d.insert_temp(egui::Id::new("artcraft.vectorcraft.startup_desired"), startup);
                            d.insert_temp(egui::Id::new("artcraft.vectorcraft.startup_changed"), true);
                        });
                        context.request_repaint();
                    }
                    ui.small("Off by default. Update checks never block vector editing.");
                    let page = context.data(|d| d.get_temp::<String>(
                        egui::Id::new("artcraft.vectorcraft.release_page")))
                        .filter(|url| url.starts_with(
                            "https://github.com/KosmosSG/artcraft-android/releases/tag/vectorcraft-v"));
                    if page.is_some() && ui.button("Open GitHub Release").clicked() {
                        context.data_mut(|d| d.insert_temp(
                            egui::Id::new("artcraft.vectorcraft.open_release_requested"), true));
                        context.request_repaint();
                    }
                    ui.small("VectorCraft-only GitHub Releases; updates require the original app signature.");
                }
                _ => about_tab(app, ui),'''

def insert_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"STOP: v0.14.0 {label} source anchor changed")
    return source.replace(old, new, 1)

def apply(builder: Path) -> None:
    about = builder / "source/vectorcraft/crates/ui-egui/src/dialogs/about.rs"
    s = about.read_text()
    s = insert_once(s, ORIGINAL_TABS,
        '[tl!("About"), tl!("Contributors"), tl!("Models"), tl!("Updates")]', "about tabs")
    s = insert_once(s, ORIGINAL_MATCH, PATCHED_MATCH, "About contents")
    s = s.replace("Tabs: About · Contributors · Models (the credits are compiled in, see `credits`).",
                  "Tabs: About · Contributors · Models · Android Updates (the credits are compiled in).")
    about.write_text(s)
    print("PASS: LightCraft-inspired native About → Updates UI patched for Android only")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("builder",type=Path)
    apply(p.parse_args().builder)
