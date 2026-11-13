#!/usr/bin/env python3
"""FilmCraft v0.20.1-only wheel staging; changes disposable CI builder, not published app.

The original v0.19 Android overlay remains the protected baseline. This
adds a separate foreground egui module and intercepting control surface.
All replacements are single-anchor and fail closed on upstream/builder drift.
"""
from pathlib import Path
import argparse

RUNTIME_ANCHOR = "    return rust, java, manifest\n"
RUNTIME_EXTRA = '''    rust = require_once(rust, "mod filmcraft_features;",
        "mod filmcraft_features;\\nmod filmcraft_stylus_wheel;", "Wheel module")
    rust = require_once(rust, "    features: filmcraft_features::FilmcraftFeatures,",
        "    features: filmcraft_features::FilmcraftFeatures,\\n    wheel: filmcraft_stylus_wheel::Wheel,",
        "Wheel shell field")
    rust = require_once(rust,
        "let fc_features = filmcraft_features::FilmcraftFeatures::new(&app);",
        "let fc_features = filmcraft_features::FilmcraftFeatures::new(&app);\\n"
        "        let fc_wheel = filmcraft_stylus_wheel::Wheel::new(fc_features.storage_dir());",
        "Wheel constructor")
    rust = require_once(rust, "features: fc_features,",
        "features: fc_features, wheel: fc_wheel,", "Wheel state")
    rust = require_once(rust, "        self.inner.ui(ui, frame);",
        "        self.inner.ui(ui, frame);\\n"
        "        if let Some(command) = self.wheel.show(ui.ctx()) {\\n"
        "            let _ = filmcraft_ui_egui::menus::invoke(\\n"
        "                &mut self.inner, ui.ctx(), command, serde_json::json!({}));\\n"
        "        }", "Wheel command routing")
'''
RUNTIME_WRITE_ANCHOR = '    print("FilmCraft native font/update integration overlaid on generated crate")'
RUNTIME_WRITE_REPLACE = '''    (project / "src" / "filmcraft_stylus_wheel.rs").write_text(
        Path(__file__).with_name("filmcraft_stylus_wheel.rs").read_text())
''' + RUNTIME_WRITE_ANCHOR
FEATURE_ANCHOR = "impl FilmcraftFeatures {\n"
FEATURE_ADD = FEATURE_ANCHOR + "    pub fn storage_dir(&self) -> Option<PathBuf> { self.app_dir.clone() }\n"
HEADER_ANCHOR = '                ui.menu_button("FilmCraft Shortcuts", |ui| {'
HEADER_ADD = '''                ui.menu_button("Stylus Wheel", |ui| {
                    if ui.button("Customize Stylus Wheel…")
                        .on_hover_cursor(egui::CursorIcon::PointingHand).clicked() {
                        ui.ctx().data_mut(|data| data.insert_temp(
                            egui::Id::new("filmcraft.stylus.settings.open"), true));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                });
''' + HEADER_ANCHOR


def replace_once(src: str, old: str, new: str, name: str) -> str:
    if src.count(old) != 1 or new in src:
        raise RuntimeError(f"STOP: FilmCraft {name} missing/ambiguous or patch already applied")
    return src.replace(old, new, 1)


def prepare(builder: Path, wheel: Path) -> None:
    if builder.name != "filmcraft-builder" or not (builder / "lib/build-common.sh").is_file():
        raise RuntimeError("STOP: expected disposable FilmCraft build checkout")
    if not wheel.is_file():
        raise RuntimeError("STOP: missing isolated FilmCraft wheel Rust module")
    runtime = builder / "tools/filmcraft/runtime_patch.py"
    feature = builder / "tools/filmcraft/filmcraft_features_v019_bottom_feedback.rs"
    header = builder / "source/filmcraft/crates/ui-egui/src/header.rs"
    for path in (runtime, feature, header):
        if not path.is_file():
            raise RuntimeError(f"STOP: missing FilmCraft reviewed source {path}")

    runtime_src = runtime.read_text()
    updated_runtime = replace_once(runtime_src, RUNTIME_ANCHOR,
        RUNTIME_EXTRA + RUNTIME_ANCHOR, "runtime wrapper hook")
    updated_runtime = replace_once(updated_runtime, RUNTIME_WRITE_ANCHOR,
        RUNTIME_WRITE_REPLACE, "wheel Rust copy")
    compile(updated_runtime, str(runtime), "exec")
    feature_src = replace_once(feature.read_text(), FEATURE_ANCHOR, FEATURE_ADD, "settings path")
    header_src = replace_once(header.read_text(), HEADER_ANCHOR, HEADER_ADD, "Fc menu")
    # Check all changes first; do not partially modify the builder on an anchor failure.
    runtime.write_text(updated_runtime)
    feature.write_text(feature_src)
    header.write_text(header_src)
    (builder / "tools/filmcraft/filmcraft_stylus_wheel.rs").write_bytes(wheel.read_bytes())
    print("PASS: separate FilmCraft stylus wheel wired to Fc menu, persisted prefs and commands")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        fixture = "before\\n" + RUNTIME_ANCHOR
        assert RUNTIME_EXTRA in replace_once(fixture, RUNTIME_ANCHOR,
            RUNTIME_EXTRA + RUNTIME_ANCHOR, "fixture")
        assert FEATURE_ADD in replace_once(FEATURE_ANCHOR, FEATURE_ANCHOR, FEATURE_ADD, "feature")
        try:
            replace_once("missing", HEADER_ANCHOR, HEADER_ADD, "negative")
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing header must fail closed")
        print("FilmCraft wheel staging guard self-test PASS")
        return
    if args.builder is None:
        parser.error("disposable builder path required")
    wheel = Path(__file__).with_name("filmcraft_stylus_wheel.rs")
    prepare(args.builder.resolve(), wheel)


if __name__ == "__main__":
    main()
