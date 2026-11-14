"""VectorCraft Android.10: verify real native-to-Java IME reset transport.

Source-only regression guard for an Android.9 packaging omission: the build
ran patch_android8_ime_reset.py in app-source mode but forgot its --vendor mode.
Consequently Rust's editor counted reset requests but Java vcResetIme received
none and all later IME commits remained stale.

Run --probe BUILDER before installing NDK, and --staged BUILDER immediately
after applying both overlays. Both modes test only source, not real-device
typing, and never alter the published application.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sys

VENDOR_FILES = (
    "vendor/android-activity/src/lib.rs",
    "vendor/android-activity/src/native_activity/mod.rs",
    "vendor/winit/src/platform_impl/android/mod.rs",
)


def assert_backend_connected(root: Path) -> None:
    app = (root / VENDOR_FILES[0]).read_text()
    native = (root / VENDOR_FILES[1]).read_text()
    window = (root / VENDOR_FILES[2]).read_text()
    # The final packaging stage previously inserted these methods twice and
    # failed native compilation with E0592. Check exact method cardinality.
    assert app.count("pub fn vc_reset_ime(&self, request_id: u64)") == 1
    assert native.count("pub fn vc_reset_ime(&self, request_id: u64)") == 1
    assert window.count("pub fn reset_ime_with_request(&self, request_id: u64)") == 1
    assert "self.inner.read().unwrap().vc_reset_ime(request_id);" in app
    assert 'jni_str!("vcResetIme")' in native
    assert 'jni_sig!("(J)V")' in native
    assert "self.app.vc_reset_ime(request_id);" in window
    begin = window.index("    pub fn reset_ime_with_request(&self, request_id: u64) {")
    end = window.index("    pub fn focus_window(&self)", begin)
    method = window[begin:end]
    assert "set_ime_allowed(false)" not in method
    assert "set_ime_allowed(true)" not in method
    assert "_request_id" not in method


def assert_full_path(root: Path) -> None:
    assert_backend_connected(root)
    java = (root / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
    assert "public void vcResetIme(long requestId)" in java
    assert 'imeEvents.offer("r" + Long.toUnsignedString(requestId));' in java
    bridge = (root / "adapters/vectorcraft/src/ime_bridge.rs").read_text()
    assert "event.strip_prefix('r')" in bridge
    assert "get_temp::<Option<egui::ImeResetId>>(key).flatten()" in bridge
    assert "raw.events.push(egui::Event::ImeResetCompleted { request_id })" in bridge
    ui = (root / "source/vectorcraft/crates/ui-egui/src/ime.rs").read_text()
    assert 'ctx.request_ime_reset(viewport)' in ui
    assert 'pub(crate) fn complete(' in ui
    # Do not weaken stale-input filtering, the exact-ID fence, or doc ownership.
    typing = (root / "source/vectorcraft/crates/ui-egui/src/shortcuts/typing.rs").read_text()
    assert "IncomingComposition::Stale" in typing
    assert "Seq::Commit(_) | Seq::DeleteSurrounding(..) | Seq::Preedit(..)" in typing


def probe(builder: Path) -> None:
    from patch_android8_ime_reset import vendor
    with TemporaryDirectory(prefix="vc-android10-vendor-probe-") as directory:
        temp = Path(directory)
        for relative in VENDOR_FILES:
            destination = temp / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(builder / relative, destination)
        # Prove that the unpatched (Android.9) pinned builder lacks the
        # method. Otherwise this regression test would silently stop testing
        # the missing-transport case.
        try:
            assert_backend_connected(temp)
        except AssertionError:
            pass
        else:
            raise AssertionError("Expected pinned unpatched builder to lack the reset transport")
        vendor(temp)
        assert_backend_connected(temp)
        # The full builder can invoke --vendor again with ALL sources retained:
        # the facade, the JNI bridge and winit must remain single definitions.
        vendor(temp)
        assert_backend_connected(temp)
        # Also reproduce mixed staging: winit retained, fresh activity glue.
        for relative in VENDOR_FILES[:2]:
            shutil.copy2(builder / relative, temp / relative)
        vendor(temp)
        assert_backend_connected(temp)
        vendor(temp)
        assert_backend_connected(temp)
    print("PASS: Android.10 source-only probe covers fresh and pre-staged winit JNI reset transport, no false ack")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: test_v0241_android10_ime_reset_transport.py --probe|--staged BUILDER")
    mode, directory = sys.argv[1:]
    root = Path(directory)
    if mode == "--probe":
        probe(root)
    elif mode == "--staged":
        assert_full_path(root)
        print("PASS: Android.10 full IME reset transport staged through native, Java, JNI, Rust and Type-tool guard")
    else:
        raise SystemExit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
