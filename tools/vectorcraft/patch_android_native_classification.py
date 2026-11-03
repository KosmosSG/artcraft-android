"""Add native-activity MotionEvent::classification for the pinned VectorCraft builder.

The reference builder's android-activity 0.6.1 game-activity backend exposes
classification(), but native-activity does not. Its winit fork calls that
method unconditionally. Patch only the native backend in the disposable builder,
preserving Android 28 support with a dynamically resolved NDK symbol.

This is NOT a Cargo version upgrade or a modification of the published APK.
"""
from __future__ import annotations

import argparse
from pathlib import Path

IMPORT_ANCHOR = (
    "    Axis, Button, ButtonState, EdgeFlags, KeyAction, Keycode, MetaState, MotionAction,\n"
)
IMPORT_REPLACEMENT = (
    "    Axis, Button, ButtonState, Classification, EdgeFlags, KeyAction, Keycode, MetaState, MotionAction,\n"
)
FUNCTION_ANCHOR = "    })\n}\n\n/// A motion event"
FUNCTION_REPLACEMENT = '''    })
}

/// The classification NDK function is not available on every Android version.
/// Loading it through dlsym avoids an unresolved native symbol on Android 28,
/// which is still in VectorCraft's minSdk range.
type ClassificationFn = unsafe extern "C" fn(*const ndk_sys::AInputEvent) -> i32;

fn motion_classification_fn() -> Option<ClassificationFn> {
    static CLASSIFICATION_FN: OnceLock<Option<ClassificationFn>> = OnceLock::new();
    *CLASSIFICATION_FN.get_or_init(|| {
        let name = CStr::from_bytes_with_nul(b"AMotionEvent_getClassification\\0").unwrap();
        let sym = unsafe { libc::dlsym(libc::RTLD_DEFAULT, name.as_ptr()) };
        if sym.is_null() {
            None
        } else {
            Some(unsafe { std::mem::transmute::<*mut libc::c_void, ClassificationFn>(sym) })
        }
    })
}

/// A motion event'''
METHOD_ANCHOR = '''        let source =
            unsafe { ndk_sys::AInputEvent_getSource(self.ndk_event.ptr().as_ptr()) as u32 };
        source.into()
    }

    /// Get the device id associated with the event.'''
METHOD_REPLACEMENT = '''        let source =
            unsafe { ndk_sys::AInputEvent_getSource(self.ndk_event.ptr().as_ptr()) as u32 };
        source.into()
    }

    /// Get the system-provided gesture classification for a native motion event.
    ///
    /// If unavailable (e.g. Android API 28), treat this as an unclassified
    /// pointer event. The existing touch/mouse and ACTION_SCROLL paths remain.
    #[inline]
    pub fn classification(&self) -> Classification {
        let classification = motion_classification_fn()
            .map(|get| unsafe { get(self.ndk_event.ptr().as_ptr()) as u32 })
            .unwrap_or(0);
        classification.into()
    }

    /// Get the device id associated with the event.'''


def add_native_motion_classification(source: str) -> str:
    """Fail closed when a different android-activity revision needs re-review."""
    for anchor, label, expected in (
        (IMPORT_ANCHOR, "native input imports", 1),
        (FUNCTION_ANCHOR, "native action-button runtime lookup", 1),
        # Both MotionEvent and KeyEvent implement source(), but the first
        # belongs to the MotionEvent wrapper. Never patch the KeyEvent method.
        (METHOD_ANCHOR, "native input source accessors", 2),
    ):
        found = source.count(anchor)
        if found != expected:
            raise ValueError(f"Unsupported android-activity native backend: {label} appears {found} times (expected {expected})")
    motion = source.find("impl MotionEvent<'_> {")
    source_method = source.find(METHOD_ANCHOR)
    key_event = source.find("pub struct KeyEvent")
    if not (0 <= motion < source_method < key_event):
        raise ValueError("First source() method is no longer MotionEvent::source")
    if "pub fn classification(&self) -> Classification" in source:
        raise ValueError("Native classification method already present; do not patch twice")
    return (
        source.replace(IMPORT_ANCHOR, IMPORT_REPLACEMENT, 1)
        .replace(FUNCTION_ANCHOR, FUNCTION_REPLACEMENT, 1)
        .replace(METHOD_ANCHOR, METHOD_REPLACEMENT, 1)
    )


def patch_builder(builder: Path) -> None:
    manifest = builder / "vendor/android-activity/Cargo.toml"
    native = builder / "vendor/android-activity/src/native_activity/input.rs"
    common = builder / "vendor/android-activity/src/input.rs"
    game = builder / "vendor/android-activity/src/game_activity/input.rs"
    winit = builder / "vendor/winit/src/platform_impl/android/mod.rs"
    if manifest.read_text().count('version = "0.6.1"') != 1:
        raise ValueError("This fix is pinned to builder android-activity 0.6.1 only")
    if "pub enum Classification" not in common.read_text():
        raise ValueError("Common android-activity Classification enum not available")
    if "pub fn classification(&self) -> Classification" not in game.read_text():
        raise ValueError("The reviewed GameActivity backend has changed")
    if "motion_event.classification()" not in winit.read_text():
        raise ValueError("The reviewed winit call site has changed")
    native.write_text(add_native_motion_classification(native.read_text()))
    print("PASS: native-activity 0.6.1 gesture classification via API-safe dlsym; no dependency upgrade")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    patch_builder(parser.parse_args().builder)
