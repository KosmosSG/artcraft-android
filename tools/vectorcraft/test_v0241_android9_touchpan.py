"""Source-only guard for VectorCraft v0.24.1-android.9 touchscreen pan direction.

No Android.10 IME transport is installed or required. The published Android.9
tag and production package remain untouched. Device testing still required.
"""
from pathlib import Path
import sys

def check_patch(root: Path) -> None:
    code = (root / 'tools/vectorcraft/patch_android8_wheel_touch.py').read_text()
    assert code.count('if early_two_touch_on_canvas || native_canvas_touch.is_some() {') == 1
    assert code.count('scroll = if early_pan != egui::Vec2::ZERO {') == 1
    assert code.count('                -early_pan\n') == 1
    assert code.count('                -native_canvas_touch.map_or(egui::Vec2::ZERO, |t| t.translation_delta)') == 1
    assert 'rect.contains(t.center_pos)' in code
    assert 'scroll = -scroll' not in code
    assert 'MouseWheel' not in code.split('scroll = if early_pan != egui::Vec2::ZERO {', 1)[1].split('};', 1)[0]
    print('PASS: Android.9 patch reverses X/Y only inside guarded two-contact canvas pan')

def check_staged(root: Path) -> None:
    canvas = (root / 'source/vectorcraft/crates/ui-egui/src/canvas/input.rs').read_text()
    assert canvas.count('let native_canvas_touch = ui.input(|i| i.multi_touch())') == 1
    assert canvas.count('if early_two_touch_on_canvas || native_canvas_touch.is_some() {') == 1
    assert canvas.count('scroll = if early_pan != egui::Vec2::ZERO {') == 1
    assert canvas.count('                -early_pan\n') == 1
    assert canvas.count('                -native_canvas_touch.map_or(egui::Vec2::ZERO, |t| t.translation_delta)') == 1
    assert 'rect.contains(t.center_pos)' in canvas
    assert 'scroll = -scroll' not in canvas
    assert 'scroll.y -= 2.0 * native_pan.y;' not in canvas
    # These are generated canvas-specific checks, never trackpad or IME changes.
    print('PASS: generated Android.9 canvas has reversed two-finger X/Y, one source per frame')

if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('--source', '--staged'):
        raise SystemExit('usage: test_v0241_android9_touchpan.py --source|--staged ROOT')
    (check_patch if sys.argv[1] == '--source' else check_staged)(Path(sys.argv[2]))
