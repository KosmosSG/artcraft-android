//! Android popup / sidebar touch scrolling without egui-winit drag selection.
//! Inspired by the routing separation used by morte2437/photocraft-android.
//! A finger starting on a popup is NOT pressed until it lifts. Thus a swipe can
//! emit wheel events without ever selecting/dragging a menu item. Simple taps
//! synthesize press+release on lift. Canvas/pen gestures are not intercepted.
use egui::{Event, MouseWheelSource, MouseWheelUnit, PointerButton, Pos2, RawInput, TouchId, TouchPhase, Vec2};

struct Finger {
    id: TouchId,
    pos: Pos2,
    start: Pos2,
    popup: bool,
    scrolling: bool,
}
#[derive(Default)]
pub(crate) struct UiTouchScroll {
    fingers: Vec<Finger>,
    two_center: Option<Pos2>,
}
impl UiTouchScroll {
    fn in_popup(ctx: &egui::Context, pos: Pos2) -> bool {
        ctx.layer_id_at(pos).is_some_and(|layer| layer.order >= egui::Order::Foreground)
            || (egui::Popup::is_any_open(ctx) && ctx.layer_id_at(pos).is_some())
    }
    fn in_panels(ctx: &egui::Context, screen: egui::Rect, pos: Pos2) -> bool {
        let margin = (screen.width() * 0.235).clamp(120.0, 380.0);
        pos.x > screen.right() - margin || pos.x < screen.left() + 94.0
            || pos.y < screen.top() + 135.0 || Self::in_popup(ctx, pos)
    }
    pub(crate) fn route(&mut self, ctx: &egui::Context, raw: &mut RawInput) {
        let screen = raw.screen_rect.unwrap_or_else(|| ctx.content_rect());
        let mut wheel: Vec<(Pos2, Vec2)> = Vec::new();
        let mut delayed_taps: Vec<Pos2> = Vec::new();
        // Drop the platform's first-finger pointer emulation if *this* finger
        // began on a menu. Otherwise its early Down selects a row immediately.
        let mut suppress_pointer = self.fingers.iter().any(|f| f.popup);
        let events = raw.events.clone();
        for event in &events {
            if let Event::Touch { id, phase, pos, .. } = event {
                match phase {
                    TouchPhase::Start => {
                        if self.fingers.len() < 4 && self.fingers.iter().all(|f| f.id != *id) {
                            let popup = Self::in_popup(ctx, *pos);
                            self.fingers.push(Finger {
                                id: *id, pos: *pos, start: *pos, popup,
                                scrolling: false,
                            });
                            suppress_pointer |= popup;
                        }
                        self.two_center = None;
                    }
                    TouchPhase::Move => {
                        let count = self.fingers.len();
                        if let Some(f) = self.fingers.iter_mut().find(|f| f.id == *id) {
                            let delta = *pos - f.pos;
                            f.pos = *pos;
                            if count == 1 && f.popup {
                                suppress_pointer = true;
                                let drag = *pos - f.start;
                                if !f.scrolling && drag.y.abs() > 6.0
                                    && drag.y.abs() > drag.x.abs() * 1.1 {
                                    f.scrolling = true;
                                }
                                if f.scrolling && delta.length_sq() > 0.1 {
                                    wheel.push((*pos, delta));
                                }
                            }
                        }
                        if count == 2 {
                            let mid = self.fingers[0].pos
                                + (self.fingers[1].pos - self.fingers[0].pos) * 0.5;
                            if let Some(last) = self.two_center {
                                let delta = mid - last;
                                if delta.length_sq() > 0.1 && Self::in_panels(ctx, screen, mid) {
                                    wheel.push((mid, delta));
                                    suppress_pointer = true;
                                }
                            }
                            self.two_center = Some(mid);
                        }
                    }
                    TouchPhase::End | TouchPhase::Cancel => {
                        if let Some(f) = self.fingers.iter().find(|f| f.id == *id) {
                            if f.popup {
                                suppress_pointer = true;
                                if *phase == TouchPhase::End && !f.scrolling
                                    && (*pos - f.start).length_sq() <= 100.0 {
                                    delayed_taps.push(*pos);
                                }
                            }
                        }
                        self.fingers.retain(|f| f.id != *id);
                        self.two_center = None;
                    }
                }
            }
        }
        if suppress_pointer {
            raw.events.retain(|event| !matches!(event,
                Event::PointerMoved(_) | Event::PointerButton { .. } | Event::PointerGone));
        }
        for pos in delayed_taps {
            raw.events.push(Event::PointerMoved(pos));
            for pressed in [true, false] {
                raw.events.push(Event::PointerButton {
                    pos, button: PointerButton::Primary, pressed,
                    modifiers: egui::Modifiers::NONE,
                });
            }
        }
        for (pos, delta) in wheel {
            raw.events.push(Event::PointerMoved(pos));
            raw.events.push(Event::MouseWheel {
                unit: MouseWheelUnit::Point, delta, phase: TouchPhase::Move,
                modifiers: egui::Modifiers::NONE, source: MouseWheelSource::Trackpad,
            });
        }
    }
}
