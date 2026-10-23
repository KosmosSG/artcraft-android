"""Regression guards for the isolated VectorCraft Android enhancement build.

These tests do not require Android SDK, signing secrets, or an APK.
They prevent accidental loss of existing Android bridge/keyboard support and
ensure that the approved icon is selected before a candidate build.
"""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/vectorcraft-baseline.yml"
ICON = ROOT / "assets/branding/vectorcraft/vc-glass-approved.png"


class VectorCraftEnhancementGuards(unittest.TestCase):
    def test_launcher_icon_is_a_full_resolution_png(self):
        with ICON.open("rb") as fh:
            header = fh.read(24)
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(header[12:16], b"IHDR")
        width, height = struct.unpack(">II", header[16:24])
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 512)

    def test_workflow_builds_using_approved_icon(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("assets/branding/vectorcraft/vc-glass-approved.png", workflow)
        self.assertIn('"-appicon=$ICON"', workflow)
        self.assertIn("0.14.0-android.2", workflow)
        self.assertIn("vectorcraft-photocraft-parity-20261021", workflow)
        # Exact user-supplied artwork must be staged before an APK can build.
        self.assertIn("python3 tools/vectorcraft/verify_approved_icon.py \"$ORIGINAL\"", workflow)
        self.assertIn("install_android_brand.py", workflow)
        verifier = (ROOT / "tools/vectorcraft/verify_approved_icon.py").read_text()
        self.assertIn("291c7768cabaf4419082abfbd100a17668e9c7c4ca8a57fa45667f0f7233dbc2", verifier)
        self.assertIn("APPROVED_SIZE = (1254, 1254)", verifier)
        self.assertIn("Verify exact approved launcher icon before expensive builds", workflow)
        self.assertLess(workflow.index("Verify exact approved launcher icon before expensive builds"),
                        workflow.index("Install NDK"))

    def test_existing_android_features_are_preserved(self):
        rust = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        java = (
            ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/"
            "VectorCraftActivity.java"
        ).read_text()
        for marker in ("vcRequestOpen", "vcRequestSave", "apply_android_modifiers",
                       "system_fonts::install_font_env"):
            with self.subTest(marker=marker):
                self.assertIn(marker, rust)
        for marker in ("vcRequestOpen", "vcRequestSave"):
            with self.subTest(marker=marker):
                self.assertIn(marker, java)


    def test_photocraft_style_font_and_updater_bridge_is_packaged(self):
        manifest = (ROOT / "adapters/vectorcraft/Cargo.toml").read_text()
        rust = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        java = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        extras = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        workflow = WORKFLOW.read_text()
        for marker in ("vectorcraft-text", "android.permission.INTERNET", "com.artcraft.vectorcraft"):
            with self.subTest(marker=marker):
                self.assertIn(marker, manifest)
        for marker in ("vectorcraft_text::set_app_font_dir", '"text.rescanFonts"',
                       "vcRequestFontImport", "vcRequestFontFolder", "vcRefreshFontFolder",
                       "vcCheckForUpdates", "vcPollUpdateResult", "vcOpenUpdatePage",
                       "edit.keyboardShortcuts", "touch_dock.enabled",
                       "wgpu_render_state", "get_info()", "device.limits()"):
            with self.subTest(marker=marker):
                self.assertIn(marker, rust)
        native_menus = (ROOT / "tools/vectorcraft/patch_android_menus.py").read_text()
        for marker in ("Import Font (.ttf / .otf)", "Select Shared Font Folder",
                       "Refresh Shared Fonts", "Check for VectorCraft Updates",
                       "Touch Shortcut Pad", "Graphics Diagnostics",
                       "set_android_preferences"):
            with self.subTest(native_menu=marker):
                self.assertIn(marker, native_menus)
        self.assertNotIn("vectorcraft.android_tools_button", rust)
        self.assertIn("take_android_menu_bits", rust)
        for marker in ("vcRequestFontImport", "vcRequestFontFolder", "vcRefreshFontFolder",
                       "vcCheckForUpdates", "vcPollUpdateResult", "vcOpenUpdatePage",
                       "extras.handleActivityResult"):
            with self.subTest(marker=marker):
                self.assertIn(marker, java)
        for marker in ("Intent.ACTION_OPEN_DOCUMENT_TREE", "takePersistableUriPermission",
                       "getPersistedUriPermissions", "Fonts", "Imported", "Shared",
                       "MAX_FONT = 32L * 1024 * 1024", "MAX_FONTS = 200",
                       "MAX_FOLDERS = 1000", "vectorcraft-v", "HttpURLConnection",
                       "update_available", "up_to_date", "No published VectorCraft Android",
                       "VERSION.matcher", "RELEASE_PREFIX"):
            with self.subTest(marker=marker):
                self.assertIn(marker, extras)
        for marker in ("cp -a adapters/vectorcraft builder/adapters/vectorcraft",
                       "VectorCraftExtras.java", "javac -source 17"):
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)
        # Font scans have no external write permission; update checker opens verified release pages only.
        self.assertNotIn("Intent.FLAG_GRANT_WRITE_URI_PERMISSION", extras)
        self.assertNotIn("ACTION_INSTALL_PACKAGE", extras)

    def test_gpu_diagnostics_is_docked_and_never_floats(self):
        rust = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        diagnostic_panel = 'egui::Panel::bottom("vectorcraft.android.graphics_diagnostics")'
        editor = "self.inner.ui(ui);"
        self.assertIn(diagnostic_panel, rust)
        self.assertNotIn('egui::Window::new("VectorCraft Graphics Diagnostics")', rust)
        # The dock is allocated before the editor to reserve canvas space.
        self.assertLess(rust.index(diagnostic_panel), rust.index(editor))
        for marker in ("state.adapter.get_info()", "state.device.limits()",
                       "self.fonts.import_status", "self.fonts.shared_status",
                       'if ui.small_button("Close").clicked()',
                       "self.android_tools_open = !self.android_tools_open;"):
            with self.subTest(marker=marker):
                self.assertIn(marker, rust)

    def test_signing_guards_still_required_and_no_release_published(self):
        workflow = WORKFLOW.read_text()
        for marker in ("VECTORCRAFT_KEYSTORE_BASE64", "VECTORCRAFT_CERT_SHA256",
                       "previous_version_code", "verify_apk.py"):
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)
        self.assertNotIn("gh release create", workflow)
        self.assertNotIn("softprops/action-gh-release", workflow)


if __name__ == "__main__":
    unittest.main()
