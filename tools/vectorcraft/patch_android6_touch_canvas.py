"""VectorCraft Android.6: natural vertical touchscreen canvas scroll + early two-touch pan.

Stacked on successfully device-tested Android.5. Change ONLY upstream canvas
input's touchscreen branch, not the native Android trackpad router, egui
popup scrolling, keyboard, font library, Ctrl+Q, or published release.
Fail closed when generated source anchors drift.
"""
from pathlib import Path


def once(src: str, anchor: str, replacement: str, what: str) -> str:
    n = src.count(anchor)
    if n != 1:
        raise ValueError(f"Android.6 {what}: expected 1 source anchor, got {n}")
    return src.replace(anchor, replacement, 1)


HELPER = r'''
// Android touchscreen has two distinct sources of gesture navigation:
// egui multi_touch() (preferred after gesture establishment), and raw Touch
// positions (needed for the first motion packet on some MagicOS panels).
// Keep the lightweight fallback per canvas UI, never globally or in menus.
#[cfg(target_os = "android")]
#[derive(Clone, Default)]
struct Android6EarlyTouchPan {
    down: Vec<(egui::TouchId, egui::Pos2)>,
    previous_center: Option<egui::Pos2>,
    began_on_canvas: bool,
}

#[cfg(target_os = "android")]
fn android6_early_touch_pan(
    ui: &Ui, rect: egui::Rect, allowed: bool
) -> (egui::Vec2, bool) {
    let (touches, has_native_multi_touch) = ui.input(|input| {
        (
            input.events.iter().filter_map(|event| match event {
                egui::Event::Touch { id, phase, pos, .. } => Some((*id, *phase, *pos)),
                _ => None,
            }).collect::<Vec<_>>(),
            input.multi_touch().is_some(),
        )
    });
    let id = egui::Id::unique("android6-early-touch-canvas");
    let mut state = ui.data(|data| {
        data.get_temp::<Android6EarlyTouchPan>(id).unwrap_or_default()
    });
    let mut translated = egui::Vec2::ZERO;
    for (touch_id, phase, pos) in touches {
        match phase {
            egui::TouchPhase::Start => {
                if state.down.is_empty() {
                    state.began_on_canvas = allowed && rect.contains(pos);
                } else if !rect.contains(pos) {
                    state.began_on_canvas = false;
                }
                if !state.down.iter().any(|(id, _)| *id == touch_id) {
                    state.down.push((touch_id, pos));
                }
                state.previous_center = if state.down.len() == 2 {
                    Some(egui::pos2(
                        (state.down[0].1.x + state.down[1].1.x) * 0.5,
                        (state.down[0].1.y + state.down[1].1.y) * 0.5,
                    ))
                } else { None };
            }
            egui::TouchPhase::Move => {
                if let Some((_, previous)) = state.down.iter_mut().find(|(id, _)| *id == touch_id) {
                    *previous = pos;
                    if state.down.len() == 2 {
                        let center = egui::pos2(
                            (state.down[0].1.x + state.down[1].1.x) * 0.5,
                            (state.down[0].1.y + state.down[1].1.y) * 0.5,
                        );
                        if state.began_on_canvas && allowed && rect.contains(center) {
                            if let Some(before) = state.previous_center {
                                translated += center - before;
                            }
                        }
                        state.previous_center = Some(center);
                    }
                }
            }
            egui::TouchPhase::End | egui::TouchPhase::Cancel => {
                state.down.retain(|(id, _)| *id != touch_id);
                // No stale translation after either finger lifts.
                state.previous_center = None;
                if state.down.is_empty() { state.began_on_canvas = false; }
            }
        }
    }
    let active = allowed && state.began_on_canvas && state.down.len() == 2
        && state.previous_center.is_some();
    ui.data_mut(|data| data.insert_temp(id, state));
    // When egui has native multi_touch, its translation_delta already feeds
    // wheel(). Never double-apply the raw fallback. Avoid any gesture slop
    // threshold: the first non-zero two-contact movement may pan immediately.
    (if active && !has_native_multi_touch { translated } else { egui::Vec2::ZERO },
     active)
}

'''

def patch(root: Path) -> None:
    canvas = root / "source/vectorcraft/crates/ui-egui/src/canvas/input.rs"
    s = canvas.read_text()
    s = once(s,
        """fn wheel_view(
    app: &mut VectorcraftApp,""",
        HELPER + """fn wheel_view(
    app: &mut VectorcraftApp,""",
        "early touch helper")
    s = once(s,
        """    let (pointer, m, space, (factor, scroll)) = ui.input(|i| {""",
        """    let (pointer, m, space, (factor, mut scroll)) = ui.input(|i| {""",
        "writable scroll result")
    s = once(s,
        """    if turn != turn_before {
        ui.data_mut(|d| d.insert_temp(turn_id, turn));
    }""",
        """    // Reverse Y only for *touchscreen* two-finger canvas navigation:
    // swipe UP advances the document DOWN, swipe DOWN moves the view UP.
    // The egui wheel() function already includes the multi_touch pan, so
    // subtract twice that Y to invert it without duplicating X or pinch.
    // When egui is late exposing multi_touch, follow raw two-touch motion
    // immediately with no arbitrary distance or time threshold.
    #[cfg(target_os = "android")]
    let (early_pan, early_two_touch_on_canvas) = android6_early_touch_pan(
        ui, rect, app.session.active().is_some()
            && app.ui.dialog.is_none() && !app.ui.palette_open
            && !egui::Popup::is_any_open(ui.ctx()),
    );
    #[cfg(not(target_os = "android"))]
    let early_two_touch_on_canvas = false;
    #[cfg(target_os = "android")]
    if let Some(native_pan) = ui.input(|i| i.multi_touch().map(|t| t.translation_delta)) {
        scroll.y -= 2.0 * native_pan.y;
    } else {
        scroll.x += early_pan.x;
        scroll.y -= early_pan.y;
    }
    if turn != turn_before {
        ui.data_mut(|d| d.insert_temp(turn_id, turn));
    }""",
        "reverse natural touch pan, early fallback")
    s = once(s,
        """    let gesture_on_canvas = touch_center.is_some();
    // MagicOS may deliver native trackpad Event::Zoom""",
        """    let gesture_on_canvas = touch_center.is_some() || early_two_touch_on_canvas;
    // MagicOS may deliver native trackpad Event::Zoom""",
        "authorize early two-finger scrolling")
    s = once(s,
        """    let trackpad_pinch_needs_anchor = pointer.hover_pos().is_none()
        && !egui::Popup::is_any_open(ui.ctx())""",
        """    let trackpad_pinch_needs_anchor = pointer.hover_pos().is_none()
        && !early_two_touch_on_canvas
        && !egui::Popup::is_any_open(ui.ctx())""",
        "preserve hoverless native trackpad pinch independently")
    for required in (
        "android6_early_touch_pan", "scroll.y -= 2.0 * native_pan.y",
        "scroll.y -= early_pan.y", "trackpad_pinch_needs_anchor",
        "touch_center.is_some() || early_two_touch_on_canvas",
        "if (resp.hovered() || gesture_on_canvas) && scroll != egui::Vec2::ZERO",
    ):
        if required not in s:
            raise ValueError(f"Android.6 missing generated canvas assertion: {required}")
    canvas.write_text(s)
    print("PASS: Android.6 natural Y touchscreen pan, immediate raw two-touch fallback, unchanged trackpad pinch/menu")

if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
