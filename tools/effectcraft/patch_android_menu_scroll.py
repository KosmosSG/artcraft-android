#!/usr/bin/env python3
"""EffectCraft-only Android.8 routing for native trackpad scrolling in actual popups.

Run after menu_corner.py and patch_android_gestures.py in the disposable
EffectCraft source checkout. Do not edit PhotoCraft, shared vendor or keys.
All anchors are checked BEFORE any source is written.
"""
from pathlib import Path

APP = "crates/ui-egui/src/app.rs"
WIDGETS = "crates/ui-egui/src/widgets.rs"
HEADER = "crates/ui-egui/src/header.rs"
VIEWER = "crates/ui-egui/src/panels/viewer.rs"

APP_OLD = "            self.android_route_touch_navigation(ctx, raw_input);"
APP_NEW = APP_OLD + '\n            #[cfg(target_os = "android")]\n            crate::widgets::android_route_trackpad_menu_scroll(ctx, raw_input);'
WIDGET_START = "    let pending = ui.scope_id().with(\"menu-edge-scroll-offset\");"
WIDGET_TARGET = "    let mut area = egui::ScrollArea::vertical().max_height(max_h).min_scrolled_height(max_h);"
WIDGET_SHOW = "    let out = area.show(ui, add);"
HEADER_START = '''                egui::ScrollArea::vertical()
                    .id_salt("effectcraft.android.ec_menu_scroll")
                    .max_height(236.0)
                    .auto_shrink([true, true])
                    .show(ui, |ui| {'''
HEADER_END = '''                        if ui.button("About EffectCraft").clicked() {
                            app.dialog = Some(Dialog::About);
                            ui.close();
                        }
                    });'''
HOVER_OLD = "    let hover_pos = resp.hover_pos().or_else(|| if resp.contains_pointer() { ui.input(|i| i.pointer.hover_pos()) } else { None });"
HOVER_NEW = '''    // Android two-touch navigation must use the REAL finger centroid first,
    // not a stale hover position left by MagicOS's synthetic mouse pointer.
    #[cfg(target_os = "android")]
    let ec_touch_center: Option<egui::Pos2> = {
        let navigating: bool = ctx.data(|d| d.get_temp(
            egui::Id::new("effectcraft.android.touch.navigation.active")
        )).unwrap_or(false);
        if navigating {
            ctx.data(|d| d.get_temp(egui::Id::new(
                "effectcraft.android.touch.navigation.center"
            )))
        } else { None }
    };
    #[cfg(not(target_os = "android"))]
    let ec_touch_center: Option<egui::Pos2> = None;
    let hover_pos = ec_touch_center
        .or_else(|| resp.hover_pos())
        .or_else(|| if resp.contains_pointer() {
            ui.input(|i| i.pointer.hover_pos())
        } else { None });'''
VIEWER_OLD = '''    phase_hover(app, ui, &ectx, &resp, &mut v);
    phase_press(app, ui, &ectx, &resp, &mut v);
    phase_dragstart(app, ui, &ectx, &resp, &mut v);
    phase_drag(app, ui, &ectx, &resp, &mut v);
    phase_stopped(app, ui, &ectx, &resp, &mut v);
    phase_clicked(app, &ectx, &resp, &mut v);
    phase_dblclick(app, &ectx, &resp, &mut v);
    phase_tail(app, ui, &ectx, &mut v);'''
VIEWER_NEW = '''    phase_hover(app, ui, &ectx, &resp, &mut v);
    // Two touchscreen contacts are for NAVIGATION, not editor operations.
    // RawInput pointer filtering alone is not sufficient on MagicOS:
    // egui can retain a press/drag from the first finger between passes.
    #[cfg(target_os = "android")]
    let ec_navigating: bool = ctx.data(|d| d.get_temp::<bool>(
        egui::Id::new("effectcraft.android.touch.navigation.active")
    )).unwrap_or(false) || {
        // The canvas must not run press/drag/selection phases during active
        // two-finger trackpad or touchscreen wheel navigation.
        let scroll_until = ctx.data(|d| d.get_temp::<f64>(
            egui::Id::new("effectcraft.android14.canvas.scroll_until")
        )).unwrap_or(-1.0);
        scroll_until >= ctx.input(|i| i.time)
    };
    #[cfg(not(target_os = "android"))]
    let ec_navigating = false;
    if ec_navigating {
        // Stop any first-finger drag already started before finger two arrived.
        ui.data_mut(|d| d.remove::<Gesture>(egui::Id::unique("viewer-gesture")));
    }
    if !ec_navigating {
        phase_press(app, ui, &ectx, &resp, &mut v);
        phase_dragstart(app, ui, &ectx, &resp, &mut v);
        phase_drag(app, ui, &ectx, &resp, &mut v);
        phase_stopped(app, ui, &ectx, &resp, &mut v);
        phase_clicked(app, &ectx, &resp, &mut v);
        phase_dblclick(app, &ectx, &resp, &mut v);
    }
    phase_tail(app, ui, &ectx, &mut v);'''


# v0.23.1 added middle-button panning around drag phases. Preserve this
# upstream behavior while suppressing touchpad/two-finger editor selection.
VIEWER_OLD_023 = '''    phase_hover(app, ui, &ectx, &resp, &mut v);
    phase_press(app, ui, &ectx, &resp, &mut v);
    if !middle_pan(app, ui, &resp, &v) {
        phase_dragstart(app, ui, &ectx, &resp, &mut v);
        phase_drag(app, ui, &ectx, &resp, &mut v);
        phase_stopped(app, ui, &ectx, &resp, &mut v);
        phase_clicked(app, &ectx, &resp, &mut v);
        phase_dblclick(app, &ectx, &resp, &mut v);
    }
    phase_tail(app, ui, &ectx, &mut v);'''
VIEWER_NEW_023 = VIEWER_NEW.replace(
    '''    if !ec_navigating {
        phase_press(app, ui, &ectx, &resp, &mut v);
        phase_dragstart(app, ui, &ectx, &resp, &mut v);''',
    '''    if !ec_navigating {
        phase_press(app, ui, &ectx, &resp, &mut v);
    }
    if !ec_navigating && !middle_pan(app, ui, &resp, &v) {
        phase_dragstart(app, ui, &ectx, &resp, &mut v);'''
)

WIDGET_HELPERS = r'''
// EffectCraft Android.8: remember the actual hovered ScrollArea (including submenus)
// from the completed egui pass. Input arrives BEFORE the next layout, like in PhotoCraft.
#[cfg(target_os = "android")]
pub(crate) fn android_record_menu_scroll<R>(
    ui: &egui::Ui,
    out: &egui::containers::scroll_area::ScrollAreaOutput<R>,
    request: egui::Id,
) {
    let max = (out.content_size.y - out.inner_rect.height()).max(0.0);
    if max <= 0.5 { return; }
    if !ui.input(|i| i.pointer.latest_pos().is_some_and(|p| out.inner_rect.contains(p))) {
        return;
    }
    let ctx = ui.ctx();
    let pass = ctx.cumulative_pass_nr();
    let offset = out.state.clamped_offset().y;
    ctx.data_mut(|d| d.insert_temp(
        egui::Id::new("effectcraft.android.menu.hovered.scroll"),
        (pass, request, offset, max, out.inner_rect),
    ));
}

/// Dispatch physical touchpad scrolling to the menu beneath the pointer, not the
/// composition viewer behind it. Consume ONLY unmodified trackpad/point wheels.
/// Mouse wheel lines, keyboard, taps and stylus keep their native behavior.
#[cfg(target_os = "android")]
pub(crate) fn android_route_trackpad_menu_scroll(
    ctx: &egui::Context,
    raw: &mut egui::RawInput,
) {
    // Android.14: a trackpad/two-finger scroll must never be interpreted
    // as a selection-rectangle gesture on the composition viewer.
    // Remember a brief scroll-active interval in the current input pass.
    // This runs even when NO popup is open, before the early menu return.
    let ec14_now = ctx.input(|i| i.time);
    if raw.events.iter().any(|event| matches!(event,
        egui::Event::MouseWheel {
            unit: egui::MouseWheelUnit::Point,
            modifiers, ..
        } if !modifiers.any()
    )) {
        ctx.data_mut(|d| d.insert_temp(
            egui::Id::new("effectcraft.android14.canvas.scroll_until"),
            ec14_now + 0.18_f64,
        ));
    }
    let target: Option<(u64, egui::Id, f32, f32, egui::Rect)> =
        ctx.data(|d| d.get_temp(egui::Id::new("effectcraft.android.menu.hovered.scroll")));
    let Some((seen, request, offset, max, rect)) = target else { return };
    if seen.saturating_add(1) < ctx.cumulative_pass_nr() { return; }
    let pointer = raw.events.iter().rev().find_map(|e| match e {
        egui::Event::PointerMoved(p) => Some(*p),
        egui::Event::PointerButton { pos, .. } => Some(*pos),
        _ => None,
    }).or_else(|| ctx.pointer_hover_pos());
    if !pointer.is_some_and(|p| rect.contains(p)) { return; }
    let mut delta_y = 0.0_f32;
    raw.events.retain(|event| {
        if let egui::Event::MouseWheel { unit, source, delta, modifiers, .. } = event {
            let pad = *unit == egui::MouseWheelUnit::Point ||
                matches!(source, egui::MouseWheelSource::Trackpad |
                    egui::MouseWheelSource::Momentum);
            if pad && !modifiers.any() && delta.y.is_finite() && delta.x.is_finite() {
                let multiplier = match unit {
                    egui::MouseWheelUnit::Point => 1.0,
                    egui::MouseWheelUnit::Line => 42.0,
                    egui::MouseWheelUnit::Page => rect.height(),
                };
                delta_y += delta.y * multiplier;
                return false;
            }
        }
        true
    });
    if delta_y.is_finite() && delta_y.abs() > 0.001 {
        // Clamp a malformed driver burst, not small precision motions.
        let next = (offset - delta_y.clamp(-240.0, 240.0)).clamp(0.0, max);
        ctx.data_mut(|d| d.insert_temp(request, next));
        ctx.request_repaint();
    }
}
'''

def exactly(source: str, anchor: str, name: str):
    n = source.count(anchor)
    if n != 1:
        raise RuntimeError(f"STOP: EffectCraft Android.8 upstream drift ({name} occurs {n} times)")

def apply(root: Path):
    files = {key: root / key for key in (APP, WIDGETS, HEADER, VIEWER)}
    data = {key: path.read_text(encoding="utf-8") for key, path in files.items()}
    if ("android_route_trackpad_menu_scroll" in data[WIDGETS] or
        'effectcraft.android.touch.navigation.active' in data[VIEWER]):
        raise RuntimeError("STOP: Android.8 menu patch already applied")
    viewer_old = VIEWER_OLD_023 if data[VIEWER].count(VIEWER_OLD_023) == 1 else VIEWER_OLD
    viewer_new = VIEWER_NEW_023 if viewer_old == VIEWER_OLD_023 else VIEWER_NEW
    for key, anchor, title in (
        (APP, APP_OLD, "raw input before egui"),
        (WIDGETS, WIDGET_START, "scroll source id"),
        (WIDGETS, WIDGET_TARGET, "scroll area builder"),
        (WIDGETS, WIDGET_SHOW, "scroll area show"),
        (HEADER, HEADER_START, "Ec popup scroll area"),
        (HEADER, HEADER_END, "Ec popup closing"),
        (VIEWER, viewer_old, "viewer editing phases"),
        (VIEWER, HOVER_OLD, "viewer lost-hover fallback"),
    ):
        exactly(data[key], anchor, title)

    data[APP] = data[APP].replace(APP_OLD, APP_NEW, 1)
    data[WIDGETS] = data[WIDGETS].replace(
        WIDGET_START,
        WIDGET_START + '''
    #[cfg(target_os = "android")]
    let android_request = ui.scope_id().with("effectcraft.android.menu.scroll-request");
    #[cfg(target_os = "android")]
    let android_target = ui.ctx().data_mut(|d| d.remove_temp::<f32>(android_request));''', 1)
    data[WIDGETS] = data[WIDGETS].replace(
        WIDGET_TARGET,
        WIDGET_TARGET + '''
    #[cfg(target_os = "android")]
    if let Some(target) = android_target {
        area = area.vertical_scroll_offset(target);
    }''', 1)
    data[WIDGETS] = data[WIDGETS].replace(
        WIDGET_SHOW,
        WIDGET_SHOW + '''
    #[cfg(target_os = "android")]
    android_record_menu_scroll(ui, &out, android_request);''', 1)
    data[WIDGETS] += "\n" + WIDGET_HELPERS + "\n"

    data[HEADER] = data[HEADER].replace(
        HEADER_START, '''                let ec_scroll_key = ui.scope_id().with("effectcraft.android.ec.scroll-request");
                let ec_scroll_target = ui.ctx().data_mut(|d| d.remove_temp::<f32>(ec_scroll_key));
                let mut ec_scroll = egui::ScrollArea::vertical()
                    .id_salt("effectcraft.android.ec_menu_scroll")
                    .max_height(236.0)
                    .auto_shrink([true, true]);
                if let Some(target) = ec_scroll_target {
                    ec_scroll = ec_scroll.vertical_scroll_offset(target);
                }
                let ec_out = ec_scroll.show(ui, |ui| {''', 1)
    data[HEADER] = data[HEADER].replace(
        HEADER_END, HEADER_END + '''
                crate::widgets::android_record_menu_scroll(ui, &ec_out, ec_scroll_key);''', 1)
    data[VIEWER] = data[VIEWER].replace(viewer_old, viewer_new, 1)
    data[VIEWER] = data[VIEWER].replace(HOVER_OLD, HOVER_NEW, 1)
    for key, path in files.items():
        path.write_text(data[key], encoding="utf-8")
    print("PASS: EffectCraft Android.8 menu scroll target and viewer edit guards staged")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_android_menu_scroll.py <temporary-upstream-root>")
    apply(Path(sys.argv[1]))
