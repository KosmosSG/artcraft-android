"""Restore VectorCraft v0.24.1 editor-owned IME reset delivery on Android.

The pinned builder overrides Storytold's egui-winit with its older Android
clipboard fork. That fork handles stock IME focus but does not forward
IMEOutput.reset_request. The official VectorCraft editor requests an opaque
reset ID and refuses stale composition until that exact reset finishes.

Forward only Android's editor-owned request to winit. The existing Android.8
JNI bridge then restarts the Java input connection and returns the same ID.
Never synthesize completion, change the editor's stale-input guards, or touch
.ai document content, pan, gestures, brushes, or OS cursor behavior.
"""
from pathlib import Path
import sys

MARKER = "VC_ANDROID10_EDITOR_RESET_FORWARD"


def patch(root: Path) -> None:
    source = root / "vendor/egui-winit/src/lib.rs"
    s = source.read_text()
    if MARKER in s:
        raise RuntimeError("Android.10 reset bridge already installed")
    # Review against the exact MostafaXS1 v0.5.0 builder checkout.
    anchor = '''        if let Some(ime) = ime {
            // Android uses GameActivity's native IME (the shell polls the text state);'''
    if s.count(anchor) != 1:
        raise RuntimeError(f"Android.10 expected one egui-winit IME output anchor, got {s.count(anchor)}")
    replacement = '''        // VC_ANDROID10_EDITOR_RESET_FORWARD
        // The builder's clipboard-enabled egui-winit otherwise drops the
        // fork's request-bound IME reset (no Java vcResetIme calls at all).
        // Only the native host confirms this opaque ID, after it actually
        // clears the composition and rebinds its InputConnection.
        #[cfg(target_os = "android")]
        if let Some(request) = ime.as_ref().and_then(|ime| ime.reset_request) {
            window.reset_ime_with_request(request.as_u64());
        }

''' + anchor
    s = s.replace(anchor, replacement, 1)
    assert s.count(MARKER) == 1
    assert s.count("window.reset_ime_with_request(request.as_u64());") == 1
    assert s.count("window.set_ime_allowed(allow_ime);") >= 1
    source.write_text(s)
    print("PASS: Android.10 forwards editor-owned reset ID to native Java IME host")


def verify(root: Path) -> None:
    egui = (root / "vendor/egui-winit/src/lib.rs").read_text()
    winit = (root / "vendor/winit/src/platform_impl/android/mod.rs").read_text()
    activity = (root / "vendor/android-activity/src/native_activity/mod.rs").read_text()
    bridge = (root / "adapters/vectorcraft/src/ime_bridge.rs").read_text()
    java = (root / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
    upstream = (root / "source/vectorcraft/crates/ui-egui/src/ime.rs").read_text()
    assert MARKER in egui
    assert 'ime.as_ref().and_then(|ime| ime.reset_request)' in egui
    assert 'window.reset_ime_with_request(request.as_u64());' in egui
    assert 'self.app.vc_reset_ime(request_id);' in winit
    assert 'jni_str!("vcResetIme")' in activity
    assert 'public void vcResetIme(long requestId)' in java
    assert 'imm.restartInput(imeView);' in java
    assert 'imeEvents.offer("r" + Long.toUnsignedString(requestId));' in java
    assert 'get_temp::<Option<egui::ImeResetId>>(key).flatten()' in bridge
    assert 'raw.events.push(egui::Event::ImeResetCompleted { request_id });' in bridge
    assert 'data.insert_temp(key, Some(request_id));' in upstream
    print("PASS: full reset chain egui -> winit -> native Activity -> Java restart -> exact-ID ack")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: patch_v0241_android10_ime_reset_delivery.py BUILDER [--verify]")
    root = Path(sys.argv[1])
    if len(sys.argv) == 3 and sys.argv[2] == "--verify":
        verify(root)
    elif len(sys.argv) == 2:
        patch(root)
    else:
        raise SystemExit("unknown mode")
