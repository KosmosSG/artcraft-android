"""Android.25 reference gesture restore: fail-closed and feature-retention tests."""
from pathlib import Path
import tempfile
import unittest
from patch_android25_reference_gestures import patch_staged, restore_winit, install_build_hook

class Android25(unittest.TestCase):
    def test_exact_published_gesture_replaces_experimental_router(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            modified=base/"final/src/platform_impl/android/mod.rs"
            ref=base/"vendor/winit/src/platform_impl/android/mod.rs"
            modified.parent.mkdir(parents=True)
            ref.parent.mkdir(parents=True)
            prefix="KEEP_KEYBOARD_LIFECYCLE\n"
            suffix="\n                match motion_event.action() {\n                    // Hover: keep rest\nKEEP_STYLUS\n"
            release="                let pad_gesture = match motion_event.classification() {\n" + (
                "                    Classification::TwoFingerSwipe => PadGesture::Scroll,\n"
                "                    Classification::Pinch => PadGesture::Pinch,\n"
                "                    _ => PadGesture::None,\n"
                "                };\n"
                "                if pad_gesture != PadGesture::None {\n"
                "                    return input_status;\n"
                "                }\n")
            experimental="                let reported_pad_gesture = match motion_event.classification() {\n" + (
                "                    unclassified_pad; pad_fallback_gesture;\n"
                "                    clamp(-160.0, 160.0);\n"
                "                    factor.clamp(0.75, 1.33);\n"
                "                    return input_status;\n"
                "                }\n")
            ref.write_text(prefix+release+suffix)
            modified.write_text(
                "    pad_fallback_gesture: PadGesture,\n"
                "            pad_fallback_gesture: PadGesture::None,\n"
                +prefix+experimental+suffix
            )
            restore_winit(base/"final",ref)
            result=modified.read_text()
            self.assertIn(release,result)
            self.assertIn("KEEP_KEYBOARD_LIFECYCLE",result)
            self.assertIn("KEEP_STYLUS",result)
            self.assertNotIn("unclassified_pad",result)
            self.assertNotIn("pad_fallback_gesture",result)
            with self.assertRaises(ValueError):
                restore_winit(base/"final",ref)

    def test_popup_reference_path_and_boot_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            menu=root/"source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
            java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
            rust=root/"adapters/vectorcraft/src/lib.rs"
            for p in [menu,java,rust]:p.parent.mkdir(parents=True,exist_ok=True)
            menu.write_text('''KEEP_MENU_START
        let area = egui::ScrollArea::vertical().scroll_source(egui::containers::scroll_area::ScrollSource::ALL).max_height(room).min_scrolled_height(room);
        #[cfg(target_os = "android")]
        let area = area.id_salt("vectorcraft-android-smooth-menu")
            .wheel_scroll_multiplier(egui::vec2(1.0, 0.90));
        if ui.input(|input| input.is_scrolling()) {
            ui.ctx().request_repaint();
        }
        area.show(ui, add_contents).inner
KEEP_MENU_END''')
            java.write_text('KEYBOARD_SAFE\n        super.onCreate(savedInstanceState);\n        showStartupCover();\nMODAL_SAFE')
            rust.write_text('''    install_persist_env(&android_app);
    system_fonts::install_font_env(&android_app);''')
            patch_staged(root)
            self.assertIn("ScrollSource::ALL", menu.read_text())
            self.assertNotIn("wheel_scroll_multiplier",menu.read_text())
            self.assertIn("KEYBOARD_SAFE", java.read_text())
            self.assertIn("MODAL_SAFE", java.read_text())
            self.assertIn("android25_after_native_onCreate",java.read_text())
            self.assertIn("VC_BOOT25 after_font_environment",rust.read_text())
            with self.assertRaises(ValueError):patch_staged(root)

    def test_install_hook_after_android24(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=root/"lib/build-common.sh";p.parent.mkdir(parents=True)
            p.write_text('python3 "$ROOT/tools/vectorcraft_android24.py" "$SRC/vendor/winit" --winit')
            install_build_hook(root)
            output=p.read_text()
            self.assertLess(output.index("vectorcraft_android24.py"),output.index("vectorcraft_android25.py"))
            self.assertTrue((root/"tools/vectorcraft_android25.py").is_file())
            with self.assertRaises(ValueError):install_build_hook(root)

if __name__=="__main__":
    unittest.main()
