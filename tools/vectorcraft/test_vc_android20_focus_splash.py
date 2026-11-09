"""VectorCraft Android.20 focus/native wake and responsive launch regression guards."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"
class Android20Guards(unittest.TestCase):
    def test_direct_native_wake_and_modal_handoff(self):
        p=(TOOLS/"patch_android20_native_keyboard_splash.py").read_text()
        for symbol in (
            'return super.dispatchKeyEvent(event);',
            'com.artcraft.ime.ArtCraftIme.wake();',
            'raw.events.retain(|event| match event',
            'physical_key.unwrap_or(*native) != key',
            'vc_after_type_exit_frames',
            'just_exited_type',
            'View decor = getWindow().getDecorView();',
            'decor.requestFocus();',
            'nativeSurface.requestFocus();',
        ): self.assertIn(symbol,p)
        self.assertNotIn('finishAndRemoveTask()',p)
    def test_native_splash_stays_responsive_without_pixelcopy_gate(self):
        p=(TOOLS/"patch_android20_native_keyboard_splash.py").read_text()
        self.assertIn('vcSplashDeadline = android.os.SystemClock.uptimeMillis() + 1200L;',p)
        self.assertIn('progress.setIndeterminate(true);',p)
        self.assertIn('showStartupCover();',p)
        self.assertIn('startupStage("native_editor_ui_ready");',p)
        self.assertIn('dismissStartupCover();',p)
        self.assertIn('unused=s[begin:end]',p)
    def test_protected_separate_arm64_package(self):
        w=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn('VERSION_NAME: 0.21.0-android.23',w)
        self.assertIn("VERSION_CODE: '16783383'",w)
        self.assertIn('patch_android20_native_keyboard_splash.py',w)
        self.assertIn('com.artcraft.vectorcraft.test',w)
        self.assertIn('builder/build.sh -vectorcraft --noupdate',w)
        self.assertIn('Delete disposable builder signing materials',w)
        self.assertNotIn('gh release create',w)
if __name__=="__main__":
    unittest.main()
