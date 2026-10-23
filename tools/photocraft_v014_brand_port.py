#!/usr/bin/env python3
"""Use the already-approved Android Pc launcher PNG in PhotoCraft's tiny top-left UI mark.

Runs only on an ephemeral official-source checkout. Desktop builds keep the
upstream brand icon, and the permanent Android launcher image is not edited.
"""
from pathlib import Path
import hashlib
import sys

APPROVED_SHA256 = "1a6495c214ae4536b432a34feff9b7001b612d4df1e79bf784b00d5b393f8a9b"
ORIGINAL = 'const ICON_PNG: &[u8] = include_bytes!("../../../assets/app-icon/hicolor/128x128/apps/ai.storyteller.photocraft.png");'
REPLACEMENT = '''// Android's title-bar mark must match its approved Pc launcher art byte-for-byte.
#[cfg(target_os = "android")]
const ICON_PNG: &[u8] = include_bytes!("../../../apps/photocraft-android/res/drawable/ic_launcher.png");
// Leave official PhotoCraft desktop/web branding unchanged.
#[cfg(not(target_os = "android"))]
const ICON_PNG: &[u8] = include_bytes!("../../../assets/app-icon/hicolor/128x128/apps/ai.storyteller.photocraft.png");'''

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: photocraft_v014_brand_port.py PATH_TO_VERIFIED_SOURCE_ROOT")
    source = Path(sys.argv[1]).resolve()
    icon = source / "apps/photocraft-android/res/drawable/ic_launcher.png"
    brand = source / "crates/ui-egui/src/brand.rs"
    if not brand.is_file() or not icon.is_file():
        raise SystemExit("STOP: expected pinned PhotoCraft brand module or staged Android icon missing")
    if hashlib.sha256(icon.read_bytes()).hexdigest() != APPROVED_SHA256:
        raise SystemExit("STOP: top-left UI icon source is not the original approved Pc launcher")
    text = brand.read_text(encoding="utf-8")
    if text.count(ORIGINAL) != 1 or 'cfg(target_os = "android")' in text:
        raise SystemExit("STOP: official v0.14 brand.rs changed; refusing silent or duplicate icon port")
    brand.write_text(text.replace(ORIGINAL, REPLACEMENT, 1), encoding="utf-8")
    if REPLACEMENT not in brand.read_text(encoding="utf-8"):
        raise SystemExit("STOP: UI icon integration verification failed")
    print("PASS: Android top-left UI icon uses exact approved Pc launcher bytes; desktop unchanged")

if __name__ == "__main__":
    main()
