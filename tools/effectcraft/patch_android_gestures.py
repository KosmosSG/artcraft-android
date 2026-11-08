#!/usr/bin/env python3
"""Isolated EffectCraft Android touch navigation overlay for pinned v0.21.0.

Two touchscreen contacts inside a real Composition/Layer viewer translate to
viewer-only pan/zoom, not egui-winit's emulated primary-mouse selection.
No code is changed outside the disposable EffectCraft source checkout.
"""
from pathlib import Path

APP = "crates/ui-egui/src/app.rs"
INPUT = "crates/ui-egui/src/app/input.rs"
VIEW = "crates/ui-egui/src/panels/viewer.rs"
PANELS = "crates/ui-egui/src/panels.rs"

APP_ANCHOR = "            self.feed_synthetic(raw_input);"
VIEW_ANCHOR = '    let resp = ui.interact(area, egui::Id::unique("viewer-interact"), Sense::click_and_drag());'
PANELS_ANCHOR = '''    if trackpad != was {
        ctx.data_mut(|d| d.insert_temp(id, trackpad));
    }'''
PANELS_INSERT = '''    // On Android, high-resolution touchpad wheels arrive as Point deltas
    // (winit does not preserve the OS source classification). Keep them as
    // view panning, never accidental mouse-wheel zoom.
    #[cfg(target_os = "android")]
    let trackpad = trackpad || ctx.input(|i| i.events.iter().any(|e| matches!(e,
        egui::Event::MouseWheel { unit: egui::MouseWheelUnit::Point, modifiers, .. }
            if !modifiers.any()
    )));
''' + PANELS_ANCHOR
MARKER = "effectcraft.android.touch.navigation"

TOUCH_SOURCE = r'''
// effectcraft.android.touch.navigation: track two fingers only in the viewer.
#[cfg(target_os = "android")]
#[derive(Clone, Default)]
struct AndroidViewerFingers {
    contacts: Vec<(egui::TouchId, egui::Pos2)>,
    prior: Option<(egui::Pos2, f32)>,
    suppress_until_lift: bool,
}

#[cfg(target_os = "android")]
impl EffectcraftApp {
    pub fn android_route_touch_navigation(
        &mut self, ctx: &egui::Context, raw: &mut egui::RawInput,
    ) {
        let key = egui::Id::new("effectcraft.android.touch.navigation");
        let mut state: AndroidViewerFingers =
            ctx.data(|d| d.get_temp(key)).unwrap_or_default();
        let viewer: Option<egui::Rect> = ctx.data(|d| {
            d.get_temp(egui::Id::new("effectcraft.android.viewer.area"))
        });
        let mut moves: Vec<(egui::Pos2, egui::Vec2, f32)> = Vec::new();
        // Avoid stale deltas when a viewer is hidden or a pass has no moves.
        let pan_key = egui::Id::new("effectcraft.android.touch.pan");
        ctx.data_mut(|d| d.remove::<egui::Vec2>(pan_key));
        let mut suppress = state.suppress_until_lift;
        let mut viewer_center: Option<egui::Pos2> = None;
        for e in raw.events.clone() {
            if let egui::Event::Touch { id, phase, pos, .. } = e {
                match phase {
                    egui::TouchPhase::Start => {
                        if state.contacts.len() < 6
                            && state.contacts.iter().all(|(other, _)| *other != id) {
                            state.contacts.push((id, pos));
                        }
                    }
                    egui::TouchPhase::Move => {
                        if let Some((_, last_pos)) = state.contacts.iter_mut()
                            .find(|(other, _)| *other == id) {
                            *last_pos = pos;
                        }
                    }
                    egui::TouchPhase::End | egui::TouchPhase::Cancel => {
                        state.contacts.retain(|(other, _)| *other != id);
                    }
                }
                if state.contacts.len() == 2 {
                    let a = state.contacts[0].1;
                    let b = state.contacts[1].1;
                    if viewer.is_some_and(|area| area.contains(a) && area.contains(b)) {
                        suppress = true;
                        state.suppress_until_lift = true;
                        let center = a + (b - a) * 0.5;
                        viewer_center = Some(center);
                        let distance = (b - a).length();
                        if let Some((old_center, old_dist)) = state.prior {
                            let delta = center - old_center;
                            let scale = if distance > 10.0 && old_dist > 10.0 {
                                // Bound noisy MagicOS contact-distance updates,
                                // while still responding to intentional pinch.
                                (1.0 + (distance / old_dist - 1.0) * 0.7).clamp(0.94, 1.06)
                            } else { 1.0 };
                            if delta.length_sq() > 0.01 || (scale - 1.0).abs() > 0.002 {
                                moves.push((center, delta, scale));
                            }
                        }
                        state.prior = Some((center, distance));
                    }
                } else {
                    state.prior = None;
                }
                if state.contacts.is_empty() {
                    state.suppress_until_lift = false;
                }
            }
        }
        let mut direct_pan = egui::Vec2::ZERO;
        if suppress {
            // Cancel first-finger mouse emulation while navigating with two
            // fingers; this must not select/move layers or draw with a tool.
            raw.events.retain(|e| !matches!(
                e,
                egui::Event::Touch { .. }
                    | egui::Event::PointerMoved(_)
                    | egui::Event::PointerButton { .. }
                    | egui::Event::PointerGone
            ));
            raw.events.push(egui::Event::PointerGone);
            for (center, delta, scale) in moves {
                raw.events.push(egui::Event::PointerMoved(center));
                // The viewer's smooth_scroll_delta is not reliable for
                // touchscreen contacts: menu/panel scroll containers can own
                // or consume it first. Queue a VIEW-only pan instead, just
                // as PhotoCraft queues its editor view transforms.
                if delta.length_sq() > 0.01 {
                    direct_pan += delta;
                }
                if (scale - 1.0).abs() > 0.002 {
                    raw.events.push(egui::Event::Zoom(scale));
                }
            }
        }
        if suppress && direct_pan.length_sq() > 0.01 {
            ctx.data_mut(|d| d.insert_temp(pan_key, direct_pan));
        }
        ctx.data_mut(|d| {
            let active = egui::Id::new("effectcraft.android.touch.navigation.active");
            let center_key = egui::Id::new("effectcraft.android.touch.navigation.center");
            d.insert_temp(active, suppress);
            if let Some(center) = viewer_center {
                d.insert_temp(center_key, center);
            } else {
                d.remove::<egui::Pos2>(center_key);
            }
            d.insert_temp(key, state);
        });
    }
}
'''

def apply(root: Path) -> None:
    paths = [root / APP, root / INPUT, root / VIEW, root / PANELS]
    data = [p.read_text(encoding="utf-8") for p in paths]
    if MARKER in "".join(data):
        raise RuntimeError("STOP: EffectCraft gesture patch already applied")
    if (data[0].count(APP_ANCHOR) != 1 or data[2].count(VIEW_ANCHOR) != 1
            or data[3].count(PANELS_ANCHOR) != 1):
        raise RuntimeError("STOP: upstream EffectCraft viewer/raw_input_hook drift")
    if (data[2].count('        let scroll = super::viewer_scroll(&ctx);') != 1
            or data[2].count('} else if scroll.pan != egui::Vec2::ZERO && area.contains(hp) {') != 1
            or data[2].count('app.ui.viewer.pan = [app.ui.viewer.pan[0] + scroll.pan.x, app.ui.viewer.pan[1] + scroll.pan.y];') != 1):
        raise RuntimeError("STOP: viewer pan hooks changed")
    if "pub fn feed_synthetic" not in data[1]:
        raise RuntimeError("STOP: upstream EffectCraft input extension changed")
    data[0] = data[0].replace(
        APP_ANCHOR,
        '            #[cfg(target_os = "android")]\n'
        '            self.android_route_touch_navigation(ctx, raw_input);\n'
        + APP_ANCHOR, 1)
    data[1] += "\n" + TOUCH_SOURCE + "\n"
    data[2] = data[2].replace(
        VIEW_ANCHOR,
        '    #[cfg(target_os = "android")]\n'
        '    ui.ctx().data_mut(|d| d.insert_temp(\n'
        '        egui::Id::new("effectcraft.android.viewer.area"), area,\n'
        '    ));\n' + VIEW_ANCHOR, 1)
    data[2] = data[2].replace(
        '        let scroll = super::viewer_scroll(&ctx);',
        '''        let scroll = super::viewer_scroll(&ctx);
        // Android two-touchscreen-finger panning bypasses egui's general
        // scroll routing. Never alter editor layers or ordinary stylus input.
        #[cfg(target_os = "android")]
        let ec_touch_pan: egui::Vec2 = ctx.data(|d|
            d.get_temp(egui::Id::new("effectcraft.android.touch.pan"))
        ).unwrap_or(egui::Vec2::ZERO);
        #[cfg(not(target_os = "android"))]
        let ec_touch_pan = egui::Vec2::ZERO;''', 1)
    data[2] = data[2].replace(
        '} else if scroll.pan != egui::Vec2::ZERO && area.contains(hp) {',
        '} else if (scroll.pan + ec_touch_pan) != egui::Vec2::ZERO && area.contains(hp) {', 1)
    data[2] = data[2].replace(
        'app.ui.viewer.pan = [app.ui.viewer.pan[0] + scroll.pan.x, app.ui.viewer.pan[1] + scroll.pan.y];',
        'app.ui.viewer.pan = [app.ui.viewer.pan[0] + scroll.pan.x + ec_touch_pan.x, app.ui.viewer.pan[1] + scroll.pan.y + ec_touch_pan.y];', 1)
    data[3] = data[3].replace(PANELS_ANCHOR, PANELS_INSERT, 1)
    for path, source in zip(paths, data):
        path.write_text(source, encoding="utf-8")
    print("PASS: EffectCraft Android view-only dual-touch navigation staged")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_android_gestures.py <upstream-source-root>")
    apply(Path(sys.argv[1]))
