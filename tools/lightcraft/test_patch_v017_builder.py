"""Offline tests of the fail-closed LightCraft v0.17 Android builder patch."""
import unittest

from patch_v017_builder import MARKER, patch_source


class LightCraftV017BuilderTests(unittest.TestCase):
    @staticmethod
    def fixture():
        return '''SAF_RECIPES = {
    "lightcraft": {
        "state": "something",
        "services": \'\'\'
fn saf_services(bridge: saf::Bridge, state: Arc<SafState>, _inbox: SafInbox) -> Services {
    let write_bridge = bridge.clone_ref();
    Services {
        write: Some(Box::new(move |path: &str, bytes: &[u8]| saf_write_and_commit(&write_bridge, path, bytes))),
        ..Services::default()
    }
}
\'\'\',
    },
    "cadcraft": {
        "state": "must not be changed",
    },
}
'''

    def test_adds_no_clobber_private_writer_and_preserves_other_apps(self):
        patched = patch_source(self.fixture())
        self.assertIn(MARKER, patched)
        self.assertIn('create_new(true)', patched)
        self.assertIn('Component::Normal(std::ffi::OsStr::new("media"))', patched)
        self.assertIn('write_new: Some(Box::new(', patched)
        self.assertIn('        "state": "must not be changed",', patched)

    def test_idempotent(self):
        once = patch_source(self.fixture())
        self.assertEqual(once, patch_source(once))

    def test_rejects_missing_services_anchor(self):
        with self.assertRaisesRegex(ValueError, 'Services recipe layout changed'):
            patch_source(self.fixture().replace('        "services":', '        "service":'))

    def test_rejects_modified_existing_writer(self):
        with self.assertRaisesRegex(ValueError, 'Existing LightCraft SAF write service'):
            patch_source(self.fixture().replace('saf_write_and_commit(&write_bridge', 'unknown_writer(&write_bridge'))

    def test_rejects_existing_unreviewed_new_writer(self):
        with self.assertRaisesRegex(ValueError, 'already exists'):
            patch_source(self.fixture().replace('        ..Services::default()', '        write_new: Some(Box::new(|| Ok(()))),\n        ..Services::default()'))


if __name__ == '__main__':
    unittest.main()
