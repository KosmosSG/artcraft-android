#!/usr/bin/env python3
"""FilmCraft-only generated Android shell overlay; refuses unexpected templates.

No shared templates, official source, keystores or other apps are mutated.
Run only for APP=filmcraft after the generic launcher has been generated.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def require_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected one stable source anchor, found {source.count(old)}")
    return source.replace(old, new, 1)


def patch_text(rust: str, java: str, manifest: str, java_overlay: str) -> tuple[str, str, str]:
    if 'struct AndroidShell {' not in rust or 'fn android_main(' not in rust:
        raise RuntimeError("Refusing to patch an unknown FilmCraft Android launcher")
    if 'public final class FilmCraftActivity extends GameActivity' not in java:
        raise RuntimeError("Expected FilmCraft's own SAF/IME Java activity")
    for bridge in ('safRequestOpen(', 'safRequestSave(', 'imeShow(', 'imeHide('):
        if bridge not in java:
            raise RuntimeError(f"FilmCraft SAF/IME bridge is missing: {bridge}")
    if 'package = "com.artcraft.filmcraft"' not in manifest:
        raise RuntimeError("FilmCraft package identity differs; inspect before porting features")
    if 'java_sources = "java"' not in manifest:
        raise RuntimeError("FilmCraft Java SAF bridge is missing")

    rust = require_once(
        rust, 'mod system_fonts;', 'mod system_fonts;\nmod filmcraft_features;',
        "Rust feature module")
    rust = require_once(
        rust, '    probe: InputProbe,',
        '    probe: InputProbe,\n    features: filmcraft_features::FilmcraftFeatures,',
        "Feature shell field")
    rust = require_once(
        rust, 'let ime = ime_bridge::ime::ImeBridge::new(&app);',
        'let ime = ime_bridge::ime::ImeBridge::new(&app);\n'
        '        let fc_features = filmcraft_features::FilmcraftFeatures::new(&app);',
        "Feature shell constructor")
    rust = require_once(
        rust, 'probe: InputProbe::default(),',
        'probe: InputProbe::default(), features: fc_features,',
        "Feature shell initialization")
    rust = require_once(
        rust, '        self.inner.logic(ctx, frame);',
        '        self.features.poll(ctx);\n        self.inner.logic(ctx, frame);',
        "Feature event polling")
    # Physical Escape must leave Android's text-edit focus without stealing other
    # keyboard shortcuts. Do not synthesize V/T: the upstream keymap owns them.
    rust = require_once(
        rust, '        self.ime.poll(raw);',
        '        self.ime.poll(raw);\n'
        '        if raw.events.iter().any(|e| matches!(e, egui::Event::Key { key: egui::Key::Escape, pressed: true, .. }))\n'
        '            && ctx.text_edit_focused() {\n'
        '            ctx.memory_mut(|memory| { if let Some(id) = memory.focused() { memory.surrender_focus(id); } });\n'
        '        }',
        "Android Escape text focus handoff")
    rust = require_once(
        rust, '        system_fonts::install_system_fonts(ui.ctx());',
        '        system_fonts::install_system_fonts(ui.ctx());\n'
        '        self.features.toolbar(ui);',
        "Docked FilmCraft controls")

    java = require_once(
        java,
        '        super.onActivityResult(requestCode, resultCode, data);',
        '        super.onActivityResult(requestCode, resultCode, data);\n'
        '        if (fcHandleActivityResult(requestCode, resultCode, data)) return;',
        "FilmCraft-specific SAF results")
    # The invisible Android IME EditText can retain focus after text entry, even
    # on physical keyboards. Clear that view's focus before dispatching Escape
    # through GameActivity so the editor receives its normal Escape event.
    # Never consume printable keys or bypass the upstream text-editor guards.
    if 'public boolean dispatchKeyEvent(' in java:
        raise RuntimeError("Review existing FilmCraft hardware key dispatch before overlay")
    java = require_once(
        java, 'public final class FilmCraftActivity extends GameActivity {',
        'public final class FilmCraftActivity extends GameActivity {\n'
        '    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {\n'
        '        if (event != null && event.getKeyCode() == android.view.KeyEvent.KEYCODE_ESCAPE\n'
        '                && event.getAction() == android.view.KeyEvent.ACTION_DOWN && imeWanted && event.getRepeatCount() == 0 && event.hasNoModifiers()) {\n'
        '            if (imeView != null) imeView.clearFocus();\n'
        '            imeHide();\n'
        '            // Never focus a different overlay or a container: GameActivity\'s\n'
        '            // actual SurfaceView owns the hardware-key dispatch.\n'
        '            android.view.View surface = fcFindNativeSurface(getWindow().getDecorView());\n'
        '            if (surface != null) {\n'
        '                surface.setFocusable(true);\n'
        '                surface.setFocusableInTouchMode(true);\n'
        '                surface.requestFocus();\n'
        '            }\n'
        '        }\n'
        '        return super.dispatchKeyEvent(event);\n'
        '    }\n'
        '    private android.view.View fcFindNativeSurface(android.view.View node) {\n'
        '        if (node == null || !node.isShown()) return null;\n'
        '        if (node instanceof android.view.SurfaceView) return node;\n'
        '        if (node instanceof android.view.ViewGroup) {\n'
        '            android.view.ViewGroup group = (android.view.ViewGroup) node;\n'
        '            for (int i = 0; i < group.getChildCount(); i++) {\n'
        '                android.view.View found = fcFindNativeSurface(group.getChildAt(i));\n'
        '                if (found != null) return found;\n'
        '            }\n'
        '        }\n'
        '        return null;\n'
        '    }\n',
        "Escape release Android IME focus")
    if 'private static final int FC_FONT_PICK' not in java:
        if not java.rstrip().endswith('}'):
            raise RuntimeError("Java activity is not a complete class")
        pos = java.rfind('}')
        java = java[:pos] + '\n' + java_overlay + '\n' + java[pos:]

    manifest = require_once(
        manifest,
        '[dependencies]\n',
        '[dependencies]\nfilmcraft-text = { path = "../../crates/text" }\n',
        "FilmCraft text registry dependency")
    if 'name = "android.permission.INTERNET"' not in manifest:
        first_permission = '[[package.metadata.android.uses_permission]]'
        if first_permission not in manifest:
            raise RuntimeError("FilmCraft manifest lacks the standard Android permission section")
        manifest = manifest.replace(
            first_permission,
            first_permission + '\nname = "android.permission.INTERNET"\n\n'
            + first_permission,
            1,
        )
    return rust, java, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("android_dir", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    overlay = Path(__file__).with_name("FilmCraftActivity.features.java.inc").read_text()
    if args.self_test:
        # A real staging fixture is not available in this branch-only audit.
        # These assertions check that the injected Java bridge matches the Rust caller.
        rust = Path(__file__).with_name("filmcraft_features.rs").read_text()
        assert 'filmcraft_text::fonts::add_font_data(bytes)' in rust
        for name in ("fcRequestFontImport", "fcRequestSharedFontFolder",
                     "fcRefreshSharedFonts", "fcFeaturePoll", "fcCheckForUpdates",
                     "fcStartupUpdatesEnabled", "fcSetStartupUpdatesEnabled",
                     "fcOpenUpdatePage", "fcFeatureFilesDir"):
            assert name in overlay, name
            assert name in rust, name
        assert 'filmcraft-v[0-9]+' in overlay
        # Exercise the actual replacement logic against a minimal TOML fixture.
        # Previously this silently replaced the first SAF permission instead of
        # appending a new entry, resulting in a duplicate `name` TOML key.
        import tomllib
        permissions = (
            '[[package.metadata.android.uses_permission]]\n'
            'name = "android.permission.READ_EXTERNAL_STORAGE"\n'
            'max_sdk_version = 32\n'
        )
        patched = permissions.replace(
            '[[package.metadata.android.uses_permission]]',
            '[[package.metadata.android.uses_permission]]\n'
            'name = "android.permission.INTERNET"\n\n'
            '[[package.metadata.android.uses_permission]]', 1)
        parsed = tomllib.loads(patched)
        names = [p['name'] for p in parsed['package']['metadata']['android']['uses_permission']]
        assert names == ['android.permission.INTERNET',
                         'android.permission.READ_EXTERNAL_STORAGE'], names
        print("FilmCraft overlay static API + permission TOML: PASS (not an APK test)")
        return

    if args.android_dir is None:
        parser.error("android_dir is required except with --self-test")
    project = args.android_dir.resolve()
    if project.name != "filmcraft-android":
        raise SystemExit("Refusing to change anything except generated filmcraft-android")
    if not (project / ".artcraft-android-builder-generated").is_file():
        raise SystemExit("Not a builder-owned generated FilmCraft crate")
    src = project / "src" / "lib.rs"
    java = project / "java/com/artcraft/filmcraft/FilmCraftActivity.java"
    manifest = project / "Cargo.toml"
    if not all(path.is_file() for path in (src, java, manifest)):
        raise SystemExit("Incomplete FilmCraft SAF launcher; no changes made")
    original = [file.read_text() for file in (src, java, manifest)]
    patched = patch_text(*original, overlay)
    # Only after all guards pass is any file written.
    for file, text in zip((src, java, manifest), patched):
        if file.read_text() != text:
            file.write_text(text)
    (project / "src" / "filmcraft_features.rs").write_text(
        Path(__file__).with_name("filmcraft_features.rs").read_text())
    print("FilmCraft native font/update integration overlaid on generated crate")


if __name__ == "__main__":
    main()
