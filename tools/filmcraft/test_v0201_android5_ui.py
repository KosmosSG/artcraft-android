#!/usr/bin/env python3
"""Fast Android.5 FilmCraft UI/icon/menu regression gate (no Android build)."""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
wheel = (root / "tools/filmcraft/filmcraft_stylus_wheel.rs").read_text()
stage = (root / "tools/filmcraft/stage_v0201_wheel.py").read_text()
logo = (root / "tools/filmcraft/render_approved_fc_mark.py").read_text()
java = (root / "tools/filmcraft/FilmCraftActivity.features.v019.bottom-feedback.java.inc").read_text()

for name, marker in {
    "original Fc letterforms": 'include_bytes!("filmcraft_fc_logo.rgba")',
    "precise hub placement": 'vec2(54.0,34.0)*scale',
    "custom eight white icons": "fn paint_segment_icon(",
    "consistent anti-aliased paths": "egui::Shape::line",
    "single zoom-icon drawing": "p.circle_stroke(at(-3.0,-4.0),7.0*k,stroke)",
    "true button gate": "if button == 1 && self.enabled && !self.settings_open",
    "input isolation": "raw.events = filtered;",
    "PhotoCraft wheel dialog": 'Window::new("Stylus Wheel — Default")',
    "outside preview": 'egui::Id::new("filmcraft.wheel.preview")',
    "bottom-centre message": "vec2(350.0,31.0)",
    "100% size default": "const DEFAULT_SIZE: f32 = 1.0;",
    "85% opacity default": "const DEFAULT_OPACITY: f32 = 0.85;",
}.items():
    if marker not in wheel:
        raise SystemExit(f"STOP: missing FilmCraft Android.5 {name}: {marker}")
if "filmcraft_ui_egui::icons::paint(painter,rect,ICONS" in wheel:
    raise SystemExit("STOP: old blurry FilmCraft toolbar icons still on wheel")
if 'include_bytes!("filmcraft_fc_logo.rgba")' not in wheel or    "ORIGINAL_MASK_SHA256" not in logo:
    raise SystemExit("STOP: owner-approved launcher glyph no longer preserved")

for name, marker in {
    "one visible check-update menu": 'action(ui, "Check for Updates…", 4);',
    "hide download submenu action": 'HEADER_DOWNLOAD_LABEL',
    "hide install submenu action": 'HEADER_INSTALL_LABEL',
    "hide open release page": 'HEADER_RELEASE_ANCHOR',
    "fail closed hidden action check": "STOP: FilmCraft exposed redundant update action",
}.items():
    if marker not in stage:
        raise SystemExit(f"STOP: FilmCraft Android.5 menu staging missing {name}")
for marker in (
    "fcCheckForUpdates()", "fcDownloadVerifiedUpdate()",
    "fcInstallVerifiedDownload()", "fcVerifyArchive",
    "APK signing certificate differs from installed FilmCraft",
    "Download and verify the official APK?",
    "PhotoCraft-style single-entry updater",
    'if ("available".equals(updateState) || "test".equals(updateState))',
    'if ("com.artcraft.filmcraft.test".equals(getPackageName()))',
):
    if marker not in java:
        raise SystemExit(f"STOP: secure one-action update flow missing {marker}")
for term in ("fcWheelKey", "fcWheelMotion", "filmcraft_fc_logo.rgba"):
    if term not in stage:
        raise SystemExit(f"STOP: Android native pen bridge missing {term}")
print("PASS: approved original Fc glyph, clean white vector icon geometry, PhotoCraft wheel")
print("PASS: only Check for Updates stays visible; consent-based download/verify/install remains")
print("PASS: .test signature/install guard, original PhotoCraft notification and pen activation")
