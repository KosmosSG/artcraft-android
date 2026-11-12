"""Android.12 lifecycle contract checks; behavioral/device relaunch remains separate."""
import os, unittest
from pathlib import Path

class RelaunchIME(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("VC_ANDROID12_STAGED"),"generated adapter only")
    def test_rebind_once_and_reject_old_connection(self):
        root=Path(os.environ["VC_ANDROID12_STAGED"])
        java=(root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        self.assertIn("(!alreadyFocused || vcImeNeedsRebind)",java)
        self.assertIn("vcImeNeedsRebind = false;",java)
        self.assertIn("vcImeGeneration++;\n                    imm.restartInput(view);",java)
        self.assertIn("connectionGeneration != vcImeGeneration",java)
        self.assertEqual(java.count("vcTraceRejected.incrementAndGet();"),6)
        self.assertIn('vcImeFocusEpoch.incrementAndGet();\n        vcImeGeneration++;',java)
        self.assertIn('VC_IME12 old_activity_connection_invalidated',java)
        self.assertIn('VC_IME12 first_edit_rebind completed',java)
        self.assertNotIn("System.exit(",java)
        self.assertNotIn("killProcess(",java)

    def test_patch_requires_reviewed_anchor(self):
        from tempfile import TemporaryDirectory
        from patch_android12_relaunch_ime import once
        with self.assertRaises(ValueError): once("no anchor","missing","replacement")
        with self.assertRaises(ValueError): once("duplicate duplicate","duplicate","replacement")
        self.assertEqual(once("before anchor after","anchor","new"),"before new after")

if __name__=="__main__": unittest.main()
