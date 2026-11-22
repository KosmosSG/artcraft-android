import os, shutil, tempfile, unittest
from pathlib import Path
from patch_unsaved_dcs import apply
class PatchTests(unittest.TestCase):
    def test_exact_dialog_and_save_workflow_preserved(self):
        root=os.environ.get('WORDCRAFT_UPSTREAM')
        if not root: self.skipTest('WORDCRAFT_UPSTREAM fixture required')
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'crates/ui-egui/src/dialogs.rs';target.parent.mkdir(parents=True)
            original=(Path(root)/'crates/ui-egui/src/dialogs.rs').read_text();target.write_text(original)
            apply(tmp);actual=target.read_text()
            self.assertIn('Some(3) => Some("save")',actual)
            for key in 'DCS': self.assertIn(' ('+key+')',actual)
            self.assertIn('let _ = app.run("ui.saveChanges", json!({"answer": answer}));',actual)
            before=original.split('        Dialog::SaveChanges { name, message, .. } => {')[0]
            self.assertTrue(actual.startswith(before))
            with self.assertRaises(ValueError): apply(tmp)
if __name__=='__main__': unittest.main()
