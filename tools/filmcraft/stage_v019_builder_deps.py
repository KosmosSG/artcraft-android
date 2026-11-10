#!/usr/bin/env python3
"""FilmCraft v0.19-specific Rust dependency pin protection.

Patch the *temporary pinned Android builder* at CI staging time, never the
production ArtCraft builder or the official FilmCraft source. The pinned
builder's global vendor blocks are older than the upstream v0.19.0 egui/winit
IME-reset API; for FilmCraft, preserve official git pins. All other apps
retain the vendor workarounds byte-for-byte. Fail closed if anchors drift.
"""
from pathlib import Path
import sys

EGUI_START = 'echo "Vendoring the Android-compatible egui-winit for $TITLE (system clipboard via JNI)..."'
EGUI_END = '# Some apps call `rfd` directly from a crate'
WINIT_START = 'echo "Vendoring the mouse/scroll-aware winit for $TITLE..."'
WINIT_END = '# Every launcher uses the builder\'s vendored android-activity:'
BUILD_ANCHOR = 'echo "  -> building the native library with cargo-ndk (arm64-v8a, API $MIN_SDK)"'
# The pinned builder generates a direct egui-winit 0.36 dependency.
# FilmCraft v0.19 needs upstream egui-winit 0.37 for its IME-reset event.
LAUNCHER_EGUI_OLD = "egui-winit = \"0.36\""
LAUNCHER_EGUI_NEW = "egui-winit = \"{'0.37' if app == 'filmcraft' else '0.36'}\""
W_REV = 'a517b3846ee8457d84ee4975110bfda6797c44dc'
E_REV = '6d518fc799681571963842f95b55a6b68431b15a'

MANIFEST_GUARD = """
# Keep FilmCraft v0.19's coordinated upstream IME reset and egui-winit API.
# This must run AFTER every builder vendor operation and BEFORE cargo-ndk.
if [[ "$APP" == "filmcraft" ]]; then
    python3 - "$ROOT/$SRC/Cargo.toml" <<'PYFILMCRAFTDEPS'
from pathlib import Path
import sys
import tomllib
manifest = Path(sys.argv[1])
patches = tomllib.loads(manifest.read_text())["patch"]["crates-io"]
expected = {
    "winit": {"git": "https://github.com/storytold/winit.git",
              "rev": "a517b3846ee8457d84ee4975110bfda6797c44dc"},
    "egui-winit": {"git": "https://github.com/storytold/egui.git",
                   "rev": "6d518fc799681571963842f95b55a6b68431b15a"},
}
for name, pin in expected.items():
    if patches.get(name) != pin:
        raise SystemExit(f"STOP: unexpected FilmCraft {name} override: {patches.get(name)!r}")
print("PASS: FilmCraft v0.19.0 retains official egui-winit and winit git pins")
PYFILMCRAFTDEPS
    # The upstream pinned winit leaves mouse hover unimplemented.
    # Preserve its version/IME API; backport only reviewed builder Android mouse
    # events into the *disposable* checkout, then use a local Cargo path patch.
    python3 "$ROOT/tools/filmcraft/port_android_mouse_winit.py" "$ROOT/$SRC" "$ROOT/vendor/winit/src/platform_impl/android/mod.rs"
fi
"""

def patch_text(source: str) -> str:
    if "PYFILMCRAFTDEPS" in source:
        raise ValueError("FilmCraft dependency guard is already staged")
    for marker in (EGUI_START, EGUI_END, WINIT_START, WINIT_END, BUILD_ANCHOR, LAUNCHER_EGUI_OLD):
        if source.count(marker) != 1:
            raise ValueError(f"STOP: pinned builder anchor changed: {marker!r}")
    if not (source.index(EGUI_START) < source.index(EGUI_END) <
            source.index(WINIT_START) < source.index(WINIT_END) <
            source.index(BUILD_ANCHOR)):
        raise ValueError("STOP: pinned builder vendor block order changed")
    # Scope the EXISTING blocks rather than editing their heredocs, preserving
    # all mouse/clipboard vendor behavior for non-FilmCraft applications.
    source = source.replace(EGUI_START,
                            'mkdir -p "$SRC/vendor"\nif [[ "$APP" != "filmcraft" ]]; then\n' + EGUI_START, 1)
    source = source.replace(EGUI_END,
                            'else\n    echo "FilmCraft v0.19: keeping upstream egui-winit v0.37 Git pin"\nfi\n\n' + EGUI_END, 1)
    source = source.replace(WINIT_START,
                            'if [[ "$APP" != "filmcraft" ]]; then\n' + WINIT_START, 1)
    source = source.replace(WINIT_END,
                            'else\n    echo "FilmCraft v0.19: keeping upstream winit IME-reset Git pin"\nfi\n\n' + WINIT_END, 1)
    # Keep other ArtCraft launchers at 0.36 while FilmCraft uses 0.37.
    # This source is the pinned builder's generated Python f-string.
    source = source.replace(LAUNCHER_EGUI_OLD, LAUNCHER_EGUI_NEW, 1)
    return source.replace(BUILD_ANCHOR, MANIFEST_GUARD + BUILD_ANCHOR, 1)

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: stage_v017_builder_deps.py /temporary/filmcraft-builder/lib/build-common.sh")
    path = Path(sys.argv[1]).resolve()
    if path.name != "build-common.sh" or path.parent.name != "lib" or "filmcraft-builder" not in path.parts:
        raise SystemExit("STOP: dependency protection only allowed in disposable FilmCraft builder")
    result = patch_text(path.read_text())
    path.write_text(result)
    print("PASS: isolated builder preserves FilmCraft v0.19 Git IME API pins")

if __name__ == "__main__":
    main()
