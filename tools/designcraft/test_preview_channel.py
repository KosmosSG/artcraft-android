"""DesignCraft development source guard for the owner's release-channel preference.

No assumption about a signed, installed APK is made by these checks.
"""
from pathlib import Path
import unittest

CODE = Path(__file__).resolve().parent / "support" / "update_methods.java"

class DesignCraftPreviewChannelContract(unittest.TestCase):
    def test_owner_can_toggle_previews_with_persistent_pref(self):
        source = CODE.read_text()
        self.assertIn("Stable + Preview Releases", source)
        self.assertIn('getBoolean("dc_include_preview_releases", true)', source)
        self.assertIn('"dc_include_preview_releases", checked', source)
        self.assertIn('(!includePreview && release.optBoolean("prerelease"))', source)
        self.assertIn('release.optBoolean("draft")', source)
        self.assertIn("DesignCraftUpdatePolicy.validate", source)
        self.assertIn("DesignCraftUpdatePolicy.newer", source)
        self.assertIn('if (url != null)', source)
        self.assertNotIn('ACTION_INSTALL_PACKAGE', source)

if __name__ == "__main__":
    unittest.main()
