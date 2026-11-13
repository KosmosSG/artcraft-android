#!/usr/bin/env python3
"""Fast FilmCraft Android.4 original Fc + PhotoCraft parity + in-app updater contract check.

No native build, production signing or private credentials.
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
wheel = (root/"tools/filmcraft/filmcraft_stylus_wheel.rs").read_text()
stage = (root/"tools/filmcraft/stage_v0201_wheel.py").read_text()
logo = (root/"tools/filmcraft/render_approved_fc_mark.py").read_text()
java = (root/"tools/filmcraft/FilmCraftActivity.features.v019.bottom-feedback.java.inc").read_text()

for name, term in {
    "100% size default": "const DEFAULT_SIZE: f32 = 1.0;",
    "85% opacity default": "const DEFAULT_OPACITY: f32 = 0.85;",
    "PhotoCraft size min/max": "0.75,1.25",
    "PhotoCraft opacity min/max": "0.60,1.0",
    "eight alternate gray segments": "slot%2==0",
    "native FilmCraft toolbar glyphs": "filmcraft_ui_egui::icons::paint",
    "owner approved original Fc glyph": 'include_bytes!("filmcraft_fc_logo.rgba")',
    "photo dialog title": 'Window::new("Stylus Wheel — Default")',
    "outside dialog preview": 'egui::Id::new("filmcraft.wheel.preview")',
    "no unconditional opening": "if self.open && !self.settings_open",
    "pen-button hardware gate": "if button == 1 && self.enabled && !self.settings_open",
    "pointer isolation before editor": "raw.events = filtered;",
    "photocraft 1.9s toast": "Duration::from_millis(1900)",
    "photocraft fading toast": "Duration::from_millis(500)",
    "photocraft bottom notification": "vec2(350.0,31.0)",
}.items():
    if term not in wheel:
        raise SystemExit(f"STOP: FilmCraft wheel parity contract missing {name}: {term}")
for marker in (
    "filmcraft.stylus.menu.enabled", "HEADER_DOWNLOAD_LABEL",
    "HEADER_INSTALL_LABEL", "fcWheelMotion", "fcWheelKey",
    'Path(__file__).with_name("fc-original-launcher-mask.b64")',
    'filmcraft_fc_logo.rgba',
):
    if marker not in stage:
        raise SystemExit(f"STOP: FilmCraft staging bridge missing {marker}")
if "ORIGINAL_MASK_SHA256" not in logo or "destination.write_bytes(out.tobytes())" not in logo:
    raise SystemExit("STOP: approved Fc raster generation not checked")
for method in ("fcCheckForUpdates", "fcDownloadVerifiedUpdate",
               "fcInstallVerifiedDownload", "fcFileSha256", "fcVerifyArchive",
               "fcStartupUpdatesEnabled", "canRequestPackageInstalls",
               "DownloadManager"):
    if method not in java:
        raise SystemExit(f"STOP: in-app updater missing {method}")
if '!"com.artcraft.filmcraft.test".equals(getPackageName())' not in java:
    raise SystemExit("STOP: production-only default startup checks missing")
if 'if ("com.artcraft.filmcraft.test".equals(getPackageName()))' not in java:
    raise SystemExit("STOP: test package may accidentally try updating production")
if "APK signing certificate differs from installed FilmCraft" not in java:
    raise SystemExit("STOP: updater lost certificate comparison")
print("PASS: FilmCraft PhotoCraft wheel dialog, dual-tone, 100/85 defaults, toast")
print("PASS: Magic-Pencil hover/button isolation and checksum-verified user Fc glyph")
print("PASS: verified in-app APK download/install, startup checks on production only")
