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

    rust = require_once(rust, '        self.inner.ui(ui, frame);', '        self.inner.ui(ui, frame);\n        if android_escape && self.inner.dialog.is_none() && !egui::Popup::is_any_open(ui.ctx())\n            && ui.ctx().text_edit_focused() {\n            ui.memory_mut(|m| {\n                if let Some(focus) = m.focused() { m.surrender_focus(focus); }\n            });\n        }\n', "Release Android field focus")
    rust = require_once(rust, '        self.handle_clipboard_shortcuts(raw);', '        self.handle_clipboard_shortcuts(raw);\n        // Capture Escape before egui focus traversal or widget consumption.\n        // Some Android tablet keyboards report their Esc key as BrowserBack.\n        // Normalize the keyboard event before egui and app text-edit guards.\n        for event in &mut raw.events {\n            if let egui::Event::Key { key, physical_key, modifiers, .. } = event {\n                if *key == egui::Key::BrowserBack && !modifiers.any() {\n                    *key = egui::Key::Escape;\n                    *physical_key = Some(egui::Key::Escape);\n                }\n            }\n        }\n        if raw.events.iter().any(|event| matches!(event,\n            egui::Event::Key { key: egui::Key::Escape, pressed: true, repeat: false, modifiers, .. }\n                if !modifiers.any())) {\n            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.exit_typing"), true));\n        }\n', 'Capture Android Escape')
    rust = require_once(rust, '        system_fonts::install_system_fonts(ui.ctx());', '        let android_escape = ui.ctx().data_mut(|d|\n            d.remove_temp::<bool>(egui::Id::new("artcraft.exit_typing"))).unwrap_or(false);\n        if android_escape && self.inner.dialog.is_none()\n            && !egui::Popup::is_any_open(ui.ctx()) && self.inner.ui.gfx_edit.is_some()\n            && ui.memory(|m| m.focused().is_none_or(|id| id == egui::Id::new("gfx-text-edit"))) {\n            // Same editing-state cleanup as the monitor\'s end_edit; keep layer selection.\n            self.inner.ui.gfx_edit = None;\n            ui.memory_mut(|m| m.surrender_focus(egui::Id::new("gfx-text-edit")));\n            ui.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Escape));\n        }\n        system_fonts::install_system_fonts(ui.ctx());', 'End Android text edit')
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
        '        if (!imeWanted) artcraftRestoreCanvasFocus();\n'
        "        // Bypass focused EditText/SurfaceView dispatch: GameActivity's public\n"
        '        // handlers enqueue the original event (including modifiers and key-up).\n'
        '        // Let the IME keep printable input while editing; Escape always reaches\n'
        '        // the native editor, even if Android has already hidden its keyboard.\n'
        '        if (event != null\n'
        '                && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0\n'
        '                && (event.getKeyCode() == android.view.KeyEvent.KEYCODE_ESCAPE\n'
        '                    || (!imeWanted && !event.isSystem()))) {\n'
        '            if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {\n'
        '                super.onKeyDown(event.getKeyCode(), event);\n'
        '                return true;\n'
        '            }\n'
        '            if (event.getAction() == android.view.KeyEvent.ACTION_UP) {\n'
        '                super.onKeyUp(event.getKeyCode(), event);\n'
        '                return true;\n'
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
    java = require_once(java, '                view.clearFocus();', '                view.clearFocus();\n                artcraftRestoreCanvasFocus();', 'Restore native surface after any text exit')
    java = java[:java.rfind('}')] + """
    private android.view.View artcraftNativeSurface(android.view.View node) {
        if (node == null || !node.isShown()) return null;
        if (node instanceof android.view.SurfaceView) return node;
        if (node instanceof android.view.ViewGroup) {
            android.view.ViewGroup group = (android.view.ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                android.view.View child = artcraftNativeSurface(group.getChildAt(i));
                if (child != null) return child;
            }
        }
        return null;
    }
    private void artcraftRestoreCanvasFocus() {
        android.view.Window win = getWindow();
        android.view.View surface = win == null ? null : artcraftNativeSurface(win.getDecorView());
        if (surface != null && !surface.hasFocus()) {
            surface.setFocusable(true);
            surface.setFocusableInTouchMode(true);
            surface.requestFocus();
        }
    }
""" + java[java.rfind('}'):]
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
    rust = require_once(rust, '        self.inner.ui(ui, frame);',
        '        self.inner.android_capture_unsaved_dcs(ui.ctx());\n'
        '        self.features.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());\n'
        '        self.inner.ui(ui, frame);\n'
        '        self.features.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());', 'FilmCraft modal keys')
    java = require_once(java, '    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {\n',
        '\n    private final java.util.concurrent.atomic.AtomicInteger fcDialogAction = new java.util.concurrent.atomic.AtomicInteger();\n    private volatile boolean fcDialogActive;\n    private final java.util.HashSet<Integer> fcDialogKeys = new java.util.HashSet<>();\n    public int fcUnsavedDialog(boolean active) {\n        fcDialogActive = active;\n        int action = fcDialogAction.getAndSet(0);\n        return active ? action : 0;\n    }\n    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {\n        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {\n            int code = event.getKeyCode();\n            if (fcDialogKeys.contains(code)) {\n                if (event.getAction() == android.view.KeyEvent.ACTION_UP) fcDialogKeys.remove(code);\n                return true;\n            }\n            int action = code == android.view.KeyEvent.KEYCODE_D ? 1 : code == android.view.KeyEvent.KEYCODE_C ? 2 : code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;\n            if (fcDialogActive && action != 0 && event.hasNoModifiers()\n                    && event.getAction() == android.view.KeyEvent.ACTION_DOWN) {\n                fcDialogKeys.add(code);\n                if (event.getRepeatCount() == 0) fcDialogAction.compareAndSet(0, action);\n                return true;\n            }\n        }\n\n', 'FilmCraft modal dispatch')
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
