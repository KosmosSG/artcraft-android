"""WordCraft android.2 acceptance-guard tests for source-level wiring.

These tests catch accidental loss of the requested icon, raw D/C/S intercept
and font scan limits. Device interactions still require MagicPad testing.
"""
from pathlib import Path
import ast
import unittest

HERE = Path(__file__).resolve().parent
BUILD = HERE / "patch_builder.py"
RIBBON = HERE / "ribbon_android.rs.inc"
RUST = HERE / "wordcraft_android.rs"
JAVA = HERE / "WordCraftExtension.java.inc"
WORKFLOW = HERE.parent.parent / ".github" / "workflows" / "wordcraft-v014-candidate.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class WordCraftDeviceFixes(unittest.TestCase):
    def test_builder_shim_parses_and_wires_raw_keys_before_clipboard(self):
        s = text(BUILD)
        ast.parse(s)
        self.assertIn('wc_raw_dcs = ', s)
        self.assertIn('self.wc.capture_unsaved_keys(self.inner.android_unsaved_dcs_active(), ctx, raw)', s)
        self.assertIn('{wc_raw_dcs}        self.handle_clipboard_shortcuts(raw);', s)

    def test_approved_icon_is_derived_from_launcher_and_not_unrelated_asset(self):
        s = text(BUILD)
        self.assertIn('wordcraft-approved-192.png', s)
        self.assertIn('resize((40, 40)', s)
        self.assertIn('wordcraft-android-menu-icon.rgba', s)
        menu = text(RIBBON)
        self.assertIn('include_bytes!("wordcraft-android-menu-icon.rgba")', menu)
        self.assertIn('egui::ColorImage::from_rgba_unmultiplied([40, 40], rgba)', menu)
        self.assertIn('egui::ImageButton::new', menu)
        self.assertIn('egui::Popup::menu(&button)', menu)
        self.assertNotIn('ui.menu_button("ArtCraft"', menu)
        self.assertIn('place WordCraft launcher icon menu at top left of tab strip', s)

    def test_raw_key_dcs_preempts_editor_and_does_not_override_pending_choice(self):
        s = text(RUST)
        self.assertIn('pub fn capture_unsaved_keys(&self, active: bool, ctx: &egui::Context, raw: &mut egui::RawInput)', s)
        for k in ("D", "C", "S"):
            self.assertIn('egui::Key::' + k, s)
        self.assertIn('raw.events.retain', s)
        self.assertIn('if !modifiers.any()', s)
        self.assertIn('if d.get_temp::<u8>(id).is_none()', s)
        self.assertIn('ctx.request_repaint();', s)
        java = text(JAVA)
        self.assertIn('wcDialogAction.compareAndSet(0, action)', java)
        self.assertIn('if (!active) { wcDialogAction.set(0); return 0; }', java)

    def test_shared_scan_caps_5000_files_and_4_gib_and_stays_async(self):
        s = text(JAVA)
        for anchor in (
            'private static final int WC_MAX_FONTS = 5_000;',
            'private static final int WC_MAX_FOLDERS = 20_000;',
            'private static final long WC_MAX_FONT_TOTAL_BYTES = 4L * 1024 * 1024 * 1024;',
            'io.execute(() -> wcScanFontTree(Uri.parse(saved)));',
            'while (!pending.isEmpty() && scannedFolders < WC_MAX_FOLDERS && copied < WC_MAX_FONTS',
            'while (cursor.moveToNext() && copied < WC_MAX_FONTS',
            'pending.size() + seen.size() < WC_MAX_FOLDERS',
            'total > WC_MAX_SINGLE_FONT_BYTES',
            'copiedBytes + total > WC_MAX_FONT_TOTAL_BYTES',
            'result.put("maxFonts", WC_MAX_FONTS)',
        ):
            self.assertIn(anchor, s)
        self.assertNotIn('copied < 150', s)
        self.assertNotIn('copiedBytes < 200L * 1024 * 1024', s)
        self.assertIn('for _ in 0..8 {', text(RUST))
        self.assertIn('5,000 files / 4 GiB maximum', text(RIBBON))

    def test_candidate_build_has_new_test_and_temp_key_not_original(self):
        s = text(WORKFLOW)
        self.assertIn("test_wordcraft_device_fixes.py", s)
        self.assertIn("0.14.0-android.2", s)
        self.assertIn('100014002', s)
        self.assertIn('TEMP-SIGNED-NO-UPGRADE', s)
        self.assertNotIn("0.14.0-android.1", s)


if __name__ == "__main__":
    unittest.main()
