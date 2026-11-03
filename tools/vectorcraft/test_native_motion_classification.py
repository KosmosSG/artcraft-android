"""Pure-Python regressions for the pinned android-activity 0.6.1 NativeActivity shim."""
import unittest

from patch_android_native_classification import (
    IMPORT_ANCHOR,
    FUNCTION_ANCHOR,
    METHOD_ANCHOR,
    add_native_motion_classification,
)


def original_native_fixture():
    return (
        "use crate::input::{\n"
        + IMPORT_ANCHOR
        + "};\n\n"
        + "fn action_button_fn() {\n"
        + FUNCTION_ANCHOR
        + "\nimpl MotionEvent<'_> {\n"
        + METHOD_ANCHOR
        + "\n}\n\n"
        + "pub struct KeyEvent<'a> { _phantom: &'a () }\n"
        + "impl KeyEvent<'_> {\n"
        + METHOD_ANCHOR
        + "\n}\n"
    )


class NativeMotionClassificationTests(unittest.TestCase):
    def test_only_motion_event_receives_new_method(self):
        patched = add_native_motion_classification(original_native_fixture())
        motion, key = patched.split("pub struct KeyEvent", 1)
        self.assertEqual(patched.count("pub fn classification(&self) -> Classification"), 1)
        self.assertIn("pub fn classification(&self) -> Classification", motion)
        self.assertNotIn("pub fn classification(&self)", key)
        self.assertIn("Classification, EdgeFlags", patched)
        self.assertIn('b"AMotionEvent_getClassification\\0"', patched)
        self.assertIn("libc::dlsym(libc::RTLD_DEFAULT", patched)
        self.assertIn(".unwrap_or(0)", patched)
        self.assertNotIn("ndk_sys::AMotionEvent_getClassification(", patched)

    def test_rejects_already_patched_source(self):
        patched = add_native_motion_classification(original_native_fixture())
        with self.assertRaises(ValueError):
            add_native_motion_classification(patched)

    def test_rejects_unrecognised_android_activity(self):
        broken = original_native_fixture().replace("pub struct KeyEvent", "pub struct SomethingElse")
        with self.assertRaises(ValueError):
            add_native_motion_classification(broken)

    def test_rejects_missing_action_button_anchor(self):
        broken = original_native_fixture().replace(FUNCTION_ANCHOR, "    })\n}\n\n/// Unexpected event")
        with self.assertRaises(ValueError):
            add_native_motion_classification(broken)


if __name__ == "__main__":
    unittest.main()
