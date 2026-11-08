"""EffectCraft Android.8 menu/pointer routing regression tests (no other apps)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from patch_android_menu_scroll import (
    apply, APP, WIDGETS, HEADER, VIEWER, APP_OLD, WIDGET_START,
    WIDGET_TARGET, WIDGET_SHOW, VIEWER_OLD, HOVER_OLD
)
from menu_corner import REPLACEMENT

class MenuTrackpadRegression(unittest.TestCase):
    def fixture(self, root: Path):
        data = {
            APP: "impl EffectcraftApp {\n" + APP_OLD + "\n}\n",
            WIDGETS: (
                'pub fn menu_scroll(ui: &mut egui::Ui) {\n'
                '    let max_h = 200.0;\n' + WIDGET_START + '\n'
                '    let target = ui.ctx().data_mut(|d| d.remove_temp::<f32>(pending));\n'
                + WIDGET_TARGET + '\n'
                '    if let Some(target) = target { area = area.vertical_scroll_offset(target); }\n'
                + WIDGET_SHOW + '\n'
                '    if let Some(target) = edge_scroll(ui, &out, browsing) { }\n'
                '}\n'
            ),
            HEADER: "fn header() {\n" + REPLACEMENT + "\n}\n",
            VIEWER: ("fn show() {\n" + VIEWER_OLD + "\n}\n"
                     + "fn phase_hover() {\n" + HOVER_OLD + "\n}\n")
        }
        for rel, content in data.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return data

    def test_popup_menu_and_viewer_isolation(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            apply(root)
            menu = (root / WIDGETS).read_text()
            header = (root / HEADER).read_text()
            viewer = (root / VIEWER).read_text()
            app = (root / APP).read_text()
            self.assertIn("android_record_menu_scroll(ui, &out, android_request);", menu)
            self.assertIn("android_route_trackpad_menu_scroll(ctx, raw_input);", app)
            self.assertIn("effectcraft.android.menu.hovered.scroll", menu)
            self.assertIn("if !pointer.is_some_and(|p| rect.contains(p))", menu)
            self.assertIn("let next = (offset - delta_y.clamp(-240.0, 240.0))", menu)
            self.assertIn("return false;", menu)  # Consume only matching point wheels.
            self.assertIn("android_record_menu_scroll(ui, &ec_out, ec_scroll_key);", header)
            self.assertIn("ec_scroll.vertical_scroll_offset(target)", header)
            self.assertIn("if !ec_navigating", viewer)
            self.assertIn('d.remove::<Gesture>(egui::Id::unique("viewer-gesture"))', viewer)
            self.assertIn("effectcraft.android.touch.navigation.center", viewer)
            self.assertIn("phase_tail(app, ui, &ectx, &mut v)", viewer)
            with self.assertRaisesRegex(RuntimeError, "already applied"):
                apply(root)

    def test_upstream_drift_does_not_mutate_sources(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            header = root / HEADER
            header.write_text("upstream header changed")
            app = root / APP
            previous = app.read_text()
            with self.assertRaisesRegex(RuntimeError, "drift"):
                apply(root)
            self.assertEqual(app.read_text(), previous)

if __name__ == "__main__":
    unittest.main()
