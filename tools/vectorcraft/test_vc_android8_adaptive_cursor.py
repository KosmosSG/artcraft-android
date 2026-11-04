"""Regression guard: selectively port ArtCraft builder v0.2.0 Adaptive Cursor.

This intentionally does NOT replace the tablet's winit/egui input stack.
Source: MostafaXS1/artcraft-android v0.2.0 pointer_icon.rs, Android API24+.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VectorCraftAndroid8AdaptiveCursor(unittest.TestCase):
    def test_all_reference_cursor_mappings_are_preserved(self):
        rust=(ROOT/"adapters/vectorcraft/src/adaptive_cursor.rs").read_text()
        for snippet in (
            "C::Default => 1000",
            "C::PointingHand => 1002",
            "C::Crosshair => 1007",
            "C::Text | C::VerticalText => 1008",
            "C::ResizeHorizontal | C::ResizeColumn",
            "C::ResizeVertical | C::ResizeRow",
            "C::Move | C::AllScroll => 1015",
            "C::ResizeNwSe | C::ResizeNorthWest",
            "C::ResizeNeSw | C::ResizeNorthEast",
            "C::None | C::Progress | C::Wait => return None",
        ):
            self.assertIn(snippet,rust)

    def test_android_activity_targets_real_native_surface_and_caches(self):
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        for marker in (
            "import android.view.PointerIcon;",
            "private volatile int nativePointerIconType = -1;",
            "public void vcSetAdaptivePointerIcon(int pointerType)",
            "pointerType == nativePointerIconType",
            "runOnUiThread(() ->",
            "SurfaceView nativeSurface = findNativeSurface(getWindow().getDecorView());",
            "nativeSurface.setPointerIcon(",
            "PointerIcon.getSystemIcon(this, nativePointerIconType)",
            "nativePointerIconType = -1;",
        ):
            self.assertIn(marker,java)

    def test_egui_cursor_selected_after_upstream_ui_and_no_replacement_of_input(self):
        rust=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        for marker in (
            "mod adaptive_cursor;",
            'jni_str!("vcSetAdaptivePointerIcon")',
            'jni_sig!("(I)V")',
            "last_adaptive_pointer_type: None",
            "self.menu_scroll.apply(ctx, raw);",
            "self.inner.raw_input_hook(raw);",
            "self.inner.ui(ui);",
            "ctx.output(|out| out.cursor_icon)",
            "adaptive_cursor::native_pointer_icon(",
            "self.bridge.set_adaptive_pointer_icon(pointer_type)",
        ):
            self.assertIn(marker,rust)
        self.assertLess(rust.index("self.inner.ui(ui);"),
                        rust.index("ctx.output(|out| out.cursor_icon)"))

    def test_egui_037_scroll_and_focus_compiler_regressions(self):
        # These 3 missing egui fields / stale borrow caused Actions
        # run #41858508545 to fail after the expensive ARM64 setup.
        src=(ROOT/"adapters/vectorcraft/src/android_modifiers.rs").read_text()
        self.assertIn("egui::Event::WindowFocused(_) => {", src)
        self.assertNotIn("let _ = focused; // retain the original focus event unchanged.",src)
        self.assertIn("egui::Event::MouseWheel { unit, delta, modifiers, source, .. }",src)
        self.assertIn("phase: egui::TouchPhase::Move,",src)
        self.assertNotIn("egui::Event::MouseWheel { unit, delta, modifiers, source }",src)
        self.assertIn("popup_easing_does_not_touch_canvas_wheel_events",src)

    def test_candidate_remains_disposable_and_preserves_fonts(self):
        workflow=(ROOT/".github/workflows/vectorcraft-v021-test-apk.yml").read_text()
        fonts=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.8",workflow)
        self.assertIn("com.artcraft.vectorcraft.test",workflow)
        self.assertIn("Delete disposable builder signing materials",workflow)
        self.assertIn("MAX_FONTS = 5000",fonts)
        self.assertIn("MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024",fonts)
        self.assertNotIn("gh release create",workflow)


if __name__=="__main__":
    unittest.main()
