#!/usr/bin/env python3
"""Selective Android Program-monitor two-finger pinch and pan for FilmCraft v0.19.

Applies only to the disposable upstream checkout; rejects source anchor drift.
Desktop Source/Program monitor behavior and Android Source/Timeline are unchanged.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MONITOR_ZOOM_ANCHOR = (
    "pub fn zoom_pan_input(app: &mut FilmcraftApp, ui: &mut egui::Ui, "
    "w: Which, area: Rect, pic: Rect, fw: f32, ppp: f32) {\n"
    "    let ctx = ui.ctx().clone();\n"
)
ZOOM_ANDROID_CALL = """pub fn zoom_pan_input(app: &mut FilmcraftApp, ui: &mut egui::Ui, w: Which, area: Rect, pic: Rect, fw: f32, ppp: f32) {
    let ctx = ui.ctx().clone();
    #[cfg(target_os = "android")]
    if w == Which::Program
        && android_program_monitor_gesture(app, ui, area, pic, fw, ppp)
    {
        return;
    }
"""

GESTURE_IMPL = r'''/// On Android, a two-finger trackpad scroll pans the Program preview, not
/// the timeline or the clip transform. Touch gestures use egui's native
/// multi_touch zoom + translation; trackpad zoom uses Event::Zoom/ctrl-wheel.
/// Return true when the gesture belongs to the Program monitor, suppressing
/// the desktop fallback that interprets plain wheel scrolling as zoom.
#[cfg(target_os = "android")]
fn android_program_monitor_gesture(
    app: &mut FilmcraftApp,
    ui: &mut egui::Ui,
    area: Rect,
    pic: Rect,
    fw: f32,
    ppp: f32,
) -> bool {
    let ctx = ui.ctx().clone();
    let touch = ctx.multi_touch().filter(|touch| {
        touch.num_touches >= 2
            && area.contains(touch.start_pos)
            && area.contains(touch.center_pos)
    });
    let pointer = ctx.pointer_hover_pos().filter(|p| area.contains(*p));
    let Some(anchor) = touch.map(|g| g.center_pos).or(pointer) else {
        return false;
    };

    // Only consume wheel/pinch when the cursor is over Program. Never modify
    // Source, timeline, playback, selection or clip scale.
    let wheel = crate::panels::timeline::wheel_input(&ctx);
    // egui's zoom_delta includes trackpad Ctrl+wheel synthesis as well as
    // native Event::Zoom. Direct two-finger touch gets the true gesture ratio.
    let trackpad_factor = ctx.input(|i| i.zoom_delta());
    let factor = touch.map_or(trackpad_factor, |g| g.zoom_delta);
    let zooming = factor.is_finite() && (factor - 1.0).abs() > 1e-4;
    let translation = if let Some(g) = touch {
        g.translation_delta
    } else if zooming {
        // Some trackpads deliver both Zoom and synthetic Wheel in the same
        // frame; the Wheel component is not a second zoom or a scroll.
        Vec2::ZERO
    } else {
        wheel.delta
    };
    let delta = if translation.x.is_finite() && translation.y.is_finite() {
        // Avoid huge jumps from unexpected device-axis spikes.
        vec2(translation.x.clamp(-180.0, 180.0), translation.y.clamp(-180.0, 180.0))
    } else {
        Vec2::ZERO
    };
    let panning = delta.length_sq() > 1e-5;
    if !zooming && !panning {
        return touch.is_some();
    }

    if zooming && pic.width() > 0.0 && fw > 0.0 {
        let current = pic.width() * ppp / fw;
        if current.is_finite() && current > 1e-5 {
            let z = (current * factor.clamp(0.5, 2.0))
                .clamp(ZOOMS[0].1, ZOOMS[ZOOMS.len() - 1].1);
            let k = z / current;
            // Anchor the video pixel under the pinch centre/cursor, while
            // also applying two-finger translation (finger direction = canvas direction).
            let center = anchor - (anchor - pic.center()) * k + delta;
            let max = ((pic.size() * k - area.size()) / 2.0).max(Vec2::ZERO);
            let view = view_mut(app, Which::Program);
            view.zoom = Some(z);
            view.pan = [
                (center.x - area.center().x).clamp(-max.x, max.x),
                (center.y - area.center().y).clamp(-max.y, max.y),
            ];
            ctx.request_repaint();
        }
    } else if panning && view(app, Which::Program).zoom.is_some() {
        // Panning is only meaningful when the preview exceeds its viewport.
        // Trackpad 2-finger swipes now pan instead of changing magnification.
        let max = ((pic.size() - area.size()) / 2.0).max(Vec2::ZERO);
        let view = view_mut(app, Which::Program);
        view.pan = [
            (view.pan[0] + delta.x).clamp(-max.x, max.x),
            (view.pan[1] + delta.y).clamp(-max.y, max.y),
        ];
        ctx.request_repaint();
    }
    true
}

'''
MONITOR_TOUCH_GUARD_ANCHOR = '''    // A click on the Program monitor around the picture lets go of what is selected on it (#683;
'''
MONITOR_TOUCH_GUARD = '''    // A two-finger Program gesture navigates the canvas only. In particular,
    // don't let the primary touch synthesize a clip-selection/transform drag.
    let android_program_multitouch = cfg!(target_os = "android")
        && which == Which::Program
        && ctx.multi_touch().is_some_and(|touch| {
            touch.num_touches >= 2
                && video_area.contains(touch.start_pos)
                && video_area.contains(touch.center_pos)
        });
'''

def require_once(text: str, old: str, new: str, name: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"STOP: {name} changed; expected one upstream v0.19 anchor, got {text.count(old)}")
    return text.replace(old, new, 1)

def patch_monitor_view(source: str) -> str:
    if "android_program_monitor_gesture(" in source:
        raise ValueError("STOP: Program gesture overlay already present")
    source = require_once(source, MONITOR_ZOOM_ANCHOR,
                          ZOOM_ANDROID_CALL, "monitor zoom input")
    return require_once(source, "/// Zoom and pan the picture " ,
                        GESTURE_IMPL + "/// Zoom and pan the picture ",
                        "monitor gesture insertion")

def patch_monitor(source: str) -> str:
    if "android_program_multitouch" in source:
        raise ValueError("STOP: Program touch guard already present")
    source = require_once(source, MONITOR_TOUCH_GUARD_ANCHOR,
                          MONITOR_TOUCH_GUARD + MONITOR_TOUCH_GUARD_ANCHOR,
                          "Program selection guard")
    source = require_once(source,
        'if which == Which::Program && show_picture && ui.interact(video_area, egui::Id::unique((prefix, "background")), Sense::click()).clicked() {',
        'if which == Which::Program && show_picture && !android_program_multitouch && ui.interact(video_area, egui::Id::unique((prefix, "background")), Sense::click()).clicked() {',
        "Program background selection")
    source = require_once(source,
        '    if which == Which::Program && show_picture {\n        // an armed eyedropper owns clicks on the picture:',
        '    if which == Which::Program && show_picture && !android_program_multitouch {\n        // an armed eyedropper owns clicks on the picture:',
        "Program clip/handle interactions")
    return source

def self_test() -> None:
    view = MONITOR_ZOOM_ANCHOR + "    if view(app, w).zoom.is_none() { return; }\n" + \
        "/// Zoom and pan the picture " + "sample"
    monitor = MONITOR_TOUCH_GUARD_ANCHOR + \
        '    if which == Which::Program && show_picture && ui.interact(video_area, egui::Id::unique((prefix, "background")), Sense::click()).clicked() {\n' + \
        '    if which == Which::Program && show_picture {\n        // an armed eyedropper owns clicks on the picture:'
    a = patch_monitor_view(view)
    b = patch_monitor(monitor)
    assert 'ctx.multi_touch()' in a and 'wheel.delta' in a
    assert '&& !android_program_multitouch' in b
    assert 'touch.translation_delta' not in a  # use captured g.translation_delta instead
    assert 'g.translation_delta' in a
    assert 'w == Which::Program' in a
    assert 'area.contains(touch.center_pos)' in a
    assert 'view.zoom = Some(z)' in a
    assert 'view.pan = [' in a
    for f, src in ((patch_monitor_view, a), (patch_monitor, b)):
        try:
            f(src)
        except ValueError:
            pass
        else:
            raise AssertionError("STOP: overlay must refuse double application")
    print("PASS: FilmCraft Program-only Android touch/trackpad zoom and two-axis canvas pan; no selection drag")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.source:
        parser.error("Expected disposable FilmCraft upstream source path")
    root = args.source.resolve()
    if root.name != "filmcraft" or root.parent.name != "source" or \
            root.parent.parent.name != "filmcraft-builder":
        raise SystemExit("STOP: only patch source/filmcraft in disposable filmcraft-builder")
    v = root / "crates/ui-egui/src/panels/monitor_view.rs"
    m = root / "crates/ui-egui/src/panels/monitor.rs"
    if not v.is_file() or not m.is_file():
        raise SystemExit("STOP: official Program monitor sources missing")
    view_text = patch_monitor_view(v.read_text())
    monitor_text = patch_monitor(m.read_text())
    v.write_text(view_text)
    m.write_text(monitor_text)
    print("PASS: Program monitor pinch zoom + two-finger pan isolated to FilmCraft Android")

if __name__ == "__main__":
    main()
