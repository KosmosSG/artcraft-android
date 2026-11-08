"""Fail-closed EffectCraft 0.21 disposable test identity and feature-preservation checks."""
import json
from pathlib import Path
import tempfile
import unittest
from v021_compat import (
    ANDROID_TEST_VERSION, TEST_VERSION_CODE, TEST_PACKAGE, UPSTREAM_SHA,
    stage_trial_metadata, stage_trial_branding_metadata, menu_path_and_anchor
)
from v020_compat import MODERN_ANCHOR

class TrialGuards(unittest.TestCase):
    def test_exact_pinned_sources_and_separate_test_package(self):
        self.assertEqual(len(UPSTREAM_SHA), 40)
        self.assertEqual(ANDROID_TEST_VERSION, "0.21.0-android.12")
        self.assertEqual(TEST_PACKAGE, "com.artcraft.effectcraft.v021test12")
        self.assertGreater(TEST_VERSION_CODE, 16781320)

    def test_rewrite_disposable_metadata_once(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "lib/build-common.sh"
            path.parent.mkdir(parents=True)
            path.write_text('version_line = f\'version = "{app_version}-android.3"\' if app == "effectcraft" else "version.workspace = true"\nversion_code = 16781315\n')
            stage_trial_metadata(root)
            data = path.read_text()
            self.assertIn('version_code = 16820012', data)
            self.assertIn('{app_version}-android.12', data)
            with self.assertRaisesRegex(RuntimeError, "STOP"):
                stage_trial_metadata(root)

    def test_preserve_all_branding_fields_except_version(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "tools/approved-branding/assets/manifest.json"
            path.parent.mkdir(parents=True)
            original = {
                "app": "effectcraft",
                "package": "com.artcraft.effectcraft",
                "version_name": "0.16.0-android.8",
                "version_code": 16781320,
                "source_sha256": "approved-art-digest",
                "resources": {"res/drawable-nodpi/icon.png": "approved-asset-digest"}
            }
            path.write_text(json.dumps(original))
            stage_trial_branding_metadata(root)
            updated = json.loads(path.read_text())
            self.assertEqual(updated["version_name"], ANDROID_TEST_VERSION)
            self.assertEqual(updated["version_code"], TEST_VERSION_CODE)
            for k in original.keys() - {"version_name", "version_code"}:
                self.assertEqual(updated[k], original[k])
            with self.assertRaisesRegex(RuntimeError, "STOP"):
                stage_trial_branding_metadata(root)

    def test_modern_menus_and_safe_failure_on_upstream_drift(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "crates/ui-egui/src/menus/bar.rs"
            path.parent.mkdir(parents=True)
            path.write_text(MODERN_ANCHOR)
            self.assertEqual(menu_path_and_anchor(root)[0], path)
            path.write_text("changed upstream menu; do not overwrite")
            with self.assertRaisesRegex(RuntimeError, "drift"):
                menu_path_and_anchor(root)

if __name__ == "__main__":
    unittest.main()
