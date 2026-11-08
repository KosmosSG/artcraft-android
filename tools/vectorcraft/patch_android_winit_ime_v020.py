"""Backport Storytold winit 0.30.13 IME reset API to the pinned Android builder.

Official VectorCraft v0.20's egui-winit 0.37 expects two extensions from
storytold/winit@a517b3846ee8457d84ee4975110bfda6797c44dc:
WindowEvent::ImeResetCompleted and Window::reset_ime_with_request.

The reference Android builder also uses winit 0.30.13 but lacks those
extensions. Preserve its customized Android input backend and backport ONLY
the public interface; Android intentionally does not synthesize a completion
fence when native IME reset is unsupported, as in the reviewed upstream fork.
"""
from pathlib import Path
import sys

EVENT_BEFORE = '''    Ime(Ime),

    /// The cursor has moved on the window.'''
EVENT_AFTER = '''    Ime(Ime),

    /// An ordered IME cancellation fence identified by its requesting editor.
    ///
    /// A completion is emitted only when an underlying platform supports a
    /// successful reset. Android's legacy native backend does not emit one.
    ImeResetCompleted { request_id: u64 },

    /// The cursor has moved on the window.'''

WINDOW_BEFORE = '''        self.window
            .maybe_queue_on_main(move |w| w.set_ime_purpose(purpose))
    }

    /// Brings the window to the front and sets input focus.'''
WINDOW_AFTER = '''        self.window
            .maybe_queue_on_main(move |w| w.set_ime_purpose(purpose))
    }

    /// Reset ongoing composition when supported by the platform.
    #[inline]
    pub fn reset_ime(&self) {
        self.window.maybe_queue_on_main(|w| w.reset_ime())
    }

    /// Request an ordered cancellation fence. Unsupported Android backends
    /// perform no operation and never fabricate a success acknowledgement.
    #[inline]
    pub fn reset_ime_with_request(&self, request_id: u64) {
        self.window
            .maybe_queue_on_main(move |w| w.reset_ime_with_request(request_id))
    }

    /// Brings the window to the front and sets input focus.'''

ANDROID_BEFORE = '''    pub fn set_ime_purpose(&self, _purpose: ImePurpose) {}

    pub fn focus_window(&self) {}'''
ANDROID_AFTER = '''    pub fn set_ime_purpose(&self, _purpose: ImePurpose) {}

    // Mirrors the official Storytold winit Android stub: a native reset fence
    // cannot be acknowledged until this platform implementation supports it.
    pub fn reset_ime(&self) {}

    #[inline]
    pub fn reset_ime_with_request(&self, _request_id: u64) {}

    pub fn focus_window(&self) {}'''


def replace_unique(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Unreviewed pinned winit {label}: expected exactly one anchor, found {count}")
    return source.replace(old, new, 1)


def patch_sources(event: str, window: str, android: str) -> tuple[str, str, str]:
    if "ImeResetCompleted" in event or "reset_ime_with_request" in window or "reset_ime_with_request" in android:
        raise ValueError("Storytold IME reset backport already present or different fork: stop")
    # Build all replacements before writing any source.
    event = replace_unique(event, EVENT_BEFORE, EVENT_AFTER, "event variant")
    window = replace_unique(window, WINDOW_BEFORE, WINDOW_AFTER, "Window public methods")
    android = replace_unique(android, ANDROID_BEFORE, ANDROID_AFTER, "Android platform stubs")
    assert "ImeResetCompleted { request_id: u64 }" in event
    assert "pub fn reset_ime_with_request(&self, request_id: u64)" in window
    assert "pub fn reset_ime_with_request(&self, _request_id: u64)" in android
    return event, window, android


def patch_builder(builder: Path) -> None:
    winit = builder / "vendor/winit"
    manifest = (winit / "Cargo.toml").read_text()
    if manifest.count('name = "winit"\nversion = "0.30.13"') != 1:
        raise ValueError("Only reviewed Android builder winit v0.30.13 is supported")
    paths = [
        winit / "src/event.rs",
        winit / "src/window.rs",
        winit / "src/platform_impl/android/mod.rs",
    ]
    sources = [p.read_text() for p in paths]
    # MostafaXS1 main 2026-11-05 already has the ordered IME event and
    # Android reset handler, but lacks the PUBLIC Window forwarding methods
    # required by Storytold egui 0.37. Add just the missing public methods,
    # preserving the reference Android IME reset implementation.
    if (("ImeResetCompleted { request_id: u64 }" in sources[0])
            and ("pub fn reset_ime_with_request(&self, _request_id: u64)" in sources[2])
            and ("pub fn reset_ime_with_request(&self, request_id: u64)" not in sources[1])):
        event, window, android = sources
        window = replace_unique(window, WINDOW_BEFORE, WINDOW_AFTER, "latest builder Window API")
        if "pub fn reset_ime(&self)" not in android:
            android = replace_unique(android,
                "    pub fn reset_ime_with_request(&self, _request_id: u64) {",
                "    pub fn reset_ime(&self) {}\n\n    pub fn reset_ime_with_request(&self, _request_id: u64) {",
                "latest builder Android reset method")
        replacements = (event, window, android)
        print("PASS: Mostafa main IME event and reset preserved; add only missing public Window forwarding methods")
    else:
        replacements = patch_sources(*sources)
    for path, patched in zip(paths, replacements):
        path.write_text(patched)
    print("PASS: pinned Storytold IME API on Android builder winit; Android unsupported resets are no-ops, never false acknowledgements")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_android_winit_ime_v020.py BUILDER_DIRECTORY")
    patch_builder(Path(sys.argv[1]))
