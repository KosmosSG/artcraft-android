"""Source-level tests for separately installable VectorCraft v0.21 candidate."""
import unittest
from patch_test_package_v021 import (
    patch_generator, patch_manifest, ORIGINAL_GRADLE,
    ORIGINAL_ACTIVITY, TEST_GRADLE, TEST_ACTIVITY,
)


class SeparateTestPackage(unittest.TestCase):
    def test_preserves_java_namespace_but_uses_test_application_id(self):
        fixture = "namespace '{_groovy(namespace)}'\n" + ORIGINAL_GRADLE + "\n" + ORIGINAL_ACTIVITY
        result = patch_generator(fixture)
        self.assertIn("namespace '{_groovy(namespace)}'", result)
        self.assertIn(TEST_GRADLE, result)
        self.assertIn(TEST_ACTIVITY, result)
        self.assertIn("com.artcraft.vectorcraft.VectorCraftActivity", result)
        self.assertNotIn(ORIGINAL_GRADLE, result)

    def test_changes_only_disposable_build_labels(self):
        sample = ('package = "com.artcraft.vectorcraft"\n'
                  'label = "VectorCraft"\nlabel = "VectorCraft"\n')
        got = patch_manifest(sample)
        self.assertIn('package = "com.artcraft.vectorcraft"', got)
        self.assertEqual(got.count('label = "VectorCraft Test"'), 2)

    def test_rejects_changed_builder_or_package(self):
        with self.assertRaises(ValueError):
            patch_generator('applicationId "unreviewed"')
        with self.assertRaises(ValueError):
            patch_manifest('package = "com.artcraft.vectorcraft.test"\n')


if __name__ == "__main__":
    unittest.main()
