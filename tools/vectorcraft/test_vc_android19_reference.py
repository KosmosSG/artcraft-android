"""VectorCraft Android.19 selective Mostafa main builder and IME regression checks."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"

class Android19MostafaCompatibilityTests(unittest.TestCase):
    def test_reference_focus_hides_ime_when_not_typing(self):
        s=(TOOLS/"patch_android19_reference_ime.py").read_text()
        for token in (
            'imeView.setVisibility(View.GONE);',
            'view.setVisibility(View.VISIBLE);',
            'view.setVisibility(View.GONE);',
            'view.setFocusable(false);',
            'view.setFocusableInTouchMode(false);',
            'vcWakeNativeLoop();',
            'vcLastModalKeyDownTime = downTime',
            'PixelCopy.request(source, bitmap',
            'native_window_painted',
        ): self.assertIn(token,s)
        self.assertNotIn('killProcess(',s)

    def test_compatible_latest_builder_and_separate_package(self):
        w=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn('BUILDER_SHA: 52308fbcb26d8d8625f35fc1f048813f8e1e12a8',w)
        self.assertIn('ref: 52308fbcb26d8d8625f35fc1f048813f8e1e12a8',w)
        self.assertIn('VERSION_NAME: 0.21.0-android.21',w)
        self.assertIn("VERSION_CODE: '16783381'",w)
        self.assertIn('patch_android19_reference_ime.py',w)
        self.assertIn('com.artcraft.vectorcraft.test',w)
        self.assertIn('Delete disposable builder signing materials',w)
        self.assertIn('bash builder/build.sh -vectorcraft --noupdate',w)
        self.assertIn('test "$(git -C builder/source/vectorcraft rev-parse HEAD)" = "$UPSTREAM_SHA"',w)
        legacy=ROOT/"adapters/vectorcraft/src/ime_bridge.rs"
        self.assertTrue(legacy.is_file(),"Mostafa builder no longer auto-copies owner IME bridge")
        legacy_source=legacy.read_text()
        self.assertIn("pub struct ImeBridge",legacy_source)
        self.assertIn('ARTCRAFT_ANDROID_IME_BRIDGE_V1',legacy_source)
        self.assertIn('fn translate(event: &str)',legacy_source)
        self.assertIn("pub fn poll(&mut self, raw: &mut egui::RawInput)",legacy_source)
        self.assertNotIn('gh release create',w)

if __name__=="__main__": unittest.main()
