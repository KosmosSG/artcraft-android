#!/usr/bin/env python3
"""Install a GridCraft-only staging hook in an isolated builder checkout.

This is intentionally not a general change to the suite's main build script:
the GitHub candidate workflow checks out the pinned reference as ./builder,
then invokes this installer ONLY in that disposable workspace.
"""
import argparse
from pathlib import Path
import shutil

TRIGGER = '    (staging_dir / "src" / "lib.rs").write_text(entry)'
MARKER = 'GRIDCRAFT_OVERLAY_HOOK_V1'
SNIPPET = '''    # GRIDCRAFT_OVERLAY_HOOK_V1: GridCraft only, never other apps.
    if app == "gridcraft":
        import runpy
        runpy.run_path(str(root / "tools/gridcraft_android/overlay.py"),
                       init_globals={"staging_dir": staging_dir, "package_name": package_name, "root": root})
'''

def stage_trackpad_primary_button(builder: Path):
    """Fix dropped trackpad click+drag in a disposable GridCraft-only winit copy.

    The pinned Android winit adaptor checked action_button() for ACTION_DOWN
    and ACTION_UP. Android only defines action_button() for BUTTON_PRESS/RELEASE,
    so physical primary clicks could disappear while cursor hover still worked.
    Keep touch events, scroll axes and nonprimary-button handling unchanged.
    """
    source_file = builder / "vendor/winit/src/platform_impl/android/mod.rs"
    if not source_file.is_file():
        raise RuntimeError("Pinned Android winit mouse adapter missing")
    source = source_file.read_text()
    anchor = "                                    if motion_event.action_button() != Button::Primary {\n                                        button_sent = true;\n                                    } else {\n                                        button_sent = true;\n                                        callback("
    replacement = "                                    // GRIDCRAFT_ANDROID_TRACKPAD_PRIMARY_V1:\n                                    // Android getActionButton() is undefined on ordinary\n                                    // ACTION_DOWN / ACTION_UP. Those are the primary\n                                    // trackpad/mouse clicks, not secondary-button actions.\n                                    // Keep ACTION_POINTER_* restricted to explicit primary.\n                                    let primary = matches!(\n                                        motion_event.action(),\n                                        MotionAction::Down | MotionAction::Up | MotionAction::Cancel\n                                    ) || motion_event.action_button() == Button::Primary;\n                                    button_sent = true;\n                                    if primary {\n                                        callback("
    if source.count(anchor) != 1 or "GRIDCRAFT_ANDROID_TRACKPAD_PRIMARY_V1" in source:
        raise RuntimeError("Pinned winit trackpad event translation changed; manual review required")
    patched = source.replace(anchor, replacement, 1)
    if patched.count("GRIDCRAFT_ANDROID_TRACKPAD_PRIMARY_V1") != 1:
        raise RuntimeError("Trackpad input fix missing from isolated winit adapter")
    source_file.write_text(patched)


def stage_candidate_android_version(builder: Path):
    """Set only GridCraft candidate/production Android versionName, preserving versionCode."""
    generator = builder / "lib/android_project.py"
    source = generator.read_text()
    anchor = '        build_gradle(android_meta["package"], min_sdk, target_sdk, code, version)'
    if source.count(anchor) != 1 or "GRIDCRAFT_ANDROID_VERSION_NAME_V1" in source:
        raise RuntimeError("Pinned Android Gradle generator changed; versionName needs review")
    revised = source.replace(anchor,
        '        # GRIDCRAFT_ANDROID_VERSION_NAME_V1: app-info display only; keep upstream semver.\n'
        '        build_gradle(android_meta["package"], min_sdk, target_sdk, code,\n'
        '                     "0.19.1-android.3-test" if app == "gridcraft"\n'
        '                     and version == "0.19.1"\n'
        '                     and android_meta["package"] == "com.artcraft.gridcraft.candidate3"\n'
        '                     else "0.16.1-android.3" if app == "gridcraft"\n'
        '                     and version == "0.16.1"\n'
        '                     and android_meta["package"] in ("com.artcraft.gridcraft.candidate", "com.artcraft.gridcraft")\n'
        '                     else version)', 1)
    compile(revised, str(generator), "exec")
    generator.write_text(revised)


def install(builder: Path, additions: Path):
    builder = builder.resolve()
    additions = additions.resolve()
    source = builder / "lib/build-common.sh"
    if not source.is_file() or not (builder / "build.sh").is_file():
        raise RuntimeError("Not an ArtCraft Android builder checkout")
    if builder == Path.cwd().resolve():
        raise RuntimeError("Refusing to modify the checked-out repository; provide a disposable builder directory")
    text = source.read_text()
    if MARKER in text:
        raise RuntimeError("Overlay hook already installed; refusing duplicate patch")
    if text.count(TRIGGER) != 1:
        raise RuntimeError("Builder generator changed; manual review needed before modifying it")
    required = ("if saf:", "GridCraftActivity", "mod ime_bridge;", "system_fonts::install_system_fonts(ui.ctx());")
    if any(item not in text for item in required):
        raise RuntimeError("Pinned builder lacks GridCraft SAF or font/keyboard infrastructure")
    for file in ("overlay.py", "gridcraft_tools.rs", "GridCraftJavaMethods.java.inc", "GridCraftNativeMenu.rs.inc"):
        if not (additions / file).is_file():
            raise RuntimeError(f"Missing reviewed enhancement source {file}")
    dest = builder / "tools/gridcraft_android"
    if dest.exists():
        raise RuntimeError("A GridCraft overlay directory already exists; refusing overwrite")
    # Patch only the pinned GridCraft checkout, never the suite or other apps.
    # Its existing title bar provides a native anchored menu; the generated
    # Android shell handles Java actions through egui Context data on next frame.
    ribbon = builder / "source/gridcraft/crates/ui-egui/src/ribbon.rs"
    native_menu = (additions / "GridCraftNativeMenu.rs.inc").read_text()
    menu_marker = "GRIDCRAFT_ANDROID_NATIVE_MENU_V1"
    if native_menu.count(menu_marker) != 1 or 'ui.menu_button("GridCraft Tools"' not in native_menu:
        raise RuntimeError("GridCraft top menu contract missing")
    # Read-only source audit downloads only the builder, not upstream sources.
    # In that limited audit checkout we still install the safe staging hook.
    # The real candidate build always checks out pinned GridCraft beforehand;
    # fail there if the ribbon is missing or its API changed.
    # The latest official source split title bar, home fonts and binding state
    # into independent modules; reusing v0.11 string replacements would corrupt it.
    upstream_manifest = builder / "source/gridcraft/Cargo.toml"
    source_version = None
    if upstream_manifest.is_file():
        import tomllib
        source_version = tomllib.loads(upstream_manifest.read_text())["workspace"]["package"]["version"]
        if source_version not in ("0.11.1", "0.15.0", "0.16.1", "0.18.0", "0.19.1"):
            raise RuntimeError(f"Unreviewed GridCraft upstream source version: {source_version}")
    if source_version == "0.19.1":
        # Enforce EXACT reviewed source, rather than accepting any ref with 0.18.0 metadata.
        import subprocess
        checked = subprocess.check_output(
            ["git", "-C", str(builder / "source/gridcraft"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if checked != "476448d7d9f3a5f8e93fcf7d98b47fd52293fe7f":
            raise RuntimeError("GridCraft 0.19.1 source commit mismatch: " + checked)
    if source_version in ("0.15.0", "0.16.1", "0.18.0", "0.19.1"):
        import runpy
        port_script = Path(__file__).with_name("port_v0150_ui.py")
        port = runpy.run_path(str(port_script))
        port["stage"](builder / "source/gridcraft")
        save_port = runpy.run_path(str(Path(__file__).with_name("port_v0150_save_dcs.py")))
        save_port["port"](builder / "source/gridcraft")
        selection_port = runpy.run_path(str(Path(__file__).with_name("port_v0150_touch_selection.py")))
        selection_port["port"](builder / "source/gridcraft")
        print("v0.15.0 menu/font, D/C/S, Esc, acknowledged SAF and Android touch-selection sources staged")
    else:
        if ribbon.is_file():
            ribbon_source = ribbon.read_text()
            menu_anchor = '            let more = icon_button(ui, Icon::More, t.text_dim, "More commands", vec2(26.0, ch));'
            if ribbon_source.count(menu_anchor) != 1 or menu_marker in ribbon_source:
                raise RuntimeError("Pinned GridCraft title bar changed or menu already inserted; manual review needed")
            patched_ribbon = ribbon_source.replace(menu_anchor, native_menu + menu_anchor, 1)
            # GRIDCRAFT_ANDROID_FONT_COMBO_V1: the official GridCraft font scanner
            # already exposes families(), but this pinned v0.11.1 ribbon mistakenly
            # uses just the 17 built-in FONTS strings. Use the discovered catalog.
            combo_old = '    let items: Vec<(&str, String)> = FONTS.iter().map(|f| (*f, f.to_string())).collect();'
            combo_new = ('    // GRIDCRAFT_ANDROID_FONT_COMBO_V1: include scanned user-installed fonts.\n'
                         '    let available = crate::fonts::families();\n'
                         '    let items: Vec<(&str, String)> = available.iter()\n'
                         '        .map(|f| (f.as_str(), f.clone())).collect();')
            if patched_ribbon.count(combo_old) != 1 or "GRIDCRAFT_ANDROID_FONT_COMBO_V1" in patched_ribbon:
                raise RuntimeError("Pinned GridCraft font dropdown changed; manual review required")
            patched_ribbon = patched_ribbon.replace(combo_old, combo_new, 1)
            ribbon.write_text(patched_ribbon)
        elif (builder / "source/gridcraft").exists():
            raise RuntimeError("GridCraft checkout exists but the expected ribbon file is missing")
        # Official GridCraft's catalog scans its HOME fonts before the UI font
        # dropdown is populated (OnceLock). The system-font directory in HOME
        # is a symlink, so imported files must use a separate HOME folder.
        fonts = builder / "source/gridcraft/crates/ui-egui/src/fonts.rs"
        if fonts.is_file():
            scanned = fonts.read_text()
            home_font_anchor = '                dirs.push(h.join(".local/share/fonts"));'
            if scanned.count(home_font_anchor) != 1 or "GRIDCRAFT_ANDROID_IMPORTED_FONTS_V1" in scanned:
                raise RuntimeError("GridCraft font catalog changed; manual review required")
            scanned = scanned.replace(
                home_font_anchor,
                home_font_anchor + '\n'
                + '                // GRIDCRAFT_ANDROID_IMPORTED_FONTS_V1: Android internal HOME is shared with Java SAF.\n'
                + '                dirs.push(h.join("ArtCraft-Fonts/artcraft-imported"));\n                dirs.push(h.join("ArtCraft-Fonts/artcraft-shared"));',
                1
            )
            import runpy
            patch = runpy.run_path(str(additions / "font_catalog_patch.py"))
            scanned = patch["patch_catalog"](scanned)
            fonts.write_text(scanned)
            lib = fonts.with_name("lib.rs")
            lib.write_text(patch["patch_app"](lib.read_text()))
        elif (builder / "source/gridcraft").exists():
            raise RuntimeError("Pinned GridCraft font catalog missing")

    # Owner-approved icon: use uploaded Gc tile for legacy launcher pixels,
    # but separate lime letters from the dark-green background for Android's
    # adaptive foreground. This avoids Android double-masking a rounded tile.
    # Fail closed on unexpected image SHA, source, or generic builder changes.
    icon_script = builder / "lib/app_icons.py"
    icon_source = icon_script.read_text()
    icon_hook = '    foreground = _foreground(Image, stripped)'
    replacement = '''    # GRIDCRAFT_USER_ADAPTIVE_ICON_V2
    if app == "gridcraft":
        import hashlib
        if hashlib.sha256(source.read_bytes()).hexdigest() != "e35af23c45ee75e1e026374c7b2458ac9f616cc82ffe39465f9c0ad3f3aeb7b2":
            raise RuntimeError("GridCraft user Gc image mismatch")
        from PIL import ImageChops
        # The supplied tile has red=0 on the green background and red=171 on
        # the Gc lettering. Reconstruct only the antialiased lettering alpha.
        shade = pristine.getchannel("R").point(lambda r: min(255, round(r * 255 / 171)))
        alpha = ImageChops.multiply(shade, pristine.getchannel("A"))
        lettering = Image.new("RGBA", pristine.size, (171, 232, 128, 0))
        lettering.putalpha(alpha)
        bounds = lettering.getchannel("A").getbbox()
        if not bounds:
            raise RuntimeError("GridCraft user Gc lettering is missing")
        foreground = _foreground(Image, lettering.crop(bounds))
        # GRIDCRAFT_GC_SAFE_PADDING_V1: reserve more visible breathing room
        # inside HONOR adaptive circle/squircle masks; original lettering was
        # almost touching the launcher edge on device.
        inset_px = round(CANVAS_PX * 0.78)
        inset_layer = foreground.resize((inset_px, inset_px), Image.Resampling.LANCZOS)
        foreground = Image.new("RGBA", (CANVAS_PX, CANVAS_PX), (0, 0, 0, 0))
        foreground.alpha_composite(
            inset_layer, ((CANVAS_PX - inset_px) // 2, (CANVAS_PX - inset_px) // 2)
        )
        color = "#006818"
    else:
        foreground = _foreground(Image, stripped)'''
    if icon_source.count(icon_hook) != 1:
        raise RuntimeError("Pinned adaptive icon generator changed")
    icon_source = icon_source.replace(icon_hook, replacement, 1)
    # Legacy density surfaces use the uploaded PNG, not a second padded and
    # masked raster. The Gc logo is already rounded exactly as the user wants.
    legacy_hook = '    _write_legacy(source, pristine, res_dir)'
    legacy = '''    # GRIDCRAFT_USER_LEGACY_ICON_V2: preserve user's Gc lettering with extra
    # spacing, instead of the old edge-to-edge source PNG.
    _write_legacy(source, pristine, res_dir)
    if app == "gridcraft":
        for density, size in DENSITIES.items():
            inset = max(1, round(size * 0.82))
            # Transparent margins avoid a second rounded-square mask.
            tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            art = pristine.resize((inset, inset), Image.Resampling.LANCZOS)
            tile.alpha_composite(art, ((size - inset) // 2, (size - inset) // 2))
            tile.save(res_dir / f"mipmap-{density}" / "ic_launcher.png")'''
    if icon_source.count(legacy_hook) != 1:
        raise RuntimeError("Pinned legacy icon generator changed")
    icon_script.write_text(icon_source.replace(legacy_hook, legacy, 1))
    # v0.15 adds an acknowledged SAF callback ONLY to the GridCraft generated
    # builder recipe, never the original product's permanent-signing paths.
    # It is a source transformation: the real Rust/Java launch is still unbuilt.
    if source_version in ("0.15.0", "0.16.1", "0.18.0", "0.19.1"):
        import runpy
        saf_patch = runpy.run_path(str(Path(__file__).with_name("port_v0150_builder_saf.py")))
        text = saf_patch["transform"](text)
    # Do not touch other source apps, keys, adapters or .github workflows.
    dest.mkdir(parents=True)
    for item in ("overlay.py", "gridcraft_tools.rs", "gridcraft_stylus_wheel.rs", "GridCraftJavaMethods.java.inc", "GridCraftSafeUpdater.java.inc"):
        shutil.copyfile(additions / item, dest / item)
    # All generated files (Cargo.toml, Java Activity, Rust lib.rs) must exist first.
    # Inject immediately AFTER the generator writes lib.rs, before its
    # atomic staging-directory rename publishes the Android launcher.
    if source_version in ("0.15.0", "0.16.1", "0.18.0", "0.19.1"):
        stage_trackpad_primary_button(builder)
        stage_candidate_android_version(builder)
    source.write_text(text.replace(TRIGGER, TRIGGER + "\n" + SNIPPET, 1))
    print("Installed isolated GridCraft native top Tools menu and Android source overlay.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path, help="Disposable builder checkout, e.g. ./builder")
    opts = parser.parse_args()
    install(opts.builder, Path(__file__).resolve().parent / "android_addons")
