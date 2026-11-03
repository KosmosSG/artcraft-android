"""VectorCraft-only packaging optimization for the immutable reference builder.

VectorCraftActivity extends android.app.NativeActivity. Both shipped Java sources
use Android SDK classes, not AndroidX/AppCompat, Kotlin or GameActivity.
Avoid shipping those unused Java/DEX resources in VectorCraft's test APK.
Keep extractNativeLibs=false (uncompressed/page-aligned .so for startup speed).
Rust symbol stripping is selected by CARGO_PROFILE_RELEASE_STRIP=symbols in CI.
"""
from pathlib import Path
import argparse

UNUSED_DEPS = """dependencies {{
    // AndroidX pulls kotlin-stdlib 1.8 next to the old split -jdk7/-jdk8 artifacts; align
    // them (same combination the reference project ships).
    implementation platform('org.jetbrains.kotlin:kotlin-bom:1.8.22')
    implementation 'androidx.appcompat:appcompat:1.7.0'
    implementation 'androidx.core:core:1.13.1'
    // The Java half of GameActivity, whose Activity the launcher extends; version matched
    // to the vendored android-activity crate's game-activity backend (see its README).
    implementation 'androidx.games:games-activity:4.4.0'
}}"""
COMPACT_DEPS = """dependencies {{
    // VectorCraftActivity extends android.app.NativeActivity and uses only Android
    // SDK APIs. The reference builder's Kotlin, AppCompat and GameActivity
    // runtime dependencies are unnecessary for this application's APK.
}}"""


def patch_source(generated: str, java: str, extras: str, manifest: str) -> str:
    if "extends NativeActivity" not in java or "extends GameActivity" in java:
        raise ValueError("Unexpected VectorCraft Activity superclass; cannot drop GameActivity")
    if "native-activity" not in manifest:
        raise ValueError("Android adapter is no longer using NativeActivity")
    for label, data in (("Activity", java), ("Extras", extras)):
        if "androidx." in data or "com.google.androidgamesdk." in data or "kotlin." in data:
            raise ValueError(f"{label} uses a dependency slated for removal")
    if generated.count(UNUSED_DEPS) != 1:
        raise ValueError("Pinned builder dependency declaration changed; review required")
    return generated.replace(UNUSED_DEPS, COMPACT_DEPS, 1)


def patch_builder(builder: Path, android_port: Path) -> None:
    generated = builder / "lib/android_project.py"
    manifest = android_port / "adapters/vectorcraft/Cargo.toml"
    java = android_port / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    extras = android_port / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java"
    source = generated.read_text()
    updated = patch_source(source, java.read_text(), extras.read_text(), manifest.read_text())
    generated.write_text(updated)
    print("PASS: VectorCraft-only dependency-free NativeActivity Android package; JNI/ARM64 kept")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    parser.add_argument("android_port", type=Path)
    args=parser.parse_args()
    patch_builder(args.builder,args.android_port)
