#!/usr/bin/env python3
"""Convert an ALREADY-STAGED PR93 AI Preview overlay into a throwaway
production-identity *build proof* on a GitHub Actions runner.

Do not distribute the resulting APK: the generic builder signs it with a
DISPOSABLE key, not the permanent PhotoCraft release certificate. This script
never accesses secrets or changes checked-in production source. Run only on
the isolated ephemeral pinned keyboard baseline, after preview_stage.py.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tomllib

PREVIEW = "com.artcraft.photocraft.ai.preview"
PRODUCTION = "com.artcraft.photocraft"
OLD_VERSION = "0.14.0-android.1"
PROPOSED_VERSION = "0.14.0-android.2"
ICON_SHA = "1a6495c214ae4536b432a34feff9b7001b612d4df1e79bf784b00d5b393f8a9b"


def exactly(text: str, old: str, new: str, count: int = 1) -> str:
    actual = text.count(old)
    if actual != count:
        raise ValueError(f"Unexpected staged source anchor count {actual} (wanted {count}): {old[:100]}")
    return text.replace(old, new)


def stage(root: Path) -> None:
    adapter = root / "adapters/photocraft"
    manifest = adapter / "Cargo.toml"
    java_dir = adapter / "java/com/artcraft/photocraft"
    branding = root / "tools/approved-branding/assets/manifest.json"
    prep = adapter / "prepare.sh"
    builder = root / "lib/build-common.sh"
    launcher = root / "assets/photocraft/launcher-pc.png"
    if not launcher.is_file() or hashlib.sha256(launcher.read_bytes()).hexdigest() != ICON_SHA:
        raise ValueError("Approved PhotoCraft launcher/icon reference changed")
    data = manifest.read_text()
    config = tomllib.loads(data)["package"]["metadata"]["android"]
    if config["package"] != PREVIEW or config["application"]["label"] != "PhotoCraft AI Preview":
        raise ValueError("Only a checked PR93 isolated preview may be converted for this CI proof")
    data = exactly(data, f'package = "{PREVIEW}"', f'package = "{PRODUCTION}"')
    data = exactly(data, 'label = "PhotoCraft AI Preview"', 'label = "PhotoCraft"', 2)
    # The template adapter inherits its Cargo workspace version. Its
    # generated Android crate gets the .2 version only when build.sh runs
    # prepare.sh with the explicit candidate-review environment override.
    parsed = tomllib.loads(data)
    if parsed["package"].get("version", {}).get("workspace") is not True:
        raise ValueError("Expected inherited adapter version (generated crate owns versionName)")
    if parsed["package"]["metadata"]["android"]["package"] != PRODUCTION:
        raise ValueError("Production package identity verification failed")
    java_sources = ["PhotoCraftActivity.java", "PhotoCraftUpdatePolicy.java"]
    old_java = java_dir / "ai/preview"
    for filename in java_sources:
        source = old_java / filename
        target = java_dir / filename
        if not source.is_file() or target.exists():
            raise ValueError(f"Unsafe Java namespace/source state: {filename}")
        text = exactly(source.read_text(),
                       f"package {PREVIEW};", f"package {PRODUCTION};")
        target.write_text(text)
        source.unlink()
    old_java.rmdir()
    (java_dir / "ai").rmdir()
    raw = branding.read_text()
    record = json.loads(raw)
    if record.get("package") != PREVIEW or record.get("display_name") != "PhotoCraft AI Preview":
        raise ValueError("Unexpected approved-branding preview state")
    record["package"] = PRODUCTION
    record["display_name"] = "PhotoCraft"
    # No icon pixels or image references are changed.
    manifest.write_text(data)
    branding.write_text(json.dumps(record, indent=2) + "\n")

    # The immutable v0.14 adapter's preparation code selects the approved
    # icon only for android.1; include android.2 in this disposable checkout.
    # The production repo's original prepare.sh is not edited or committed.
    setup = prep.read_text()
    selector = '"${ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME:-}" == "0.14.0-android.1"'
    setup = exactly(setup, selector,
        selector + ' || "${ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME:-}" == "0.14.0-android.2"')
    prep.write_text(setup)

    # The generic builder recognizes only android.1 as the reviewed v0.14
    # menu port, otherwise it attempts to reapply the incompatible v0.12
    # patch. Extend this temporary runner's guard for android.2; still run
    # photocraft_v014_menu_guard.py on the same immutable upstream commit.
    # Nothing here is committed into the repository's shared builder.
    build_text = builder.read_text()
    guard = 'if [[ "${ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME:-}" == "0.14.0-android.1" ]]; then'
    replacement = 'if [[ "${ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME:-}" == "0.14.0-android.1" || "${ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME:-}" == "0.14.0-android.2" ]]; then'
    build_text = exactly(build_text, guard, replacement)
    builder.write_text(build_text)
    print("PASS: temporary v0.14 menus guard covers candidate-review android.2 without legacy patch")
    print("PASS: staging ONLY — regular PhotoCraft name, package, Activity and icon preserved")
    print("PASS: proposed review version", PROPOSED_VERSION)
    print("IMPORTANT: output is signed with a disposable key; NEVER install/publish its APK")


def self_test() -> None:
    assert exactly("a a", "a", "b", 2) == "b b"
    for text, old, count in [("abc", "z", 1), ("a a", "a", 1)]:
        try:
            exactly(text, old, "x", count)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe staging anchor was accepted")
    assert PRODUCTION != PREVIEW and OLD_VERSION != PROPOSED_VERSION
    assert "android.2" in PROPOSED_VERSION
    print("PASS: isolated production identity conversion anchor tests")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        self_test()
    elif len(sys.argv) == 2:
        try:
            stage(Path(sys.argv[1]).resolve())
        except (ValueError, OSError, KeyError) as exc:
            raise SystemExit(f"STOP: disposable PhotoCraft source proof failed: {exc}")
    else:
        raise SystemExit("usage: photocraft_ai_production_dryrun_stage.py --self-test|ROOT")
