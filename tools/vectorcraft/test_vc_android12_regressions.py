"""Cheap Android.12 test-candidate source guards; no Android toolchain needed."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tools/vectorcraft"

class Android12RegressionGuards(unittest.TestCase):
    def test_physical_keys_are_scoped_and_no_normal_typing_captured(self):
        patch = (BASE / "patch_android12_keyboard.py").read_text()
        for marker in (
            "mode == 1 && !imeWanted",
            "mode == 2",
            "event.isCtrlPressed()",
            "event.getRepeatCount() == 0",
            "event.isAltPressed()",
            "return super.dispatchKeyEvent(event)",
            "self.inner.session.active().is_some()",
            "raw.focused = true",
            "raw.events.push(egui::Event::Key",
            "vcSetHardwareShortcutMode",
            "vcPollPhysicalShortcut",
        ):
            self.assertIn(marker, patch)
        self.assertIn("if hardware_mode == 1", patch)
        self.assertNotIn("app.run(\"ui.dialog.confirm\"", patch)

    def test_modal_letters_save_cancel_and_discard_from_android(self):
        patch = (BASE / "patch_android12_keyboard.py").read_text()
        self.assertIn("(47, 2) => Some(egui::Key::S)", patch)
        self.assertIn("(31, 2) => Some(egui::Key::C)", patch)
        self.assertIn("(32, 2) => Some(egui::Key::D)", patch)
        self.assertIn("(111, 2) => Some(egui::Key::Escape)", patch)
        self.assertIn("dialog.kind == \"saveChanges\"", patch)

    def test_untouched_source_keys_gboard_ime(self):
        patch = (BASE / "patch_android12_keyboard.py").read_text()
        self.assertIn('event.isMetaPressed()', patch)
        self.assertIn("mode == 1 && !imeWanted", patch)
        self.assertIn("!editing && !field_focused && !composing", patch)
        self.assertIn("physicalShortcutKeys.clear()", patch)

    def test_startup_does_not_timeout_onto_black_native_frame(self):
        patch = (BASE / "patch_android12_startup.py").read_text()
        for marker in (
            "verifiedNativeFrames >= 3",
            "renderer_watchdog_active",
            "Tap to show editor",
            "startupCover.bringToFront()",
        ):
            self.assertIn(marker, patch)
        # The generator MUST contain the old timeout as its replacement
        # anchor; assert the safe replacement exists, then let CI's real
        # generated-source preflight inspect the final Java output.
        self.assertIn("cover.postDelayed(() -> {", patch)
        self.assertIn("cover.setOnClickListener", patch)

    def test_menu_smoothing_is_menu_only(self):
        patch = (BASE / "patch_android12_menu_scroll.py").read_text()
        for marker in (
            "Popup::is_any_open", "layer.order >= egui::Order::Foreground",
            "TouchPhase::Move", "MouseWheelSource::Trackpad",
            "request_repaint_after", "if !hovered_menu",
        ):
            self.assertIn(marker, patch)
        self.assertIn("self.menu_scroll.apply(ctx, raw)", patch)

    def test_guards_run_before_ndk_and_release_stays_forbidden(self):
        flow = (ROOT / ".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.19", flow)
        self.assertIn("VERSION_CODE: '16783379'", flow)
        self.assertIn("patch_android12_keyboard.py", flow)
        self.assertIn("patch_android12_startup.py", flow)
        self.assertIn("patch_android12_menu_scroll.py", flow)
        self.assertLess(flow.index("Enforce source, version, signing and test-only gates"),
                        flow.index("Install Android 35, tools and NDK 27.2 once"))
        self.assertNotIn("gh release create", flow)
        self.assertIn("com.artcraft.vectorcraft.test", flow)

if __name__ == "__main__":
    unittest.main()
