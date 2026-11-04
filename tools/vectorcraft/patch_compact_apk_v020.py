"""VectorCraft-only packaging optimization for the immutable reference builder.

VectorCraftActivity extends android.app.NativeActivity. Both shipped Java sources
use framework Android and the official lightweight AndroidX SplashScreen API.
Avoid shipping AppCompat/GameActivity/Kotlin that the NativeActivity does not use.
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
    // NativeActivity needs only AndroidX's small splash compat API for a
    // real setKeepOnScreenCondition() while Vulkan prepares its first pixels.
    // No AppCompat, Kotlin BOM or GameActivity.
    implementation 'androidx.core:core-splashscreen:1.0.1'
}}"""

# The generated theme is shared with the GameActivity builder, which needs
# AppCompat. The VectorCraft native launcher does NOT: its theme must use a
# framework-defined ancestor, or AAPT fails after AppCompat is removed.
APPCOMPAT_THEME = '<style name="Theme.Artcraft" parent="Theme.AppCompat.NoActionBar">'
NATIVE_THEME = '<style name="Theme.ArtcraftPost" parent="android:style/Theme.Material.NoActionBar">'


def patch_native_theme(source: str) -> str:
    if source.count(APPCOMPAT_THEME) != 1:
        raise ValueError("Pinned builder AppCompat theme anchor changed; review required")
    if source.count(NATIVE_THEME):
        raise ValueError("Android native theme was already patched")
    patched = source.replace(APPCOMPAT_THEME,
        '<style name="Theme.Artcraft" parent="Theme.SplashScreen">', 1)
    # AndroidX requires postSplashScreenTheme to switch away from the launch
    # theme when the native activity draws. Use the framework no-actionbar
    # post theme so AppCompat and GameActivity remain unnecessary.
    black = '<item name="android:windowBackground">@android:color/black</item>'
    if patched.count(black) != 1:
        raise ValueError("Pinned Android windowBackground anchor changed")
    patched = patched.replace(black,
        '<item name="android:windowBackground">#2d0000</item>\n'
        '        <item name="windowSplashScreenBackground">#2d0000</item>\n'
        '        <item name="windowSplashScreenAnimatedIcon">@mipmap/ic_launcher</item>\n'
        '        <item name="postSplashScreenTheme">@style/Theme.ArtcraftPost</item>', 1)
    closing = '    </style>\n</resources>'
    if patched.count(closing) != 1:
        raise ValueError("Pinned theme close changed; review required")
    return patched.replace(closing,
        '    </style>\n'
        '    ' + NATIVE_THEME + '\n'
        '        <item name="android:windowFullscreen">true</item>\n'
        '        <item name="android:windowBackground">#2d0000</item>\n'
        '        <item name="android:defaultFocusHighlightEnabled">false</item>\n'
        '    </style>\n</resources>', 1)


def patch_source(generated: str, java: str, extras: str, manifest: str) -> str:
    if "extends NativeActivity" not in java or "extends GameActivity" in java:
        raise ValueError("Unexpected VectorCraft Activity superclass; cannot drop GameActivity")
    if "native-activity" not in manifest:
        raise ValueError("Android adapter is no longer using NativeActivity")
    for label, data in (("Activity", java), ("Extras", extras)):
        checked = data.replace("androidx.core.splashscreen.SplashScreen", "")
        if "androidx." in checked or "com.google.androidgamesdk." in checked or "kotlin." in checked:
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
    updated = patch_native_theme(updated)
    generated.write_text(updated)
    # The production adapter still names the original framework theme; only
    # this disposable candidate selects the generated brand-coloured theme.
    # Do not modify the committed stable app or its production manifest.
    staged = builder / "adapters/vectorcraft/Cargo.toml"
    original = staged.read_text()
    old = 'theme = "@android:style/Theme.DeviceDefault.NoActionBar.Fullscreen"'
    if original.count(old) != 1:
        raise ValueError("Pinned VectorCraft Android theme anchor changed")
    staged.write_text(original.replace(old, 'theme = "@style/Theme.Artcraft"', 1))
    print("PASS: VectorCraft AndroidX SplashScreen keep condition, maroon post theme, no AppCompat/GameActivity")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    parser.add_argument("android_port", type=Path)
    args=parser.parse_args()
    patch_builder(args.builder,args.android_port)
