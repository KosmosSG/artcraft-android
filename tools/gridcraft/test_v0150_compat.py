"""Regression guards for the v0.15.0 GridCraft Android source-only review."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FOLDER = Path(__file__).resolve().parent

class GridCraftV0150ReviewTests(unittest.TestCase):
    def test_source_pin_does_not_authorize_production(self):
        lock = json.loads((FOLDER / "source-lock.json").read_text())
        self.assertEqual(lock["official_release_tag"], "v0.15.0")
        self.assertEqual(lock["version_name"], "0.15.0-android.1")
        self.assertEqual(lock["intended_release_tag"], "gridcraft-v0.15.0-android.1")
        self.assertEqual(lock["official_release_commit"], "30b210b4ef03b30616923465efa70766cefba379")
        self.assertEqual(lock["baseline_android_source_commit"], "720fab9eaa178da485750009f1a2782026da6286")
        self.assertTrue(lock["upstream_review_only"])
        self.assertIsNone(lock["version_code_reserved"])
        self.assertFalse(lock["build_approved"])
        self.assertFalse(lock["publish_approved"])

    def test_android_candidate_version_and_manual_only_build(self):
        installer = (FOLDER / "install_overlay.py").read_text()
        workflow = (FOLDER.parent.parent / ".github/workflows/gridcraft-v0150-test-once.yml").read_text()
        self.assertIn("GRIDCRAFT_ANDROID_VERSION_NAME_V1", installer)
        self.assertIn('"0.15.0-android.1" if app == "gridcraft"', installer)
        self.assertIn("versionName=\'0.15.0-android.1\'", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\\n  push:", workflow)

    def test_tested_android_overlay_still_exists(self):
        installer = (FOLDER / "install_overlay.py").read_text()
        java = (FOLDER / "android_addons" / "GridCraftJavaMethods.java.inc").read_text()
        modal = (FOLDER / "patch_unsaved_dcs.py").read_text()
        for marker in ("GRIDCRAFT_ANDROID_IMPORTED_FONTS_V1", "GRIDCRAFT_USER_ADAPTIVE_ICON_V2"):
            self.assertIn(marker, installer)
        for marker in ("gcImportFont()", "gcSelectSharedFolder()", "gcRefreshSharedFolder()", "gcCheckForUpdates()"):
            self.assertIn(marker, java)
        self.assertIn("android_save_and_close", modal)
        self.assertTrue((FOLDER / "editor_escape.rs").is_file())

    def test_compat_scanner_flags_changed_api(self):
        spec = importlib.util.spec_from_file_location("compat", FOLDER / "check_upstream_port_compat.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text("[workspace]\n")
            for path, marker in module.ANCHORS.values():
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("a") as stream:
                    stream.write(marker + "\n")
            first = module.audit(root)
            self.assertFalse(first["manual_port_required"])
            path, _ = module.ANCHORS["save_changes_dialog"]
            (root / path).write_text("upstream moved save dialog\n")
            second = module.audit(root)
            self.assertTrue(second["manual_port_required"])
            self.assertIn("save_changes_dialog", second["missing_or_changed_anchors"])
            self.assertFalse(second["apk_compilation_verified"])

if __name__ == "__main__":
    unittest.main()
