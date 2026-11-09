"""Android.21 — PhotoCraft-parity startup and menu-scroll protection tests.

User confirmed Android.20 keyboard PASS; these tests prohibit touching its
input bridge while improving launch/menus. Separate temporary ARM64 test only.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"
class VectorCraftAndroid21Parity(unittest.TestCase):
    def test_no_custom_launch_overlay_and_no_pixel_gate(self):
        s=(TOOLS/"patch_android21_photocraft_parity.py").read_text()
        for token in (
            'photocraft_direct_native_launch',
            'SplashScreen.installSplashScreen(this);',
            'showStartupCover();',
            'getWindow().getDecorView().postInvalidateOnAnimation()',
            'native_editor_ui_ready',
            'setKeepOnScreenCondition',
        ):
            self.assertIn(token,s)
        self.assertIn('Do NOT gate the platform splash',s)
        self.assertNotIn('finishAndRemoveTask()',s)

    def test_only_removes_secondary_scroll_replay(self):
        s=(TOOLS/"patch_android21_photocraft_parity.py").read_text()
        self.assertIn('self.menu_scroll.apply(ctx, raw);',s)
        self.assertIn('self.inner.raw_input_hook(raw);',s)
        self.assertIn('PhotoCraft parity: let egui',s)
        # This patch must NOT modify Android keyboard/IME/shortcuts at all:
        for forbidden in ('dispatchKeyEvent','physicalShortcutKeys','ImeBridge',
                          'vcSetHardwareShortcutMode','vc_modal_pending_action',
                          'touch_gestures =','select_tool('):
            self.assertNotIn(forbidden,s)

    def test_release_and_feature_protection(self):
        w=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn('VERSION_NAME: 0.21.0-android.21',w)
        self.assertIn("VERSION_CODE: '16783381'",w)
        self.assertIn('patch_android20_native_keyboard_splash.py',w)
        self.assertIn('patch_android21_photocraft_parity.py',w)
        self.assertIn('com.artcraft.vectorcraft.test',w)
        self.assertIn('builder/build.sh -vectorcraft --noupdate',w)
        self.assertIn('Delete disposable builder signing materials',w)
        self.assertIn('vc_after_type_exit_frames',w)
        self.assertIn('com.artcraft.ime.ArtCraftIme.wake();',w)
        self.assertNotIn('gh release create',w)

if __name__=="__main__":
    unittest.main()
