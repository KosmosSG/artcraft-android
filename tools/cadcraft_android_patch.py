#!/usr/bin/env python3
"""Targeted CADCraft v0.19.0 Android-only UI compatibility overlay.

Apply only to a separately checked-out official Storytold CADCraft release.
Fail closed on upstream code changes; never modify other Craft apps.
"""
from pathlib import Path
import argparse


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


def disable_reference_updater(template: Path) -> None:
    """Prevent the reference builder's global updater from advertising unrelated apps.

    Its Java version comparator checks the MostafaXS1 *builder* release rather than
    the installed CADCraft APK. It must not run automatically in this isolated test.
    The upstream manual CADCraft check remains available in the Cc menu.
    """
    text = template.read_text(encoding="utf-8")
    anchor = "    public static void start(final Activity activity) {"
    i = text.find(anchor)
    if i < 0:
        raise SystemExit("Reference Java updater changed: inspect before enabling a test build")
    first_brace = text.index("{", i)
    depth = 0
    end = None
    for j in range(first_brace, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end is None:
        raise SystemExit("Unbalanced reference Java updater start()")
    replacement = anchor + '\n        // CADCraft TEST ONLY: globally scoped builder updater disabled.\n    }'
    text = text[:i] + replacement + text[end:]
    template.write_text(text, encoding="utf-8")
    print("PASS: disabled unrelated builder-wide automatic update notifications in test APK.")



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
""")
    src = replace_once(src, "            last_pgp_dir: None,\n",
        """            last_pgp_dir: None,
            cad_wheel_open: false,
            cad_wheel_customize: false,
            cad_wheel_actions: vec![
                "select", "line", "circle", "ui.panel.layers", "pan", "trim", "redo", "undo",
            ].into_iter().map(str::to_string).collect(),
""")
    src = replace_once(src, "        prefs.to_string()\n",
        """        #[cfg(target_os = "android")]
        {
            prefs["cadWheelActions"] = json!(self.ui.cad_wheel_actions);
        }
        prefs.to_string()
""")
    src = replace_once(src, '        if let Some(keys) = v.get("shortcuts").filter(|k| k.is_object()) {\n',
        """        #[cfg(target_os = "android")]
        if let Some(actions) = v.get("cadWheelActions").and_then(Value::as_array) {
            if actions.len() == 8
                && actions.iter().all(|v| v.as_str().is_some_and(crate::cadcraft_android_wheel::valid_action))
            {
                self.ui.cad_wheel_actions = actions.iter()
                    .filter_map(Value::as_str).map(str::to_string).collect();
            }
        }
        if let Some(keys) = v.get("shortcuts").filter(|k| k.is_object()) {
""")
    src = replace_once(src, "        self.opening.show(ui.ctx());\n",
        """        #[cfg(target_os = "android")]
        crate::cadcraft_android_wheel::show(self, ui.ctx());
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
    print("PASS: 8-segment wheel, native CAD actions, menu customization and saved preferences staged.")


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
    disable_reference_updater(args.reference / "templates/android/UpdateCheck.java")


if __name__ == "__main__":
    main()
