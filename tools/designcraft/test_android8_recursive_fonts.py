"""Android.8 recursive SAF font scan source guards."""
from pathlib import Path
import unittest


class Android8RecursiveFonts(unittest.TestCase):
    def test_recursive_scan_is_bounded_and_supports_collections(self):
        src = Path("tools/designcraft/support/font_methods.java").read_text()
        for required in (
            'pending.addLast(documentId)', 'seen.add(parentId)',
            'visitedFolders < 5000', 'count < 5000',
            'lower.endsWith(".ttc")',
            'first == \'t\' && second == \'t\'',
            '4L * 1024 * 1024 * 1024',
            'StandardCopyOption.ATOMIC_MOVE',
            'getPersistedUriPermissions()',
        ):
            self.assertIn(required, src)
        self.assertNotIn('count < 200', src)
        self.assertIn('64L * 1024 * 1024', src)


    def test_font_import_feedback_is_wired_to_completion_and_visible(self):
        """Guard the existing feedback UX against disappearing from Android.9 builds."""
        tablet = Path("tools/designcraft/support/tablet.rs").read_text()
        launcher = Path("tools/designcraft/support/patch_launcher.py").read_text()
        for required in (
            'static FONT_RESULT:', 'pub fn font_result(',
            'let font_event = FONT_RESULT.lock()', 'app.run("font.reload"',
            'self.notify(ui, format!("{message} — font list updated"), false)',
            'self.notify(ui, format!("Font import failed: {error}"), true)',
            'self.notify(ui, format!("Font import saved; reload failed: {error}"), true)',
            'fn show_notification(', 'self.show_notification(ui);',
            'egui::Order::Foreground',
            'ui.ctx().request_repaint_after(',
        ):
            self.assertIn(required, tablet)
        self.assertIn('tablet::font_result(Ok(format!("Imported font: {name}")))', launcher)
        self.assertIn('tablet::font_result(Err(error))', launcher)
        self.assertLess(tablet.index('let font_event = FONT_RESULT.lock()'),
                        tablet.index('self.show_notification(ui);'))

if __name__ == "__main__":
    unittest.main()
