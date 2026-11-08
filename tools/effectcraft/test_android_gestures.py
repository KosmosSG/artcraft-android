"""EffectCraft-only fail-closed two-finger navigation overlay tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from patch_android_gestures import apply, APP_ANCHOR, VIEW_ANCHOR, PANELS_ANCHOR, MARKER

class TouchNavigationTests(unittest.TestCase):
    def fixture(self, root: Path):
        a = root / "crates/ui-egui/src/app.rs"
        b = root / "crates/ui-egui/src/app/input.rs"
        c = root / "crates/ui-egui/src/panels/viewer.rs"
        d = root / "crates/ui-egui/src/panels.rs"
        for path in (a, b, c, d):
            path.parent.mkdir(parents=True, exist_ok=True)
        a.write_text("test\\n" + APP_ANCHOR + "\\n")
        b.write_text("pub fn feed_synthetic(&self) {}")
        c.write_text(
            "viewer\\n" + VIEW_ANCHOR + "\\n"
            + "        let scroll = super::viewer_scroll(&ctx);\\n"
            + "        } else if scroll.pan != egui::Vec2::ZERO && area.contains(hp) {\\n"
            + "            app.ui.viewer.pan = [app.ui.viewer.pan[0] + scroll.pan.x, app.ui.viewer.pan[1] + scroll.pan.y];\\n"
        )
        d.write_text(PANELS_ANCHOR)
        return a, b, c

    def test_view_only_touch_and_no_selection(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            a, b, c = self.fixture(root)
            apply(root)
            content = b.read_text()
            self.assertIn(MARKER, content)
            self.assertIn("state.contacts.len() == 2", content)
            self.assertIn("egui::Event::PointerGone", content)
            self.assertIn('effectcraft.android.touch.pan', content)
            self.assertIn('direct_pan += delta', content)
            self.assertNotIn('raw.events.push(egui::Event::MouseWheel', content)
            self.assertIn('egui::Event::PointerGone', content)
            self.assertIn('ctx.data_mut(|d| d.insert_temp(pan_key, direct_pan))', content)
            viewer = c.read_text()
            self.assertIn('if ec_touch_pan != egui::Vec2::ZERO', viewer)
            self.assertIn('app.ui.viewer.pan[0] + ec_touch_pan.x', viewer)
            self.assertNotIn('scroll.pan + ec_touch_pan', viewer)
            self.assertIn("egui::Event::Zoom(scale)", content)
            self.assertIn("self.android_route_touch_navigation(ctx, raw_input)", a.read_text())
            self.assertIn("effectcraft.android.viewer.area", c.read_text())
            self.assertIn("egui::MouseWheelUnit::Point", (root / "crates/ui-egui/src/panels.rs").read_text())
            with self.assertRaisesRegex(RuntimeError, "already applied"):
                apply(root)

    def test_upstream_drift_refuses_without_writing(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            a, b, c = self.fixture(root)
            c.write_text("upstream changed")
            original = a.read_text()
            with self.assertRaisesRegex(RuntimeError, "drift"):
                apply(root)
            self.assertEqual(a.read_text(), original)
