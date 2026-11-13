#!/usr/bin/env python3
"""WordCraft-only Android font persistence overlay for the audited pinned builder.

This script mutates the ephemeral builder checkout on CI, never suite main or upstream.
It intentionally does NOT claim shared SAF font folders or an in-app updater exist.
"""
from pathlib import Path
import sys


def exactly_once(text: str, old: str, new: str, purpose: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WordCraft integration stopped: {purpose} anchor occurs {count} times")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_builder.py <isolated pinned builder checkout>")
    root = Path(sys.argv[1]).resolve()
    source = root / "lib" / "build-common.sh"
    if not (root / "lib" / "app_icons.py").is_file() or not source.is_file():
        raise SystemExit("The pinned reference Android builder is incomplete")
    from patch_unsaved_dcs import apply
    from font_paths import patch_android_font_paths
    apply(root / "source" / "wordcraft")
    fonts = root / "templates" / "android" / "system_fonts.rs"
    fonts.write_text(patch_android_font_paths(fonts.read_text()))
    original = source.read_text(encoding="utf-8")
    patched = original

    # The engine already handles font.add from the Home / Font command. Its
    # Android open_async + inbox path already detects TTF/OTF and dispatches
    # font.add bytes. Add WordCraft's own FontDb as a direct launcher dependency
    # so imported fonts can be saved/restored in a private persistent folder.
    patched = exactly_once(
        patched,
        "    manifest = f'''[package]",
        "    font_dep = 'wordcraft-fonts = { path = \"../../crates/fonts\" }\\n' if app == \"wordcraft\" else ''\n"
        "    manifest = f'''[package]",
        "add WordCraft-only dependency",
    )
    patched = exactly_once(
        patched,
        "{serde_dep}{rfd_dep}{cpal_dep}{host_dep}",
        "{serde_dep}{rfd_dep}{cpal_dep}{host_dep}{font_dep}",
        "add WordCraft font DB dependency to generated launcher",
    )
    # Main entry initializes the DB before WordApp is constructed, just as the
    # official WordCraft desktop app initializes its user-font folder on startup.
    font_init = (
        '        if app == "wordcraft":\n'
        '            saf_setup = (\n'
        '                \'    if let Some(root) = app_data_dir(&android_app) {\\n\'\n'
        '                \'        let (loaded, skipped) = wordcraft_fonts::FontDb::global().load_user_fonts(&root.join("fonts"));\\n\'\n'
        '                \'        log::info!("WordCraft: restored {} saved fonts, {} skipped", loaded.len(), skipped.len());\\n\'\n'
        '                \'        for (file, reason) in skipped { log::warn!("WordCraft: skipped font {}: {}", file, reason); }\\n\'\n'
        '                \'    }\\n\'\n'
        '            ) + saf_setup\n'
    )
    patched = exactly_once(
        patched,
        '        inner_decl = "let mut inner" if post_construct else "let inner"',
        font_init + '        inner_decl = "let mut inner" if post_construct else "let inner"',
        "load saved WordCraft fonts before UI construction",
    )
    # WordCraft uses Android document-scoped SAF intents, not blanket storage.
    patched = exactly_once(
        patched,
        '    (staging_dir / "Cargo.toml").write_text(manifest)',
        '    if app == "wordcraft":\n'
        '        manifest = manifest.replace(\'[[package.metadata.android.uses_permission]]\\nname = "android.permission.MANAGE_EXTERNAL_STORAGE"\\n\', "")\n'
        '    (staging_dir / "Cargo.toml").write_text(manifest)',
        "omit MANAGE_EXTERNAL_STORAGE for WordCraft",
    )
    patched = exactly_once(
        patched,
        '    (staging_dir / "src" / "lib.rs").write_text(entry)',
        '    if app == "wordcraft":\n'
        '        storage_prompt = "    saf_bridge.request_storage_permission();\\n"\n'
        '        if entry.count(storage_prompt) != 1:\n'
        '            raise SystemExit("WordCraft SAF storage prompt anchor changed")\n'
        '        entry = entry.replace(storage_prompt, "", 1)\n'
        '    (staging_dir / "src" / "lib.rs").write_text(entry)',
        "avoid Android all-files access prompt in WordCraft",
    )
    # Add an isolated Java Activity extension. The source builder and other apps
    # never receive these methods, permissions, or saved preferences.
    java_template = root / "templates" / "android" / "SafActivity.java"
    java = java_template.read_text(encoding="utf-8")
    java = exactly_once(
        java,
        "        super.onActivityResult(requestCode, resultCode, data);\n",
        "        super.onActivityResult(requestCode, resultCode, data);\n"
        "        if (requestCode == WC_FONT_IMPORT_REQUEST) {\n"
        "            wcHandleImportedFonts(resultCode, data);\n"
        "            return;\n"
        "        }\n"
        "        if (requestCode == WC_FONT_FOLDER_REQUEST) {\n"
        "            wcHandleFontFolderResult(resultCode, data);\n"
        "            return;\n"
        "        }\n",
        "route the WordCraft SAF tree picker",
    )
    # Hidden EditText and InputConnection sometimes receive a physical key
    # instead of the Activity; intercept there before the IME consumes it.
    java = exactly_once(
        java, "                        public boolean sendKeyEvent(KeyEvent event) {\n",
        "                        public boolean sendKeyEvent(KeyEvent event) {\n"
        "                            if (wcHandleHardwareShortcut(event)) return true;\n",
        "WordCraft keyboard InputConnection")
    java = exactly_once(
        java, "                        public boolean commitText(CharSequence text, int newCursorPosition) {\n",
        "                        public boolean commitText(CharSequence text, int newCursorPosition) {\n"
        "                            if (wcHandleImeChoice(text)) return true;\n",
        "WordCraft IME commit")
    java = exactly_once(
        java, "                public boolean onKeyDown(int keyCode, KeyEvent event) {\n",
        "                public boolean onKeyDown(int keyCode, KeyEvent event) {\n"
        "                    if (wcHandleHardwareShortcut(event)) return true;\n",
        "WordCraft IME keydown")
    java = exactly_once(
        java, "                public boolean onKeyUp(int keyCode, KeyEvent event) {\n",
        "                public boolean onKeyUp(int keyCode, KeyEvent event) {\n"
        "                    if (wcHandleHardwareShortcut(event)) return true;\n",
        "WordCraft IME keyup")
    if not java.endswith("}\n"):
        raise SystemExit("Unexpected Activity template closing brace")
    extension = Path(__file__).with_name("WordCraftExtension.java.inc").read_text(encoding="utf-8")
    java = java[:-2] + extension + "\n}\n"
    java_template.write_text(java, encoding="utf-8")
    import shutil
    shutil.copy2(
        Path(__file__).with_name("wordcraft_android.rs"),
        root / "templates" / "android" / "wordcraft_android.rs",
    )
    shutil.copy2(
        Path(__file__).with_name("refresh_feedback.rs"),
        root / "templates" / "android" / "refresh_feedback.rs",
    )

    shutil.copy2(
        Path(__file__).with_name("stylus_wheel.rs"),
        root / "templates" / "android" / "stylus_wheel.rs",
    )

    # Inject the WordCraft-specific JNI tools into the generated shell. The
    # Android candidate still builds the unmodified upstream engine and UI.
    patched = exactly_once(
        patched,
        "        self.handle_clipboard_shortcuts(raw);\n{persist_hook}        {inner_hook}",
        "{wc_raw_dcs}{wc_trackpad_scroll}{wc_touch_pan}{wc_stylus_samples}{wc_wheel_input}        self.handle_clipboard_shortcuts(raw);\n{wc_clip_dedupe}{persist_hook}        {inner_hook}",
        "intercept D/C/S physical keys before app input processing",
    )
    patched = exactly_once(
        patched,
        "    shell = f'''",
        "    wc_fields = '\\n    wc: wordcraft_android::Tools,' if app == 'wordcraft' else ''\n"
        "    wc_new_setup = '        let wc_tools = wordcraft_android::Tools::new(&app);\\n' if app == 'wordcraft' else ''\n"
        "    wc_new_init = ', wc: wc_tools' if app == 'wordcraft' else ''\n"
        "    wc_logic = '        self.inner.android_capture_unsaved_dcs(ctx);\\n        self.wc.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ctx);\\n        self.wc.poll(&mut self.inner, ctx);\\n' if app == 'wordcraft' else ''\n"
        "    wc_raw_dcs = '        self.wc.capture_unsaved_keys(self.inner.android_unsaved_dcs_active(), ctx, raw);\\n' if app == 'wordcraft' else ''\n"
        "    wc_trackpad_scroll = '        self.wc.inject_trackpad_scroll(ctx, raw, self.modifiers);\\n' if app == 'wordcraft' else ''\n"
        "    wc_touch_pan = '        self.wc.inject_touch_pan(ctx, raw, self.modifiers, self.inner.canvas.canvas_rect);\\n' if app == 'wordcraft' else ''\n"
        "    wc_stylus_samples = '        self.wc.inject_stylus_motion(ctx);\\n' if app == 'wordcraft' else ''\n"
        "    wc_wheel_input = '        self.wc.isolate_wheel_input(ctx, raw);\\n' if app == 'wordcraft' else ''\n"
        "    wc_clip_dedupe = '        self.wc.deduplicate_clipboard_input(raw);\\n' if app == 'wordcraft' else ''\n"
        "    wc_ui = '        self.wc.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());\\n        self.wc.ui(&mut self.inner, ui.ctx(), frame);\\n        if let Some(copy) = ui.ctx().output(|o| o.commands.iter().rev().find_map(|c| match c { egui::OutputCommand::CopyText(text) => Some(text.clone()), _ => None })) { android_clipboard_set(&self.app, &copy); }\\n' if app == 'wordcraft' else ''\n"
        "    wc_preui = 'self.wc.prepare_menu(ui.ctx(), frame);\\n        self.wc.update_feedback(ui);\\n        ' if app == 'wordcraft' else ''\n"
        "    shell = f'''",
        "initialize WordCraft-only shell fields",
    )
    for before, after, purpose in (
        ("bars_theme: Option<bool>,{saf_fields}",
         "bars_theme: Option<bool>,{wc_fields}{saf_fields}",
         "add WordCraft tools field"),
        ("let ime = ime_bridge::ime::ImeBridge::new(&app);\n        Self {{",
         "let ime = ime_bridge::ime::ImeBridge::new(&app);\n{wc_new_setup}        Self {{",
         "construct tools before moving AndroidApp"),
        ("bars_theme: None{saf_new_init}",
         "bars_theme: None{wc_new_init}{saf_new_init}",
         "initialize WordCraft tools"),
        ("{intent_logic}{saf_logic_poll}{persist_logic}",
         "{intent_logic}{saf_logic_poll}{wc_logic}{persist_logic}",
         "poll WordCraft Java results"),
        ("        {inner_ui}\n    }}",
         "        {wc_preui}{inner_ui}\n{wc_ui}    }}",
         "show WordCraft tools and shortcut pad"),
    ):
        patched = exactly_once(patched, before, after, purpose)

    patched = exactly_once(
        patched,
        '    (staging_dir / "src" / "lib.rs").write_text(entry)',
        '    if app == "wordcraft":\n'
        '        if entry.count("mod system_fonts;") != 1:\n'
        '            raise SystemExit("WordCraft module insertion anchor changed")\n'
        '        entry = entry.replace("mod system_fonts;", "mod wordcraft_android;\\nmod system_fonts;", 1)\n'
        '        shutil.copy2(root / "templates" / "android" / "wordcraft_android.rs", staging_dir / "src" / "wordcraft_android.rs")\n'
        '        (staging_dir / "src" / "wordcraft_android").mkdir(exist_ok=True)\n'
        '        shutil.copy2(root / "templates" / "android" / "refresh_feedback.rs", staging_dir / "src" / "wordcraft_android" / "refresh_feedback.rs")\n'
        '        shutil.copy2(root / "templates" / "android" / "stylus_wheel.rs", staging_dir / "src" / "wordcraft_android" / "stylus_wheel.rs")\n'
        '        shutil.copy2(root / "templates" / "android" / "stylus_wheel_wc.rgba", staging_dir / "src" / "wordcraft_android" / "stylus_wheel_wc.rgba")\n'
        '    (staging_dir / "src" / "lib.rs").write_text(entry)',
        "install WordCraft Rust module into generated launcher",
    )
    patched = exactly_once(
        patched,
        '        manifest = manifest.replace(\'[[package.metadata.android.uses_permission]]\\nname = "android.permission.MANAGE_EXTERNAL_STORAGE"\\n\', "")',
        '        manifest = manifest.replace(\'[[package.metadata.android.uses_permission]]\\nname = "android.permission.MANAGE_EXTERNAL_STORAGE"\\n\', "")\n'
        '        manifest += \'\\n[[package.metadata.android.uses_permission]]\\nname = "android.permission.INTERNET"\\n\'',
        "permit WordCraft-only read-only GitHub update checks",
    )

    # WC_EXACT_LAUNCHER_WC_GLYPH_V1 — recover the original blue/cyan Wc
    # lettering, not generic egui text. Verify the owner-approved SHA before
    # creating the transparent RGBA used in the PhotoCraft-ratio round hub.
    from PIL import Image
    import hashlib
    import json
    assets = Path(__file__).resolve().parents[2] / "tools" / "approved-branding" / "assets"
    manifest = json.loads((assets / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["app"] == "wordcraft" and manifest["filename"] == "WordCraft.png"
    source_icon = assets / manifest["filename"]
    assert hashlib.sha256(source_icon.read_bytes()).hexdigest() == manifest["source_sha256"], "STOP: WordCraft icon changed"
    assert manifest["bg_color"].lower() == "#0e52a5"
    assert manifest["letter_color"].lower() == "#7ad8fc"
    assert manifest["glyph_source_bounds"] == [86, 597, 1983, 1468]
    original = Image.open(source_icon).convert("RGBA")
    assert original.size == (2048, 2048)
    cropped = original.crop(tuple(manifest["glyph_source_bounds"]))
    alpha = cropped.getchannel("R").point(
        lambda value: round(max(0., min(1., (value - 14.) / (122. - 14.))) * 255))
    exact_glyph = Image.new("RGBA", cropped.size, (122, 216, 252, 0))
    exact_glyph.putalpha(alpha)
    exact_glyph = exact_glyph.resize((192, 88), Image.Resampling.LANCZOS)
    assert exact_glyph.getchannel("A").getbbox() is not None, "STOP: no original Wc glyph"
    (root / "templates" / "android" / "stylus_wheel_wc.rgba").write_bytes(exact_glyph.tobytes())

    # The approved launcher icon is the only source for the in-app menu artwork.
    # Embed a tiny raw RGBA texture: no PNG loader, file permission or runtime
    # decoding dependency. This is only copied into the isolated WordCraft UI.
    from PIL import Image
    app_icon = Path(__file__).with_name("icon") / "wordcraft-approved-192.png"
    if not app_icon.is_file():
        raise SystemExit("Approved WordCraft launcher icon missing; stop")
    with Image.open(app_icon) as approved:
        rgba = approved.convert("RGBA").resize((40, 40), Image.Resampling.LANCZOS)
        (root / "source" / "wordcraft" / "crates" / "ui-egui" / "src" /
         "wordcraft-android-menu-icon.rgba").write_bytes(rgba.tobytes())
    # Add ArtCraft as a real ribbon dropdown, with room reserved by the tab
    # planner. Other app checkouts and the upstream repository are untouched.
    ribbon = root / "source" / "wordcraft" / "crates" / "ui-egui" / "src" / "ribbon.rs"
    ribbon_text = ribbon.read_text(encoding="utf-8")
    ribbon_text = exactly_once(
        ribbon_text,
        "let button_levels = [button_widths(0), button_widths(1), button_widths(2)];",
        "let android_tools_width = if cfg!(target_os = \"android\") { 42.0 } else { 0.0 };\n"
        "                let button_levels = [button_widths(0), button_widths(1), button_widths(2)].map(|width| width + android_tools_width);",
        "reserve native ArtCraft menu space",
    )
    ribbon_text = exactly_once(
        ribbon_text,
        "                    ui.with_layout(crate::rtl::far_side(ui, egui::Align::Center), |ui| {\n"
        "                        // No document open (#1129): nothing to share, edit or comment on — but only",
        "                #[cfg(target_os = \"android\")]\n"
        "                artcraft_android_menu(ui);\n"
        "                    ui.with_layout(crate::rtl::far_side(ui, egui::Align::Center), |ui| {\n"
        "                        // No document open (#1129): nothing to share, edit or comment on — but only",
        "place WordCraft launcher icon menu at top left of tab strip",
    )
    ribbon.write_text(ribbon_text + Path(__file__).with_name("ribbon_android.rs.inc").read_text(), encoding="utf-8")
    from patch_stylus_ink import apply_stylus_ink
    apply_stylus_ink(root / "source" / "wordcraft", Path(__file__).with_name("stylus_curve.rs.inc"))
    from patch_pressure_ink import apply_pressure_ink
    apply_pressure_ink(root / "source" / "wordcraft", Path(__file__).with_name("stylus_pressure.rs.inc"))
    from patch_touch_guard import apply_touch_guard
    apply_touch_guard(root / "source" / "wordcraft")
    source.write_text(patched, encoding="utf-8")
    print("Applied WordCraft font persistence and scoped-storage overlay to isolated builder")
    print("WordCraft SAF shared font folder, manual/opt-in updater, shortcut pad and GPU info installed; device testing pending")


if __name__ == "__main__":
    main()

