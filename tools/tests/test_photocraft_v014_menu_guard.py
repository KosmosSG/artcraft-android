"""Prevent regressions in the PhotoCraft 0.14 Android menu patch migration."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from photocraft_v014_menu_guard import IDS, EXPECTED_HOOKS, validate_menu_text, validate_checkout


def complete_menu():
    return "\n".join((
        *IDS, *EXPECTED_HOOKS,
        "pub fn is_enabled(app: &PhotocraftApp, id: &str) -> bool {",
        "pub fn is_live(id: &str) -> bool {",
    ))


class V014MenuGuardTests(unittest.TestCase):
    def test_all_six_commands_and_hooks_accepted(self):
        validate_menu_text(complete_menu())

    def test_missing_each_menu_command_is_rejected(self):
        for command in IDS:
            with self.subTest(command=command), self.assertRaises(ValueError):
                validate_menu_text(complete_menu().replace(command, ""))

    def test_missing_upstream_command_hooks_is_rejected(self):
        for marker in EXPECTED_HOOKS:
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                validate_menu_text(complete_menu().replace(marker, ""))

    def test_unverified_source_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "expected a checkout"):
                validate_checkout(Path(directory))

    def test_builder_has_explicit_version_bound_guard_and_keeps_legacy_behavior(self):
        script = (ROOT / "lib/build-common.sh").read_text()
        self.assertIn('ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME:-}', script)
        self.assertIn('== "0.14.0-android.1"', script)
        self.assertIn('photocraft_v014_menu_guard.py', script)
        self.assertIn('git -C "$SRC" apply "$MENU_PATCH"', script)
        self.assertIn('fail "PhotoCraft upstream menus.rs has changed', script)


if __name__ == "__main__":
    unittest.main()
