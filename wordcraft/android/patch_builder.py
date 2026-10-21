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
    source.write_text(patched, encoding="utf-8")
    print("Applied WordCraft font persistence and scoped-storage overlay to isolated builder")
    print("Shared SAF folder and updater: not installed by this overlay")


if __name__ == "__main__":
    main()
