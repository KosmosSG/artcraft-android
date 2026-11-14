#!/usr/bin/env python3
"""Android-only LightCraft v0.21.1 stylus wheel overlay.

Apply only to the checked-out, disposable official source copy AFTER the
published Android SAF, update UI and Lc menu compatibility patch. Never
rewrite the protected repository, official release, or signing artifacts.
Fails on source drift instead of silently editing the wrong API.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"STOP: LightCraft stylus wheel {label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    suite = args.suite.resolve()
    if source == suite or suite in source.parents:
        raise SystemExit("STOP: protected suite may not be rewritten")
    wheel_file = suite / "tools/lightcraft/android_stylus_wheel.rs"
    if not wheel_file.is_file():
        raise SystemExit("STOP: reviewed LightCraft stylus module missing")
    root = source / "crates/ui-egui/src"
    paths = {
        "lib": root / "lib.rs",
        "settings": root / "state/settings.rs",
        "frame": root / "app/frame.rs",
        "input": root / "app/input.rs",
        "menu": root / "menus/menubar.rs",
    }
    old = {k: p.read_text(encoding="utf-8") for k, p in paths.items()}
    new = dict(old)

    new["lib"] = once(new["lib"], "pub mod theme;\n",
        '#[cfg(target_os = "android")]\npub mod android_stylus_wheel;\npub mod theme;\n',
        "module registry")

    new["settings"] = once(new["settings"],
        "    pub favorite_themes: Vec<String>,",
        '    pub favorite_themes: Vec<String>,\n'
        '    /// Android-only stylus shortcut wheel configuration, saved in ui.json.\n'
        '    #[cfg(target_os = "android")]\n'
        '    pub stylus_wheel: crate::android_stylus_wheel::WheelPrefs,',
        "persistent preference field")
    new["settings"] = once(new["settings"],
        "            favorite_themes: Vec::new(),",
        '            favorite_themes: Vec::new(),\n'
        '            #[cfg(target_os = "android")]\n'
        '            stylus_wheel: crate::android_stylus_wheel::WheelPrefs::default(),',
        "persistent preference default")

    # Wheel input is captured before egui's ordinary photo canvas hit-test;
    # the visual ring is non-interactable to prevent selecting behind it.
    new["input"] = once(new["input"],
        "pub fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {\n",
        "pub fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {\n"
        "        #[cfg(target_os = \"android\")]\n"
        "        crate::android_stylus_wheel::capture(&self.ui.settings.stylus_wheel, ctx, raw);\n",
        "raw pointer shield")

    # Render last on a foreground egui Area in BOTH regular and fullscreen
    # presentations. This must run after the photo/canvas panels.
    target = "            panels::toast(self, &ctx);\n"
    if new["frame"].count(target) != 1:
        raise ValueError("STOP: expected one fullscreen toast hook")
    new["frame"] = new["frame"].replace(target,
        '            #[cfg(target_os = "android")]\n'
        '            crate::android_stylus_wheel::show(self, &ctx);\n' + target, 1)
    target = "        panels::toast(self, &ctx);\n"
    # Replace only the 8-space main hook, not the 12-space fullscreen one.
    lines = new["frame"].splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line == target]
    if len(matches) != 1:
        raise ValueError(f"STOP: main toast anchor count {len(matches)}")
    pos = matches[0]
    lines.insert(pos, '        #[cfg(target_os = "android")]\n        crate::android_stylus_wheel::show(self, &ctx);\n')
    new["frame"] = "".join(lines)

    # PhotoCraft's hierarchy: Lc > Stylus Wheel >
    # Enable Stylus Wheel (checkmark) / Stylus Wheel Customization.
    # Keep approved Appearance, updater and About commands unchanged.
    new["menu"] = once(new["menu"],
        '            if ui.button("About LightCraft").clicked() {',
        '''            ui.menu_button("Stylus Wheel", |ui| {
                let mut enabled = app.ui.settings.stylus_wheel.enabled;
                if ui.checkbox(&mut enabled, "Enable Stylus Wheel").changed() {
                    app.ui.settings.stylus_wheel.enabled = enabled;
                    crate::android_stylus_wheel::set_enabled_feedback(ui.ctx(), enabled);
                    ui.close();
                }
                if ui.button("Stylus Wheel Customization").clicked() {
                    crate::android_stylus_wheel::open_settings(ui.ctx());
                    ui.close();
                }
            });
            ui.separator();
            if ui.button("About LightCraft").clicked() {''',
        "PhotoCraft-style Lc Stylus Wheel submenu")

    if args.apply:
        for key, file in paths.items():
            file.write_text(new[key], encoding="utf-8")
        shutil.copyfile(wheel_file, root / "android_stylus_wheel.rs")
        print("Applied Android-only LightCraft stylus wheel, 1:1 preview, saved size/opacity/slots and foreground hover isolation.")
    else:
        print("PASS: LightCraft v0.21.1 Android stylus wheel anchors, preserved menu and preference interface.")
    print("No APK signing or publishing performed by this patch.")

if __name__ == "__main__":
    main()
