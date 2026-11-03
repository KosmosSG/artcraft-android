//! Wheel events from Android trackpads. Some MagicOS keyboards deliver a
//! MotionEvent.ACTION_SCROLL to NativeActivity without winit translating it.
//! Keep the platform's own MouseWheel events when present: never double-scroll.
use crate::AndroidFileBridge;
use egui::{Event, MouseWheelSource, MouseWheelUnit, Pos2, RawInput, TouchPhase, Vec2};

pub(crate) fn route(bridge: &AndroidFileBridge, ctx: &egui::Context, raw: &mut RawInput) {
    let native_wheel_present = raw.events.iter().any(|e| matches!(e, Event::MouseWheel { .. }));
    let rect = raw.screen_rect.unwrap_or_else(|| ctx.content_rect());
    for _ in 0..16 {
        let Ok(Some(data)) = bridge.poll_trackpad_scroll() else { break };
        if native_wheel_present { continue; }
        let numbers: Vec<f32> = data.split(',').filter_map(|p| p.parse::<f32>().ok()).collect();
        if numbers.len() != 6 { continue; }
        let [dx, dy, x, y, width, height]: [f32; 6] = match numbers.try_into() {
            Ok(v) => v, Err(_) => continue,
        };
        if width < 1.0 || height < 1.0 { continue; }
        let pos = Pos2::new(
            rect.left() + x.clamp(0.0, width) / width * rect.width(),
            rect.top() + y.clamp(0.0, height) / height * rect.height(),
        );
        // Android AXIS_VSCROLL is + up; egui is + up. A wheel step
        // corresponds to 42 points; high-res trackpads supply fractions.
        let delta = Vec2::new(dx * 42.0, dy * 42.0);
        if delta.length_sq() <= 0.0001 { continue; }
        raw.events.push(Event::PointerMoved(pos));
        raw.events.push(Event::MouseWheel {
            unit: MouseWheelUnit::Point, delta, phase: TouchPhase::Move,
            modifiers: egui::Modifiers::NONE, source: MouseWheelSource::Trackpad,
        });
    }
}
