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
        "        if (requestCode == WC_FONT_FOLDER_REQUEST) {\n"
        "            wcHandleFontFolderResult(resultCode, data);\n"
        "            return;\n"
        "        }\n",
        "route the WordCraft SAF tree picker",
    )
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

    # Inject the WordCraft-specific JNI tools into the generated shell. The
    # Android candidate still builds the unmodified upstream engine and UI.
    patched = exactly_once(
        patched,
        "    shell = f'''",
        "    wc_fields = '\\n    wc: wordcraft_android::Tools,' if app == 'wordcraft' else ''\n"
        "    wc_new_setup = '        let wc_tools = wordcraft_android::Tools::new(&app);\n' if app == 'wordcraft' else ''
    wc_new_init = ', wc: wc_tools' if app == 'wordcraft' else ''\n"
        "    wc_logic = '        self.wc.poll(&mut self.inner, ctx);\\n' if app == 'wordcraft' else ''\n"
        "    wc_ui = '        self.wc.ui(&mut self.inner, ui.ctx(), frame);\\n' if app == 'wordcraft' else ''\n"
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
         "        {inner_ui}\n{wc_ui}    }}",
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

    source.write_text(patched, encoding="utf-8")
    print("Applied WordCraft font persistence and scoped-storage overlay to isolated builder")
    print("WordCraft SAF shared font folder, manual/opt-in updater, shortcut pad and GPU info installed; device testing pending")


if __name__ == "__main__":
    main()
