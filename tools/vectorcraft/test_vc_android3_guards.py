"""Android.3 source-level checks for the owner-reported VectorCraft regressions.

Run on GitHub Actions before native compilation to conserve minutes.
"""
from pathlib import Path
import unittest
from patch_vc_icon_menu_v021 import patch_sources

ROOT = Path(__file__).resolve().parents[2]


class VectorCraftAndroid3Guards(unittest.TestCase):
    def test_existing_brand_mark_becomes_vc_popup_trigger(self):
        menu = "pub use bar::menu_bar;\n"
        bar = '.filter(|(title, _)| *title != "VectorCraft").collect();'
        chrome = '''                let (r, _) = ui.allocate_exact_size(vec2(MARK, MARK), Sense::hover());
                crate::brand::paint_mark(ui, r);
                ui.add_space(6.0);'''
        menu, bar, chrome = patch_sources(menu, bar, chrome)
        self.assertIn("pub(crate) fn android_vc_menu", menu)
        self.assertIn('menu_body(app, ui, items, &mut clicked)', menu)
        self.assertIn('&& *title != "Vc"', bar)
        self.assertIn('menus::android_vc_menu(app, &mark);', chrome)
        self.assertIn('crate::brand::paint_mark(ui, r);', chrome)
        with self.assertRaises(ValueError):
            patch_sources(menu, bar, chrome)

    def test_launcher_padding_safe_and_legacy_both(self):
        script = (ROOT / "tools/vectorcraft/adaptive_safe.py").read_text()
        self.assertIn("CANVAS_PX * 0.65", script)
        self.assertIn("side * 0.78", script)
        self.assertIn('if app == "vectorcraft" and explicit is not None:', script)
        self.assertIn("mipmap-", script)

    def test_android_launch_theme_before_java_and_gpu(self):
        compact = (ROOT / "tools/vectorcraft/patch_compact_apk_v020.py").read_text()
        java = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        self.assertIn('android:windowBackground">#2d0000', compact)
        self.assertIn('theme = "@style/Theme.Artcraft"', compact)
        self.assertIn("showStartupCover();", java)
        self.assertIn("public void vcNativeUiReady()", java)
        self.assertIn("cover.postDelayed(this::dismissStartupCover, 15000)", java)

    def test_no_synchronous_font_rescan_and_bounded_persistent_scan(self):
        rust = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        extras = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        self.assertNotIn('self.inner.run("text.rescanFonts"', rust)
        self.assertIn('name("vectorcraft-font-index"', rust)
        self.assertIn("FontDb::global().load_system_fonts()", rust)
        self.assertIn("font_index_result: None", rust)
        for requirement in (
            "MAX_FONTS = 5000",
            "MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024",
            "MAX_FONTS_PER_PASS = 128",
            "MAX_SCAN_BATCH_BYTES = 64L * 1024 * 1024",
            "SCAN_STATE_NAME", "loadScanState(treeUri)",
            "saveScanState(p)",
            "takePersistableUriPermission",
        ):
            self.assertIn(requirement, extras)

    def test_published_signing_is_still_forbidden_in_candidate(self):
        workflow = (ROOT / ".github/workflows/vectorcraft-v021-test-apk.yml").read_text()
        self.assertIn("ORIGINAL_CERT:", workflow)
        self.assertIn("com.artcraft.vectorcraft.test", workflow)
        self.assertIn("Delete disposable builder signing materials", workflow)
        self.assertNotIn("gh release create", workflow)


if __name__ == "__main__":
    unittest.main()
