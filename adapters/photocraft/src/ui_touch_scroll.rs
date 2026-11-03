//! UI-only Android touch scrolling for menus, lists and side panels.
//! Adapts the gesture distinction in morte2437/photocraft-android
//! apps/photocraft-android/src/pad/router.rs without replacing NativeActivity.
//! Canvas strokes, pinch gestures, stylus, and keyboard input remain untouched.
use egui::{Event, MouseWheelSource, MouseWheelUnit, PointerButton, Pos2, RawInput, TouchId, TouchPhase, Vec2};

struct Finger {
    id: TouchId,
    pos: Pos2,
    start: Pos2,
    ui_only: bool,
}

#[derive(Default)]
pub(crate) struct UiTouchScroll {
    fingers: Vec<Finger>,
    last_center: Option<Pos2>,
    single_scroll: bool,
}
impl UiTouchScroll {
    fn popup_at(ctx: &egui::Context, at: Pos2) -> bool {
        ctx.layer_id_at(at)
            .is_some_and(|layer| layer.order >= egui::Order::Foreground)
    }
    fn ui_at(ctx: &egui::Context, area: egui::Rect, at: Pos2) -> bool {
        let margin = (area.width() * 0.235).clamp(120.0, 380.0);
        at.y < area.top() + 135.0 || at.x < area.left() + 95.0
            || at.x > area.right() - margin || Self::popup_at(ctx, at)
    }
    pub(crate) fn route(&mut self, ctx: &egui::Context, raw: &mut RawInput) {
        let area = raw.screen_rect.unwrap_or_else(|| ctx.content_rect());
        let mut wheels: Vec<(Pos2, Vec2)> = Vec::new();
        let mut consume_pointer = false;
        let mut cancel_drag: Option<Pos2> = None;
        for event in &raw.events {
            if let Event::Touch { id, phase, pos, .. } = event {
                match phase {
                    TouchPhase::Start => {
                        if self.fingers.len() < 4 && !self.fingers.iter().any(|f| f.id == *id) {
                            self.fingers.push(Finger {
                                id: *id, pos: *pos, start: *pos,
                                // One-finger scroll is restricted to a popup/list overlay:
                                // dragging ordinary sliders/tools or the canvas is unchanged.
                                ui_only: Self::popup_at(ctx, *pos),
                            });
                        }
                        self.last_center = None;
                        self.single_scroll = false;
                    }
                    TouchPhase::Move => {
                        let finger_count = self.fingers.len();
                        if let Some(f) = self.fingers.iter_mut().find(|f| f.id == *id) {
                            let delta = *pos - f.pos;
                            f.pos = *pos;
                            if finger_count == 1 && f.ui_only {
                                let moved = *pos - f.start;
                                if self.single_scroll || moved.y.abs() > 8.0 && moved.y.abs() > moved.x.abs() * 1.2 {
                                    if !self.single_scroll {
                                        cancel_drag = Some(f.start);
                                        self.single_scroll = true;
                                    }
                                    if delta.length_sq() > 0.25 {
                                        wheels.push((*pos, delta));
                                    }
                                    consume_pointer = true;
                                }
                            }
                        }
                        if self.fingers.len() == 2 {
                            let center = self.fingers[0].pos + (self.fingers[1].pos - self.fingers[0].pos) * 0.5;
                            if let Some(last) = self.last_center {
                                let delta = center - last;
                                if delta.length_sq() > 0.25 && Self::ui_at(ctx, area, center) {
                                    wheels.push((center, delta));
                                    consume_pointer = true;
                                }
                            }
                            self.last_center = Some(center);
                        }
                    }
                    TouchPhase::End | TouchPhase::Cancel => {
                        if self.single_scroll {
                            consume_pointer = true; // prevent release from selecting a row
                        }
                        self.fingers.retain(|finger| finger.id != *id);
                        self.last_center = None;
                        self.single_scroll = false;
                    }
                }
            }
        }
        if consume_pointer {
            // Android's winit touch emulation moves/drags the mouse on a swipe,
            // which selects a menu row instead of scrolling. Suppress that emulated
            // drag ONLY in frames we recognized a UI swipe.
            raw.events.retain(|event| !matches!(event, Event::PointerMoved(_) | Event::PointerButton { .. }));
        }
        if let Some(pos) = cancel_drag {
            raw.events.push(Event::PointerButton {
                pos, button: PointerButton::Primary, pressed: false,
                modifiers: egui::Modifiers::NONE,
            });
        }
        for (pos, delta) in wheels {
            raw.events.push(Event::PointerMoved(pos));
            raw.events.push(Event::MouseWheel {
                unit: MouseWheelUnit::Point, delta, phase: TouchPhase::Move,
                modifiers: egui::Modifiers::NONE, source: MouseWheelSource::Trackpad,
            });
        }
    }
}
