"""Cheap source regressions for VectorCraft v0.20 Android.3 performance/size changes.

No full ARM64 rebuild, local Android SDK, signing keys, or network required.
"""
import unittest
from pathlib import Path
from patch_compact_apk_v020 import UNUSED_DEPS, APPCOMPAT_THEME, NATIVE_THEME, patch_source, patch_native_theme
from patch_cached_system_fonts_v020 import OLD, apply

ROOT = Path(__file__).resolve().parents[2]


class Android3OptimizationSourceTests(unittest.TestCase):
    def test_compact_package_removes_only_unneeded_native_activity_dependencies(self):
        project = "base\n" + UNUSED_DEPS + "\nother"
        actual = patch_source(
            project,
            "import android.view.View; public class VectorCraftActivity extends NativeActivity {}",
            "import android.provider.DocumentsContract; class VectorCraftExtras {}",
            'features = ["native-activity"]',
        )
        self.assertIn("VectorCraftActivity extends android.app.NativeActivity", actual)
        for item in ("androidx.appcompat", "androidx.games", "kotlin-bom"):
            self.assertNotIn(item, actual)
        self.assertIn("base\n", actual)
        self.assertIn("\nother", actual)

    def test_compact_native_theme_uses_framework_noactionbar_style(self):
        generated = f'<resources>\n{APPCOMPAT_THEME}\n<item name="android:windowFullscreen">true</item>\n<item name="android:windowBackground">@android:color/black</item>\n</resources>'
        updated = patch_native_theme(generated)
        self.assertIn(NATIVE_THEME, updated)
        self.assertNotIn(APPCOMPAT_THEME, updated)
        self.assertIn('android:windowFullscreen', updated)
        self.assertIn('android:windowBackground', updated)
        with self.assertRaises(ValueError):
            patch_native_theme(updated)
        with self.assertRaises(ValueError):
            patch_native_theme('<resources/>')

    def test_compact_package_rejects_androidx_usage(self):
        with self.assertRaises(ValueError):
            patch_source(
                UNUSED_DEPS,
                "import androidx.foo.Bar; class VectorCraftActivity extends NativeActivity {}",
                "class VectorCraftExtras {}",
                'native-activity',
            )
        with self.assertRaises(ValueError):
            patch_source(
                UNUSED_DEPS,
                "class VectorCraftActivity extends GameActivity {}",
                "class VectorCraftExtras {}",
                'native-activity',
            )

    def test_font_links_cached_without_disabling_runtime_refresh(self):
        base = "start\n" + OLD + "\nrefresh_font_links();\nend"
        updated = apply(base)
        self.assertIn('root.is_dir()', updated)
        self.assertIn('vectorcraft-font-links-cache-v1', updated)
        self.assertIn('link_fonts(&root)', updated)
        self.assertIn('remember_font_state(state)', updated)
        self.assertIn('refresh_font_links();', updated)
        with self.assertRaises(ValueError):
            apply(updated)

    def test_feature_preservation_and_reduced_size_build_gates(self):
        shell = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        mod = (ROOT / "adapters/vectorcraft/src/android_modifiers.rs").read_text()
        workflow = (ROOT / ".github/workflows/vectorcraft-v020-test-apk.yml").read_text()
        self.assertIn("VectorCraft startup diagnostic: first_ui", shell)
        self.assertIn("VectorCraft startup diagnostic: font_environment", shell)
        self.assertIn("classify_android_precision_scroll(raw);", shell)
        self.assertIn("MouseWheelSource::Trackpad", mod)
        self.assertIn("consume_type_close_chord", shell)
        self.assertIn("vcRequestFontFolder", (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text())
        for marker in ("patch_compact_apk_v020.py", "patch_cached_system_fonts_v020.py",
                       "CARGO_PROFILE_RELEASE_STRIP", "size-report.json", "0.20.0-android.3"):
            self.assertIn(marker, workflow)
        self.assertIn("workflow_dispatch:", workflow)
        if "\n  push:" in workflow:
            # A one-shot build commit temporarily enables push for THIS workflow
            # file alone. The next commit immediately restores manual-only.
            self.assertEqual(workflow.count("\n  push:"), 1)
            self.assertIn("      - .github/workflows/vectorcraft-v020-test-apk.yml", workflow)
            self.assertIn("      - development/vectorcraft-v020-android14-20261102", workflow)
        else:
            self.assertIn("  workflow_dispatch:", workflow)


if __name__ == "__main__":
    unittest.main()
