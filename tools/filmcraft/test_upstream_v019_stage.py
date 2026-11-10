"""Offline tests for the FilmCraft v0.19.0 isolated CI version stage.

No GitHub requests, signing keys, APK publication or project mutation.
"""
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_upstream_v019 as stage
import stage_upstream_v019_variant as variant

class StageV019Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "suite"
        self.assets = self.root / "tools/approved-branding/assets"
        self.tools = self.root / "tools/filmcraft"
        self.assets.mkdir(parents=True)
        self.tools.mkdir(parents=True)
        self.cfg = {
            "app": "filmcraft", "package": "com.artcraft.filmcraft",
            "version_name": "0.10.0-android.5", "version_code": 1000005,
            "previous_version_code": 1000004,
            "resources": {"res/drawable-xxxhdpi/ic_launcher_foreground.png": "unchanged"},
        }
        self.manifest = self.assets / "manifest.json"
        self.manifest.write_text(json.dumps(self.cfg))
        self.verifier = self.tools / "verify_android_features_apk_v019.py"
        self.old = '("com.artcraft.filmcraft", "1000005", "0.10.0-android.5")'
        self.verifier.write_text("expected = " + self.old + "\n")
        (self.tools / "stage_upstream_v019_variant.py").touch()

    def test_staging_changes_only_version_metadata(self):
        stage.stage(self.root)
        result = json.loads(self.manifest.read_text())
        self.assertEqual(result["version_name"], "0.19.0-android.1-test")
        self.assertEqual(result["package"], "com.artcraft.filmcraft.test")
        self.assertEqual(result["version_code"], 1900001)
        self.assertEqual(result["previous_version_code"], 1700001)
        self.assertEqual(result["resources"], self.cfg["resources"])
        self.assertIn("1900001", self.verifier.read_text())
        self.assertNotIn(self.old, self.verifier.read_text())

    def test_unreviewed_baseline_is_blocked_before_write(self):
        self.cfg["version_code"] = 1000999
        self.manifest.write_text(json.dumps(self.cfg))
        before = self.verifier.read_text()
        with self.assertRaisesRegex(ValueError, "baseline changed"):
            stage.stage(self.root)
        self.assertEqual(self.verifier.read_text(), before)

    def test_changed_verifier_is_blocked_before_write(self):
        self.verifier.write_text("expected = ('other', 'identity')")
        before = self.manifest.read_text()
        with self.assertRaisesRegex(ValueError, "verifier drifted"):
            stage.stage(self.root)
        self.assertEqual(self.manifest.read_text(), before)

    def test_builder_patch_is_single_use_and_preserves_other_apps(self):
        source = ("def example(app, version):\n"
                  "    code = version_code(version)\n"
                  "    return code\n")
        changed = variant.patch_text(source)
        self.assertIn('if app == "filmcraft":', changed)
        self.assertIn('version != "0.19.0"', changed)
        self.assertEqual(changed.count("code = version_code(version)"), 1)
        with self.assertRaises(ValueError):
            variant.patch_text(changed)

if __name__ == "__main__":
    unittest.main()
