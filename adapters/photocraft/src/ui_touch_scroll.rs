//! A conservative first-stage port of PhotoCraft Android's menu/panel touch scroll.
//!
//! Reference: morte2437/photocraft-android, apps/photocraft-android/src/pad/router.rs
//! (two-finger UI scrolling, mouse-wheel-style event routing).
//!
//! Its full router depends on GameActivity pen JNI, Shortcut Pad and UI layer
//! snapshots; do not replace our owner-tested NativeActivity touch/SAF input.
//! This module adds UI-region scrolling only; canvas gestures are unchanged.
use egui::{Event, MouseWheelSource, MouseWheelUnit, Pos2, RawInput, TouchId, TouchPhase, Vec2};

#[derive(Default)]
pub(crate) struct UiTouchScroll {
    fingers: Vec<(TouchId, Pos2)>,
    last_center: Option<Pos2>,
}
impl UiTouchScroll {
    fn update_touch(&mut self, id: TouchId, pos: Pos2) {
        if let Some((_, at)) = self.fingers.iter_mut().find(|(finger, _)| *finger == id) {
            *at = pos;
        } else if self.fingers.len() < 4 {
            self.fingers.push((id, pos));
        }
    }
    fn ui_target(ctx: &egui::Context, area: egui::Rect, at: Pos2) -> bool {
        // Tool palette, upper menus/options, and document side panels.
        // A popup menu/dialog drawn over the canvas has a foreground layer.
        // Do not translate canvas pinch/rotate into a scroll (user preservation).
        let margin = (area.width() * 0.235).clamp(120.0, 380.0);
        let frame_ui = at.y < area.top() + 135.0
            || at.x < area.left() + 95.0
            || at.x > area.right() - margin;
        let popup = ctx.layer_id_at(at)
            .is_some_and(|layer| layer.order >= egui::Order::Foreground);
        frame_ui || popup
    }
    pub(crate) fn route(&mut self, ctx: &egui::Context, raw: &mut RawInput) {
        let area = raw.screen_rect.unwrap_or_else(|| ctx.content_rect());
        let mut wheels: Vec<(Pos2, Vec2)> = Vec::new();
        for event in &raw.events {
            if let Event::Touch { id, phase, pos, .. } = event {
                match phase {
                    TouchPhase::Start => {
                        self.update_touch(*id, *pos);
                        self.last_center = None;
                    }
                    TouchPhase::Move => {
                        self.update_touch(*id, *pos);
                        if self.fingers.len() == 2 {
                            let center = self.fingers[0].1 + (self.fingers[1].1 - self.fingers[0].1) * 0.5;
                            if let Some(last) = self.last_center {
                                let delta = center - last;
                                if delta.length_sq() > 0.25 && Self::ui_target(ctx, area, center) {
                                    wheels.push((center, delta));
                                }
                            }
                            self.last_center = Some(center);
                        } else {
                            self.last_center = None;
                        }
                    }
                    TouchPhase::End | TouchPhase::Cancel => {
                        self.fingers.retain(|(finger, _)| *finger != *id);
                        self.last_center = None;
                    }
                }
            }
        }
        for (pos, delta) in wheels {
            raw.events.push(Event::PointerMoved(pos));
            raw.events.push(Event::MouseWheel {
                unit: MouseWheelUnit::Point,
                delta,
                phase: TouchPhase::Move,
                modifiers: egui::Modifiers::NONE,
                source: MouseWheelSource::Trackpad,
            });
        }
    }
}
