#!/usr/bin/env python3
"""Source-only regression checks for the DesignCraft v0.16 Android review branch.

These checks inspect source contracts; they do NOT prove an APK has built or that
features work on an Android device. Production publication remains a separate gate.
"""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "lib" / "build-common.sh"
LOCK = ROOT / "configs" / "upstream" / "designcraft-v016.json"


class DesignCraftV016SourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = BUILDER.read_text(encoding="utf-8")
        cls.lock = json.loads(LOCK.read_text(encoding="utf-8"))

    def test_stable_upstream_lock(self):
        self.assertEqual(self.lock["schema_version"], 1)
        self.assertEqual(self.lock["official_upstream"], "storytold/designcraft")
        self.assertEqual(self.lock["stable_tag"], "v0.16.0")
        self.assertEqual(self.lock["upstream_workspace_version"], "0.16.0")
        self.assertRegex(self.lock["tag_commit"], r"^[a-f0-9]{40}$")
        self.assertFalse(self.lock["android_source_port_complete"])
        self.assertFalse(self.lock["android_build_verified"])
        self.assertFalse(self.lock["permanent_signing_authorized"])
        self.assertFalse(self.lock["production_release_authorized"])

    def test_pinned_checkout_does_not_overwrite_existing_sources(self):
        self.assertIn('git clone --depth 1 --branch v0.16.0 "$REPO" "$SRC"', self.shell)
        self.assertIn('ACTUAL_SOURCE_SHA', self.shell)
        self.assertIn('"$DESIGNCRAFT_LOCKED_COMMIT"', self.shell)
        self.assertIn("Preserve it: run this in a separate clean builder checkout", self.shell)
        self.assertIn('echo "Source is not automatically reset or updated."', self.shell)

    def test_review_build_is_debug_only(self):
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true && "$APP" != "designcraft" ]]', self.shell)
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true && "$MODE" != "debug" ]]', self.shell)
        self.assertIn("production/release signing is blocked", self.shell)

    def test_recovery_persisted_per_designcraft_instance(self):
        self.assertIn('let recovery_root = dir.join("Recovery");', self.shell)
        self.assertIn('inner.session.recovery_dir = Some(run_dir);', self.shell)
        self.assertIn('"file.recovery.open"', self.shell)
        self.assertIn('"file.recovery.save"', self.shell)
        self.assertIn('inner.session.documents().iter().any(|d| d.is_dirty())', self.shell)

    def test_existing_android_behaviors_remain_in_source(self):
        activity = (ROOT / "templates" / "android" / "SafActivity.java").read_text()
        self.assertIn("private File newStageFile(String name, Uri uri)", activity)
        self.assertIn('stem + " (" + attempt + ")" + extension', activity)
        self.assertIn('com.artcraft.', self.shell)
        self.assertIn('designcraft deckcraft gridcraft', self.shell)
        self.assertIn('"designcraft": {', self.shell)
        self.assertTrue((ROOT / "templates" / "android" / "ime_bridge.rs").is_file())
        self.assertTrue((ROOT / "templates" / "android" / "system_fonts.rs").is_file())

    def test_source_review_cannot_claim_publication(self):
        self.assertFalse(self.lock.get("production_release_authorized", False))
        self.assertFalse(self.lock.get("permanent_signing_authorized", False))


if __name__ == "__main__":
    unittest.main()
