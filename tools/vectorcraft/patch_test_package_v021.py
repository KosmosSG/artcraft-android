"""VectorCraft v0.21 temporary test package, never a production source change.

The Android Gradle namespace and original Java/JNI class paths stay identical;
only the generated testing applicationId is different.
This is deliberately fail-closed against changes in the pinned builder.
"""
from pathlib import Path
import argparse

ORIGINAL = "com.artcraft.vectorcraft"
TEST = "com.artcraft.vectorcraft.test"
ORIGINAL_GRADLE = "        applicationId '{_groovy(namespace)}'"
TEST_GRADLE = "        applicationId '{_groovy(namespace)}.test'"
ORIGINAL_ACTIVITY = '''        attrs = [f'android:name="{_esc(activity.get("name", ""))}"']'''
TEST_ACTIVITY = '''        activity_name = activity.get("name", "")
        if android_meta.get("package") == "com.artcraft.vectorcraft" and activity_name == ".VectorCraftActivity":
            activity_name = "com.artcraft.vectorcraft.VectorCraftActivity"
        attrs = [f'android:name="{_esc(activity_name)}"']'''


def patch_generator(source: str) -> str:
    for old, label in ((ORIGINAL_GRADLE, "application ID"),
                       (ORIGINAL_ACTIVITY, "activity name")):
        if source.count(old) != 1:
            raise ValueError(f"STOP: pinned Android builder {label} anchor changed")
    assert TEST not in source
    return source.replace(ORIGINAL_GRADLE, TEST_GRADLE, 1).replace(
        ORIGINAL_ACTIVITY, TEST_ACTIVITY, 1)


def patch_manifest(source: str) -> str:
    if source.count('package = "com.artcraft.vectorcraft"') != 1:
        raise ValueError("STOP: stable VectorCraft package identity changed")
    if source.count('label = "VectorCraft"') != 2:
        raise ValueError("STOP: VectorCraft launcher labels changed")
    return source.replace('label = "VectorCraft"', 'label = "VectorCraft Test"')


def apply(root: Path):
    project = root / "lib/android_project.py"
    adapter = root / "adapters/vectorcraft/Cargo.toml"
    source = project.read_text()
    manifest = adapter.read_text()
    updated_source = patch_generator(source)
    updated_manifest = patch_manifest(manifest)
    # Finish every guard before writing to the ephemeral builder checkout.
    project.write_text(updated_source)
    adapter.write_text(updated_manifest)
    print(f"PASS: disposable VectorCraft candidate uses {TEST} with original Java/JNI package {ORIGINAL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    apply(parser.parse_args().builder)
