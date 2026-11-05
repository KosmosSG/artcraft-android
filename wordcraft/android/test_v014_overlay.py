"""Integration test against the pinned v0.14.0 dialog implementation.

Run after CI checks out builder/source/wordcraft at the exact release commit.
No network, APK signing, or source checkout modifications.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from patch_unsaved_dcs import apply

REPO = Path(__file__).resolve().parents[2]
UPSTREAM = REPO / "builder" / "source" / "wordcraft" / "crates" / "ui-egui" / "src" / "dialogs"


class WordcraftV014OverlayTest(unittest.TestCase):
    def test_split_dialog_port_preserves_save_flow_and_isolation(self):
        with tempfile.TemporaryDirectory(prefix="wordcraft-v014-") as directory:
            root = Path(directory)
            target = root / "crates" / "ui-egui" / "src" / "dialogs"
            target.mkdir(parents=True)
            for filename in ("dispatch.rs", "chrome.rs"):
                shutil.copyfile(UPSTREAM / filename, target / filename)
            original_dispatch = (target / "dispatch.rs").read_text()
            original_chrome = (target / "chrome.rs").read_text()
            apply(root)
            dispatch = (target / "dispatch.rs").read_text()
            chrome = (target / "chrome.rs").read_text()
            self.assertIn('format!("{} (C)", tl!("Cancel"))', dispatch)
            self.assertIn('format!("{} (D)", tl!("Don\'t Save"))', dispatch)
            self.assertIn('format!("{} (S)", tl!("Save"))', dispatch)
            self.assertIn('app.run("ui.saveChanges", json!({"answer": answer}))', dispatch)
            self.assertIn("android_unsaved_dcs_active", dispatch)
            self.assertIn("android_capture_unsaved_dcs", dispatch)
            self.assertIn("wordcraft.unsaved.modal.backdrop", chrome)
            self.assertIn(".order(egui::Order::Foreground)", chrome)
            self.assertNotIn("wordcraft.unsaved.modal.backdrop", original_chrome)
            self.assertNotIn("android_capture_unsaved_dcs", original_dispatch)

    def test_missing_upstream_anchor_fails_without_mutating_checkout(self):
        with tempfile.TemporaryDirectory(prefix="wordcraft-v014-negative-") as directory:
            root = Path(directory)
            target = root / "crates" / "ui-egui" / "src" / "dialogs"
            target.mkdir(parents=True)
            for filename in ("dispatch.rs", "chrome.rs"):
                shutil.copyfile(UPSTREAM / filename, target / filename)
            before = (target / "dispatch.rs").read_text()
            chrome = target / "chrome.rs"
            original = chrome.read_text()
            chrome.write_text(original.replace(
                "let window = crate::window_close::window", "let window = changed_api",
                1,
            ))
            with self.assertRaises(ValueError):
                apply(root)
            self.assertEqual((target / "dispatch.rs").read_text(), before)


if __name__ == "__main__":
    unittest.main()
