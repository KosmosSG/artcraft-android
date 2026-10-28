from pathlib import Path
import os,tempfile,unittest
from patch_unsaved_dcs import apply
from font_paths import patch_android_font_paths

@unittest.skipUnless(os.environ.get('FILMCRAFT_UPSTREAM'), 'pinned source fixture required')
class DcsPatch(unittest.TestCase):
    def test_reapply_refuses_and_save_workflow_is_unchanged(self):
        source=Path(os.environ['FILMCRAFT_UPSTREAM'])/'crates/ui-egui/src/panels/clip_dialogs.rs'
        original=source.read_text()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'crates/ui-egui/src/panels/clip_dialogs.rs'
            target.parent.mkdir(parents=True);target.write_text(original)
            apply(d); patched=target.read_text()
            self.assertIn('Some(3) if can_save',patched)
            start='    match action {'
            end='/// The parameters sent on OK'
            self.assertEqual(original[original.index(start):original.index(end)],patched[patched.index(start):patched.index(end)])
            with self.assertRaises(ValueError): apply(d)
            self.assertEqual(target.read_text(),patched)
