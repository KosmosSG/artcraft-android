                // Android 14+ can report two-finger distances (pixels) and
                // pinch ratios on MOVE instead of legacy HSCROLL/VSCROLL.
                // A single event may carry both forms. Consume it only once.
                if pointer_class && matches!(motion_event.action(),
                    MotionAction::Move | MotionAction::HoverMove | MotionAction::Scroll)
                    && motion_event.pointer_count() > 0
                {
                    let p = motion_event.pointer_at_index(0);
                    let axis_x = Axis::from(50u32);
                    let axis_y = Axis::from(51u32);
                    let axis_scale = Axis::from(52u32);
                    let mut dx = 0.0_f64;
                    let mut dy = 0.0_f64;
                    let mut log_scale = 0.0_f64;
                    let current = (p.axis_value(axis_x), p.axis_value(axis_y), p.axis_value(axis_scale));
                    let history = p.history().map(|h| (h.axis_value(axis_x), h.axis_value(axis_y), h.axis_value(axis_scale)));
                    for (x, y, scale) in history.chain(std::iter::once(current)) {
                        if x.is_finite() { dx += f64::from(x); }
                        if y.is_finite() { dy += f64::from(y); }
                        if scale.is_finite() && scale > 0.0 { log_scale += f64::from(scale).ln(); }
                    }
                    if dx != 0.0 || dy != 0.0 || log_scale != 0.0 {
                        let mut emit = |event| callback(event::Event::WindowEvent { window_id, event }, self.window_target());
                        emit(event::WindowEvent::CursorMoved { device_id, position: pointer_position(&p) });
                        if dx != 0.0 || dy != 0.0 {
                            emit(event::WindowEvent::MouseWheel { device_id,
                                delta: event::MouseScrollDelta::PixelDelta(PhysicalPosition { x: -dx, y: -dy }),
                                phase: event::TouchPhase::Moved });
                        }
                        if log_scale != 0.0 {
                            emit(event::WindowEvent::PinchGesture { device_id, delta: log_scale, phase: event::TouchPhase::Moved });
                        }
                        return InputStatus::Handled;
                    }
                }
