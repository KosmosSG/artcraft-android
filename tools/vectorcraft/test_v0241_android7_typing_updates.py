"""Source-level acceptance gates for the Android.7 staged APK.

Full behavioral verification requires the HONOR MagicPad 4 hardware test.
These gates prevent accidental edits to the old release, IME safety fences,
stylus wheel, or verified downloader before the expensive ARM64 build.
"""
from pathlib import Path
import sys
import unittest


def check(root: Path) -> None:
    adapter = root / "adapters/vectorcraft"
    java = (adapter / "java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
    bridge = (adapter / "src/ime_bridge.rs").read_text()
    host = (adapter / "src/lib.rs").read_text()
    menu = (root / "source/vectorcraft/crates/ui-egui/src/menus/bar.rs").read_text()
    updater = (adapter / "java/com/artcraft/vectorcraft/VectorCraftUpdateInstaller.java").read_text()
    assert "vcPhysicalTypeEditing" in java
    assert "event.getDeviceId()" in java
    assert "Character.isISOControl(unicode)" in java
    assert "!event.isCtrlPressed() && !event.isAltPressed()" in java
    assert "vcWakeNativeLoop();" in java
    assert 'imeEvents.offer("h" + new String(Character.toChars(unicode)));' in java
    assert "'h' if !payload.is_empty() => Some(egui::Event::Text(payload.to_owned()))" in bridge
    assert "'c' if !payload.is_empty()" in bridge  # preserve composing IME
    assert "ImeResetCompleted" in bridge              # preserve upstream reset
    assert "set_physical_type_editing" in host
    assert "last_physical_type_editing" in host
    assert "self.inner.session.tool_wants_text()" in host
    assert "self.ime.poll(ctx, raw);" in host
    assert "self.inner.raw_input_hook(ctx, raw);" in host
    assert "vc_document_changed()" in host
    assert "self.stylus_wheel.capture(ctx, raw, wheel_blocked);" in host
    assert "Check for updates at startup" in menu
    assert "ANDROID_STARTUP_ENABLED.load" in menu
    assert "vc_update_toast" in host
    assert "vc-update-notification" in host
    assert ".interactable(false)" in host
    assert "self.inner.ui.about = true;" not in host[host.index("        if check_updates {"):host.index("        // Adaptive cursor")]
    assert "session.commit(sender.getIntentSender())" in updater
    assert "verify" in updater
    assert "com.artcraft.vectorcraft" in updater
    assert "PackageInstaller" in updater
    assert "ANDROID_WHEEL_ENABLED" in menu or "Stylus Wheel" in menu
    print("PASS: Android.7 Type JNI bridge, scoped physical dispatch, reset retention, wheel parity and updater UI")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: test_v0241_android7_typing_updates.py STAGED_BUILDER")
    check(Path(sys.argv[1]))
