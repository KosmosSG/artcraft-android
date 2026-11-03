//! Canvas-only two-finger pan/pinch/twist view transform, adapted from the
//! coordinate-preserving algorithm in morte2437/photocraft-android/touch/mod.rs.
//! A gesture changes document VIEW state only; it never mutates image pixels.
use egui::{Event, Pos2, RawInput, Rect, TouchId, TouchPhase};

#[derive(Clone, Copy)]
struct Finger { id: TouchId, pos: Pos2 }

#[derive(Clone, Copy)]
struct ViewMove { from: Pos2, to: Pos2, scale: f32, degrees: f32 }

#[derive(Default)]
pub(crate) struct CanvasTouchGestures {
    fingers: Vec<Finger>,
    previous: Option<(Pos2, Pos2)>,
    moves: Vec<ViewMove>,
}
impl CanvasTouchGestures {
    fn canvas_region(rect: Rect) -> Rect {
        // The NativeActivity tablet layout has toolbar left, panels right,
        // title/options above and status/tabs below; do not steal their touches.
        Rect::from_min_max(
            egui::pos2(rect.left() + 95.0, rect.top() + 135.0),
            egui::pos2(rect.right() - (rect.width() * 0.24).max(175.0), rect.bottom() - 50.0),
        )
    }
    pub(crate) fn route(&mut self, ctx: &egui::Context, raw: &mut RawInput) {
        let area = Self::canvas_region(raw.screen_rect.unwrap_or_else(|| ctx.content_rect()));
        let mut gesture = self.previous.is_some();
        for event in raw.events.clone() {
            if let Event::Touch { id, phase, pos, .. } = event {
                // IMPORTANT: egl/winit reports finger pressure as Some(0.0)
                // (and often Some(nonzero)) on Android too. 'force.is_some()'
                // is NOT a pen classifier; it disabled all finger twist rotation.
                // Restrict to two touches within the canvas instead. An actual
                // stylus/palm classifier must come from MotionEvent toolType
                // and is tracked separately from this UI-only view transform.
                match phase {
                    TouchPhase::Start => {
                        if area.contains(pos) && self.fingers.iter().all(|f| f.id != id)
                            && self.fingers.len() < 2 {
                            self.fingers.push(Finger { id, pos });
                        }
                        if self.fingers.len() == 2 {
                            self.previous = Some((self.fingers[0].pos, self.fingers[1].pos));
                            gesture = true;
                        }
                    }
                    TouchPhase::Move => {
                        if let Some(f) = self.fingers.iter_mut().find(|f| f.id == id) {
                            f.pos = pos;
                        }
                        if self.fingers.len() == 2 {
                            let (p, q) = (self.fingers[0].pos, self.fingers[1].pos);
                            if let Some((a, b)) = self.previous {
                                let before = b - a;
                                let after = q - p;
                                let dist = before.length();
                                let new_dist = after.length();
                                if dist > 10.0 && new_dist > 10.0 {
                                    let angle = after.y.atan2(after.x) - before.y.atan2(before.x);
                                    let degrees = angle.to_degrees();
                                    let from = a + before * 0.5;
                                    let to = p + after * 0.5;
                                    if degrees.is_finite() {
                                        self.moves.push(ViewMove {
                                            from, to,
                                            scale: (new_dist / dist).clamp(0.75, 1.25),
                                            degrees: ((degrees + 180.0).rem_euclid(360.0) - 180.0)
                                                .clamp(-30.0, 30.0),
                                        });
                                    }
                                }
                            }
                            self.previous = Some((p, q));
                            gesture = true;
                        }
                    }
                    TouchPhase::End | TouchPhase::Cancel => {
                        self.fingers.retain(|f| f.id != id);
                        self.previous = None;
                    }
                }
            }
        }
        if gesture {
            // Prevent the winit first-finger mouse emulation from painting
            // while two fingers are rotating/pinching the canvas.
            raw.events.retain(|event| !matches!(event,
                Event::PointerMoved(_) | Event::PointerButton { .. }));
        }
    }
    pub(crate) fn apply(&mut self, app: &mut photocraft_ui_egui::PhotocraftApp) {
        if self.moves.is_empty() { return; }
        use photocraft_ui_egui::canvas::ViewXform;
        app.sync_views();
        for mv in self.moves.drain(..) {
            let Some(index) = app.session.active_index() else { break };
            let Some(xf) = ViewXform::active(app) else { break };
            let Some(v) = app.ui.views.get_mut(index) else { break };
            let original = xf.to_doc(mv.from);
            let zoom = (v.zoom * mv.scale).clamp(0.01, 32.0);
            let turn = if xf.flip { -mv.degrees } else { mv.degrees };
            let rotation = (xf.rotation + turn + 540.0).rem_euclid(360.0) - 180.0;
            let next = ViewXform {
                zoom: xf.zoom * (zoom / v.zoom.max(0.00001)),
                rotation,
                center: [0.0, 0.0],
                ..xf
            };
            let moved = next.to_doc(mv.to);
            let center = [
                (original[0] - moved[0]) as f32,
                (original[1] - moved[1]) as f32,
            ];
            if zoom.is_finite() && rotation.is_finite()
                && center.iter().all(|c| c.is_finite()) {
                v.fit_pending = false;
                v.fill_pending = false;
                v.zoom = zoom;
                v.rotation = rotation;
                v.center = center;
            }
        }
    }
}
