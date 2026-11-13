#!/usr/bin/env python3
"""Targeted CADCraft v0.19.0 Android-only UI compatibility overlay.

Apply only to a separately checked-out official Storytold CADCraft release.
Fail closed on upstream code changes; never modify other Craft apps.
"""
from pathlib import Path
import argparse
import shutil


def apply(source: Path) -> None:
    menu = source / "crates/ui-egui/src/menus.rs"
    original = menu.read_text(encoding="utf-8")
    anchor = "                // Titles first, so a hovered title can take over before any menu is drawn."
    if original.count(anchor) != 1:
        raise SystemExit("CADCraft menu_bar changed upstream: refusing unreviewed patch")
    if "CADCRAFT_ANDROID_CC_MENU_V2" in original:
        raise SystemExit("CADCraft Cc menu already patched: refusing duplicate")

    # The extra menu is Android-only. It does not change CADCraft's desktop menus,
    # native keyboard shortcuts, CAD command registry or reference menu tree.
    # Every menu action reuses an existing CADCraft command, rather than a fake row.
    injected = """                // CADCRAFT_ANDROID_CC_MENU_V2: native-icon compact menu.
                #[cfg(target_os = "android")]
                crate::cadcraft_android_wheel::cc_menu(app, ui, &mut clicked);
"""

    revised = original.replace(anchor, injected + anchor, 1)
    menu.write_text(revised, encoding="utf-8")
    assert revised.count("CADCRAFT_ANDROID_CC_MENU_V2") == 1
    assert "cadcraft_android_wheel::cc_menu" in revised
    print("PASS: native-Cc PhotoCraft-style compact CADCraft Android menu injected.")


def install_cadcraft_updater(reference: Path) -> None:
    """Replace reference-builder updater with a CADCraft-only in-app downloader.

    This affects solely the disposable CADCraft Actions checkout. The reference
    builder's unrelated versions must never be promoted to CADCraft users.
    """
    root = Path(__file__).resolve().parent
    java_source = root / "CadCraftUpdateCheck.java"
    if not java_source.is_file():
        raise SystemExit("Missing reviewed CADCraft Android updater")
    target = reference / "templates/android/UpdateCheck.java"
    original = target.read_text(encoding="utf-8")
    if 'private static final String BUILDER_VERSION = "__BUILDER_VERSION__"' not in original:
        raise SystemExit("Pinned Android builder updater changed; refusing unsafe replacement")
    reviewed = java_source.read_text(encoding="utf-8")
    if ("public static void checkNow(final Activity activity)" not in reviewed
            or "KosmosSG/artcraft-android/releases?" not in reviewed):
        raise SystemExit("CADCraft-only updater code validation failed")
    target.write_text(reviewed, encoding="utf-8")
    builder = reference / "lib/build-common.sh"
    source = builder.read_text(encoding="utf-8")
    needle = 'name = "android.permission.INTERNET"\n'
    if source.count(needle) != 1:
        raise SystemExit("Builder Android permission manifest anchor changed")
    source = source.replace(needle, needle + """
# Allow explicit user-approved APK installation from CADCraft's in-app downloader.
[[package.metadata.android.uses_permission]]
name = "android.permission.REQUEST_INSTALL_PACKAGES"
""", 1)
    builder.write_text(source, encoding="utf-8")
    print("PASS: CADCraft-only GitHub release checker and in-app APK download/installer staged.")



def patch_cadcraft_ui(source: Path) -> None:
    """Persist wheel customization through native prefs without changing desktop behavior."""
    lib = source / "crates/ui-egui/src/lib.rs"
    src = lib.read_text(encoding="utf-8")

    def replace_once(text: str, needle: str, replacement: str) -> str:
        if text.count(needle) != 1:
            raise SystemExit("CADCraft v0.19.0 UI anchor changed; refusing unreviewed patch: " + needle[:70])
        return text.replace(needle, replacement, 1)

    src = replace_once(src, "pub mod menus;\n",
        'pub mod menus;\n#[cfg(target_os = "android")]\npub mod cadcraft_android_wheel;\n')
    src = replace_once(src, "    pub last_pgp_dir: Option<String>,\n",
        """    pub last_pgp_dir: Option<String>,
    /// Android-only PhotoCraft-style CAD stylus wheel controls.
    pub cad_wheel_open: bool,
    pub cad_wheel_customize: bool,
    pub cad_wheel_actions: Vec<String>,
    pub cad_wheel_size: f32,
    pub cad_wheel_opacity: f32,
""")
    src = replace_once(src, "            last_pgp_dir: None,\n",
        """            last_pgp_dir: None,
            cad_wheel_open: false,
            cad_wheel_customize: false,
            cad_wheel_actions: vec![
                "select", "line", "circle", "ui.panel.layers", "pan", "trim", "redo", "undo",
            ].into_iter().map(str::to_string).collect(),
            cad_wheel_size: 1.0,
            cad_wheel_opacity: 1.0,
""")
    src = replace_once(src, "        prefs.to_string()\n",
        """        #[cfg(target_os = "android")]
        {
            prefs["cadWheelActions"] = json!(self.ui.cad_wheel_actions);
            prefs["cadWheelSize"] = json!(self.ui.cad_wheel_size);
            prefs["cadWheelOpacity"] = json!(self.ui.cad_wheel_opacity);
        }
        prefs.to_string()
""")
    src = replace_once(src, '        if let Some(keys) = v.get("shortcuts").filter(|k| k.is_object()) {\n',
        """        #[cfg(target_os = "android")]
        {
            if let Some(actions) = v.get("cadWheelActions").and_then(Value::as_array) {
                if actions.len() == 8
                    && actions.iter().all(|v| v.as_str().is_some_and(crate::cadcraft_android_wheel::valid_action))
                {
                    self.ui.cad_wheel_actions = actions.iter()
                        .filter_map(Value::as_str).map(str::to_string).collect();
                }
            }
            if let Some(size) = v.get("cadWheelSize").and_then(Value::as_f64) {
                if size.is_finite() { self.ui.cad_wheel_size = (size as f32).clamp(0.65, 1.45); }
            }
            if let Some(opacity) = v.get("cadWheelOpacity").and_then(Value::as_f64) {
                if opacity.is_finite() { self.ui.cad_wheel_opacity = (opacity as f32).clamp(0.35, 1.0); }
            }
        }
        if let Some(keys) = v.get("shortcuts").filter(|k| k.is_object()) {
""")
    src = replace_once(src, "        self.opening.show(ui.ctx());\n",
        """        #[cfg(target_os = "android")]
        crate::cadcraft_android_wheel::show(self, ui.ctx(), ui.max_rect());
        self.opening.show(ui.ctx());
""")
    lib.write_text(src, encoding="utf-8")

    template = Path(__file__).with_name("cadcraft_android_wheel.rs")
    if not template.is_file():
        raise SystemExit("Missing reviewed Android wheel module")
    dest = source / "crates/ui-egui/src/cadcraft_android_wheel.rs"
    if dest.exists():
        raise SystemExit("CADCraft wheel module exists upstream; refusing overwrite")
    dest.write_bytes(template.read_bytes())
    # JNI bridge is compiled only for the Android UI target; no desktop graph changes.
    cargo = source / "crates/ui-egui/Cargo.toml"
    manifest = cargo.read_text(encoding="utf-8")
    dep_section = """\n[target.'cfg(target_os = "android")'.dependencies]\njni = "0.22"\nndk-context = "0.1"\n"""
    if "ndk-context" in manifest or "[target.'cfg(target_os = \"android\")'.dependencies]" in manifest:
        raise SystemExit("CADCraft Android JNI dependencies changed; inspect manifest")
    cargo.write_text(manifest + dep_section, encoding="utf-8")
    print("PASS: 8 CAD actions, live size/opacity preview, native updater entry and saved prefs staged.")


def prepare_exact_icon(reference: Path, source: Path) -> None:
    """Generate the PNG and an embedded matching 64px Cc menu/wheel icon."""
    import subprocess
    from PIL import Image
    root = Path(__file__).resolve().parent.parent
    png = reference / "assets/cadcraft/cc-icon-1024.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "java", "-Djava.awt.headless=true",
        str(root / "tools/CadCraftIcon.java"),
        str(root / "assets/cadcraft/Cc-launcher-icon.svg"),
        str(png)
    ], check=True)
    icon = Image.open(png).convert("RGBA")
    if icon.getpixel((icon.width // 2, icon.height // 6))[:3] != (209, 49, 83):
        raise SystemExit("Cc icon is not exact #D13153: refusing Android build")
    raw = icon.resize((64, 64), Image.Resampling.LANCZOS).tobytes()
    if len(raw) != 64 * 64 * 4:
        raise SystemExit("Invalid CADCraft native menu icon")
    (source / "crates/ui-egui/src/cadcraft_cc_icon.rgba").write_bytes(raw)
    # Transparent cream glyph for the circular solid-pink center hub, preserving
    # the exact Cc letterforms (never place a rounded square inside the hub).
    work = icon.resize((256, 256), Image.Resampling.LANCZOS)
    pixels = work.load()
    glyph = Image.new("RGBA", work.size, (0, 0, 0, 0))
    gp = glyph.load()
    for y in range(256):
        for x in range(256):
            r, g, b, a = pixels[x, y]
            coverage = max(0, min(255, round((g - 49) * 255 / (228 - 49))))
            if coverage > 1 and a > 0:
                gp[x, y] = (243, 228, 231, round(a * coverage / 255))
    bbox = glyph.getbbox()
    if bbox is None:
        raise SystemExit("Cc center glyph extraction failed")
    glyph = glyph.crop(bbox)
    glyph.thumbnail((52, 39), Image.Resampling.LANCZOS)
    center = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    center.alpha_composite(glyph, ((64 - glyph.width) // 2, (64 - glyph.height) // 2))
    (source / "crates/ui-egui/src/cadcraft_cc_glyph.rgba").write_bytes(center.tobytes())
    from cadcraft_icon_fix import patch_reference
    patch_reference(reference)
    print("PASS: Cc menu/wheel artwork uses exact supplied red #D13153 and cream #F3E4E7.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path)
    args = p.parse_args()
    apply(args.source)
    patch_cadcraft_ui(args.source)
    prepare_exact_icon(args.reference, args.source)
    install_cadcraft_updater(args.reference)


if __name__ == "__main__":
    main()
