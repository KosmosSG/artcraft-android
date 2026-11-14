#!/usr/bin/env python3
"""Stage user-approved FilmCraft Android.8 *production identity* in disposable CI only.

Rebuild from the same reviewed FilmCraft v0.20.1 Android.8 source as the
separate-install test. Do not modify published APKs, source branches, keystores
or upstream worktrees. Production signing/publishing is a later gated step.
"""
import json
import sys
from pathlib import Path

PROD_PACKAGE = "com.artcraft.filmcraft"
TEST_PACKAGE = "com.artcraft.filmcraft.test"
PROD_VERSION = "0.20.1-android.8"
TEST_VERSION = "0.20.1-android.8-test"
CODE = 2001008
PREVIOUS_PUBLISHED_CODE = 1900001

def once(s: str, old: str, new: str, name: str) -> str:
    if s.count(old) != 1 or new in s:
        raise RuntimeError(f"STOP: production FilmCraft {name} anchor mismatch: {s.count(old)}")
    return s.replace(old, new, 1)

def stage(suite: Path, builder: Path) -> None:
    if suite.name != "suite" or builder.name != "filmcraft-builder":
        raise RuntimeError("STOP: only disposable FilmCraft Actions checkouts accepted")
    if not (suite/".github").is_dir() or not (builder/"lib/build-common.sh").is_file():
        raise RuntimeError("STOP: expected reviewed FilmCraft CI worktrees")

    manifest = suite/"tools/approved-branding/assets/manifest.json"
    verifier = suite/"tools/filmcraft/verify_android_features_apk_v019.py"
    variant = suite/"tools/filmcraft/stage_upstream_v0201_variant.py"
    runtime = builder/"tools/filmcraft/runtime_patch.py"
    for file in (manifest, verifier, variant, runtime):
        if not file.is_file():
            raise RuntimeError(f"STOP: FilmCraft production staging input missing {file}")

    cfg = json.loads(manifest.read_text())
    if (cfg.get("app"), cfg.get("package"), cfg.get("version_name"),
            cfg.get("version_code"), cfg.get("previous_version_code")) != (
                "filmcraft", TEST_PACKAGE, TEST_VERSION, CODE, PREVIOUS_PUBLISHED_CODE):
        raise RuntimeError("STOP: stage disposable Android.8 version before production identity")
    cfg["package"] = PROD_PACKAGE
    cfg["version_name"] = PROD_VERSION

    check = verifier.read_text()
    check = once(check,
        f'("{TEST_PACKAGE}", "{CODE}", "{TEST_VERSION}")',
        f'("{PROD_PACKAGE}", "{CODE}", "{PROD_VERSION}")',
        "compiled APK identity verifier")
    compile(check, str(verifier), "exec")

    version_source = variant.read_text()
    version_source = once(version_source,
        f'os.environ.get("FILMCRAFT_ANDROID_VERSION_NAME") != "{TEST_VERSION}"',
        f'os.environ.get("FILMCRAFT_ANDROID_VERSION_NAME") != "{PROD_VERSION}"',
        "ephemeral version guard")
    version_source = once(version_source,
        f'os.environ.get("FILMCRAFT_TEST_PACKAGE") != "{TEST_PACKAGE}"',
        f'os.environ.get("FILMCRAFT_TEST_PACKAGE") != "{PROD_PACKAGE}"',
        "builder package guard")
    compile(version_source, str(variant), "exec")

    # The shared Android builder emits Java paths matching -packagename.
    # Change only the production package manifest check and generated Java
    # filename. Keep the Java *test package* guard in the updater untouched.
    android_runtime = runtime.read_text()
    android_runtime = once(android_runtime,
        "if 'package = \"" + TEST_PACKAGE + "\"' not in manifest:",
        "if 'package = \"" + PROD_PACKAGE + "\"' not in manifest:",
        "generated Cargo production package check")
    android_runtime = once(android_runtime,
        '"java/com/artcraft/filmcraft/test/FilmCraftActivity.java"',
        '"java/com/artcraft/filmcraft/FilmCraftActivity.java"',
        "generated production Java Activity path")
    compile(android_runtime, str(runtime), "exec")
    if 'if ("com.artcraft.filmcraft.test".equals(getPackageName()))' not in android_runtime:
        raise RuntimeError("STOP: original test APK update-install isolation lost")
    if 'fcWheelOnDocumentEpoch(long epoch)' not in android_runtime:
        raise RuntimeError("STOP: reviewed Android.8 project-open hover rebind lost")

    # All source checks first; only then mutate disposable worktree files.
    manifest.write_text(json.dumps(cfg, indent=2)+"\n")
    verifier.write_text(check)
    variant.write_text(version_source)
    runtime.write_text(android_runtime)
    print("PASS: isolated FilmCraft production package/version/code staged; "
          "original wheel + touchless project-open hover preserved")

def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        check = Path(__file__).read_text()
        for value in (TEST_PACKAGE, PROD_PACKAGE, TEST_VERSION, PROD_VERSION):
            assert value in check
        assert CODE == 2001008 and PREVIOUS_PUBLISHED_CODE < CODE
        print("PASS: production stage guards are pinned to FilmCraft Android.8")
        return
    if len(sys.argv) != 3:
        raise SystemExit("Usage: stage_v0201_android8_production.py suite filmcraft-builder")
    stage(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())

if __name__ == "__main__":
    main()
