"""Route tablet trackpad motion to the hovered, scrollable Android menu level."""
import argparse
from pathlib import Path
from photocraft_v0201_keyboard_diagnostics_overlay import patch

parser = argparse.ArgumentParser()
for name in ("upstream", "adapter", "vendor"):
    parser.add_argument("--" + name, type=Path, required=True)
a = parser.parse_args()
host = a.adapter / "src/lib.rs"
wheel = a.adapter / "src/trackpad_wheel.rs"
menus = a.upstream / "crates/ui-egui/src/menus.rs"
nav = menus.parent / "menus/menu_nav.rs"
library = a.vendor / "android-activity/src/lib.rs"
native = a.vendor / "android-activity/src/native_activity/mod.rs"
patch(a.adapter / "Cargo.toml", 'version = "0.20.1-android.7"', 'version = "0.20.1-android.8"')

# Cache the actual popup level, including its current offset and bounds.
# Raw input arrives before the next layout, so use the last completed pass.
with menus.open("a") as f:
    f.write("""
#[cfg(target_os = "android")]
pub fn pc_hovered_menu(ctx: &egui::Context) -> Option<(egui::Id, f32, f32)> {
    let pass = ctx.cumulative_pass_nr();
    let (seen, key, offset, max) = ctx.data(|d|
        d.get_temp::<(u64, egui::Id, f32, f32)>(egui::Id::new("pc-trackpad-menu")))?;
    (seen.saturating_add(1) >= pass).then_some((key, offset, max))
}
""")
patch(nav, "    let offset = out.state.clamped_offset().y;", """    let offset = out.state.clamped_offset().y;
    #[cfg(target_os = "android")]
    if max > 0.0 && pointer_on(ui, out.inner_rect) {
        let pass = ctx.cumulative_pass_nr();
        ctx.data_mut(|d| d.insert_temp(egui::Id::new("pc-trackpad-menu"),
            (pass, scroll_request_id(key), offset, max)));
    }""")

with library.open("a") as f:
    f.write("""
#[derive(Default)]
struct PcMenuScroll {
    target: Option<u64>,
    delta: f32,
    previous: Option<(i32, f32)>,
}
static PC_MENU_SCROLL: std::sync::Mutex<PcMenuScroll> = std::sync::Mutex::new(
    PcMenuScroll { target: None, delta: 0.0, previous: None });

pub fn pc_menu_scroll(target: Option<u64>) -> f32 {
    let mut s = PC_MENU_SCROLL.lock().unwrap();
    if s.target != target {
        *s = PcMenuScroll { target, ..Default::default() };
    }
    std::mem::take(&mut s.delta)
}
""")
patch(native, "            let owner = crate::PHOTOCRAFT_INPUT_OWNER.load", """            if let ndk::event::InputEvent::MotionEvent(m) = &ndk_event {
                let ptr = m.ptr().as_ptr();
                // Android SOURCE_MOUSE / SOURCE_TOUCHPAD. Keep touchscreen and stylus on their usual path.
                let source = unsafe { ndk_sys::AInputEvent_getSource(ptr) };
                let pad = source & 0x100008 == 0x100008;
                if pad || source & 0x2002 == 0x2002 {
                    let mut s = crate::PC_MENU_SCROLL.lock().unwrap();
                    if s.target.is_some() {
                        let action = unsafe { ndk_sys::AMotionEvent_getAction(ptr) } & 255;
                        let count = unsafe { ndk_sys::AMotionEvent_getPointerCount(ptr) };
                        let device = unsafe { ndk_sys::AInputEvent_getDeviceId(ptr) };
                        let mut delta = 0.0;
                        if count > 0 && matches!(action, 2 | 7 | 8) {
                            // AXIS_GESTURE_SCROLL_Y_DISTANCE is per sample in display pixels.
                            let axis = 51;
                            let history = unsafe { ndk_sys::AMotionEvent_getHistorySize(ptr) };
                            for i in 0..history {
                                delta -= unsafe { ndk_sys::AMotionEvent_getHistoricalAxisValue(ptr, axis, 0, i) };
                            }
                            delta -= unsafe { ndk_sys::AMotionEvent_getAxisValue(ptr, axis, 0) };
                        }
                        let pair = count == 2 && matches!(action, 2 | 5);
                        if pair {
                            let y = unsafe { (ndk_sys::AMotionEvent_getY(ptr, 0)
                                + ndk_sys::AMotionEvent_getY(ptr, 1)) * 0.5 };
                            if action == 2 && delta == 0.0 {
                                if let Some((id, previous)) = s.previous {
                                    if id == device { delta = y - previous; }
                                }
                            }
                            s.previous = Some((device, y));
                        } else {
                            s.previous = None;
                        }
                        if delta.is_finite() && delta != 0.0 {
                            s.delta += delta;
                            drop(s);
                            queue.finish_event(ndk_event, true);
                            return true;
                        }
                    }
                }
            }
            let owner = crate::PHOTOCRAFT_INPUT_OWNER.load""")

patch(wheel, "    let native_wheel_present =", """    let menu = photocraft_ui_egui::menus::pc_hovered_menu(ctx);
    let native_delta = android_activity::pc_menu_scroll(menu.map(|m| m.0.value()));
    let native_wheel_present =""")
patch(wheel, "        if native_wheel_present { continue; }",
      "        if native_wheel_present || native_delta != 0.0 { continue; }")
patch(wheel, "        raw.events.push(Event::PointerMoved(pos));",
      "        if menu.is_none() { raw.events.push(Event::PointerMoved(pos)); }")
needle = "    }\n}\n"
patch(wheel, needle, """    }
    if let Some((key, offset, max)) = menu {
        let mut dy = native_delta / ctx.pixels_per_point();
        raw.events.retain(|event| {
            if let Event::MouseWheel { delta, unit, modifiers, .. } = event {
                if !modifiers.any() && delta.y != 0.0 {
                    if native_delta == 0.0 {
                        dy += delta.y * match unit {
                            MouseWheelUnit::Point => 1.0,
                            MouseWheelUnit::Line => 42.0,
                            MouseWheelUnit::Page => rect.height(),
                        };
                    }
                    return false;
                }
            }
            true
        });
        if dy.is_finite() && dy != 0.0 {
            ctx.data_mut(|d| d.insert_temp(key, (offset - dy).clamp(0.0, max)));
            ctx.request_repaint();
        }
    }
}
""")
patch(host, "        self.android_fonts.show(ui.ctx());", """        self.android_fonts.show(ui.ctx());
        if photocraft_ui_egui::menus::pc_hovered_menu(ui.ctx()).is_some() {
            ui.ctx().request_repaint_after(std::time::Duration::from_millis(32));
        }""")
