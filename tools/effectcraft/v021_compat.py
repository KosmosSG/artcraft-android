#!/usr/bin/env python3
"""EffectCraft v0.21 Android trial metadata guards.

Operate only on throwaway CI builder checkouts. No production signing or release.
The v0.20 trial and published v0.16 Android baseline remain intact.
"""
import json
from pathlib import Path
from v020_compat import menu_path_and_anchor

UPSTREAM_SHA = "7870b5916ae0749d497d880989683bf2946d6c8b"
UPSTREAM_TAG = "v0.21.0"
ANDROID_TEST_VERSION = "0.21.0-android.11"
TEST_VERSION_CODE = 16820011
TEST_PACKAGE = "com.artcraft.effectcraft.v021test11"

def replace_exact(source: str, old: str, new: str) -> str:
    if source.count(old) != 1 or new in source:
        raise RuntimeError("STOP: unexpected EffectCraft metadata; fail closed to preserve features")
    return source.replace(old, new, 1)

def stage_trial_metadata(builder_root: Path) -> None:
    """After prepare_candidate.py: change disposable build metadata only."""
    path = Path(builder_root) / "lib/build-common.sh"
    source = path.read_text(encoding="utf-8")
    # prepare_candidate stages android.3 first; advance only the disposable recipe.
    expected_version = '''version_line = f'version = "{app_version}-android.3"' if app == "effectcraft" else "version.workspace = true"'''
    if source.count(expected_version) != 1:
        raise RuntimeError("STOP: EffectCraft packager version drift")
    source = replace_exact(source, expected_version, expected_version.replace("android.3", "android.11"))
    source = replace_exact(source, "version_code = 16781315", f"version_code = {TEST_VERSION_CODE}")
    path.write_text(source, encoding="utf-8")

def stage_trial_branding_metadata(builder_root: Path) -> None:
    """Adjust only version fields of copied approved Ec artwork manifest."""
    path = Path(builder_root) / "tools/approved-branding/assets/manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "app": "effectcraft",
        "package": "com.artcraft.effectcraft",
        "version_name": "0.16.0-android.8",
        "version_code": 16781320,
    }
    for key, value in expected.items():
        if type(data.get(key)) is not type(value) or data[key] != value:
            raise RuntimeError(f"STOP: approved EffectCraft branding {key} drift")
    data["version_name"] = ANDROID_TEST_VERSION
    data["version_code"] = TEST_VERSION_CODE
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
