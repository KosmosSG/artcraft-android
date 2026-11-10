"""FilmCraft v0.19 Android Program-monitor pinch and two-finger pan guards.

Source is patched only in the disposable FilmCraft builder. Verify that the
desktop monitor and Android Source/Timeline are unchanged and no clip transform
is triggered by a two-finger Program gesture.
"""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch_v019_android_program_gestures as program


class ProgramMonitorGestureTests(unittest.TestCase):
    def test_injected_gesture_is_scoped_to_android_program(self):
        program.self_test()
        overlay = program.GESTURE_IMPL
        self.assertIn('#[cfg(target_os = "android")]', overlay)
        self.assertIn('w == Which::Program', program.ZOOM_ANDROID_CALL)
        self.assertIn('view_mut(app, Which::Program)', overlay)
        self.assertNotIn('view_mut(app, Which::Source)', overlay)
        self.assertIn('ctx.multi_touch()', overlay)
        self.assertIn('touch.num_touches >= 2', overlay)
        self.assertIn('area.contains(touch.start_pos)', overlay)
        self.assertIn('area.contains(touch.center_pos)', overlay)
        self.assertIn('any_touch.is_some() && touch.is_none()', overlay)
        self.assertIn('ctx.pointer_hover_pos()', overlay)

    def test_touch_pinch_and_trackpad_pinch_use_egui(self):
        overlay = program.GESTURE_IMPL
        self.assertIn('g.zoom_delta', overlay)
        self.assertIn('ctx.input(|i| i.zoom_delta())', overlay)
        self.assertIn('factor.clamp(0.5, 2.0)', overlay)
        self.assertIn('ZOOMS[0].1', overlay)
        self.assertIn('ZOOMS[ZOOMS.len() - 1].1', overlay)
        self.assertIn('anchor - (anchor - pic.center()) * k', overlay)
        self.assertIn('view.zoom = Some(z)', overlay)
        self.assertIn('ctx.request_repaint()', overlay)

    def test_swipe_pan_is_two_axis_and_isolated_to_preview(self):
        overlay = program.GESTURE_IMPL
        self.assertIn('g.translation_delta', overlay)
        self.assertIn('wheel.delta', overlay)
        self.assertIn('view(app, Which::Program).zoom.is_some()', overlay)
        self.assertIn('(view.pan[0] + delta.x)', overlay)
        self.assertIn('(view.pan[1] + delta.y)', overlay)
        self.assertIn('delta.x.clamp(-180.0, 180.0)', overlay)
        self.assertIn('delta.y.clamp(-180.0, 180.0)', overlay)
        self.assertIn('return touch.is_some()', overlay)
        self.assertNotIn('Tool::Select', overlay)
        self.assertNotIn('app.session.execute(', overlay)
        self.assertNotIn('timeline::zoom_about', overlay)

    def test_no_accidental_clip_transform_with_two_fingers(self):
        guard = program.MONITOR_TOUCH_GUARD
        self.assertIn('num_touches >= 2', guard)
        self.assertIn('video_area.contains(touch.start_pos)', guard)
        src = (
            program.MONITOR_TOUCH_GUARD_ANCHOR
            + '    if which == Which::Program && show_picture && '
            + 'ui.interact(video_area, egui::Id::unique((prefix, "background")), '
            + 'Sense::click()).clicked() {\n'
            + '    if which == Which::Program && show_picture {\n'
            + '        // an armed eyedropper owns clicks on the picture:'
        )
        changed = program.patch_monitor(src)
        self.assertIn('&& !android_program_multitouch && ui.interact(', changed)
        self.assertIn('if which == Which::Program && show_picture && !android_program_multitouch {', changed)
        self.assertIn('cfg!(target_os = "android")', changed)

    def test_main_builder_stages_only_scoped_program_patch(self):
        wf = (HERE.parent.parent / ".github" / "workflows" /
              "filmcraft-v019-disposable-test.yml").read_text()
        self.assertIn('patch_v019_android_program_gestures.py', wf)
        self.assertIn('filmcraft-builder/source/filmcraft', wf)
        self.assertIn('com.artcraft.filmcraft.test', wf)
        self.assertIn('TEMP SIGNING', wf)


if __name__ == "__main__":
    unittest.main()
