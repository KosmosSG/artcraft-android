"""Adapt PDFCraft's pinned Android touch overlay to single-finger swipe navigation.

Tap = click. Fast drag = scroll PDF. Hold >=300ms then drag = actual
PDF text selection/annotation in Select mode. Two-finger pan/pinch remains;
second-finger takeover explicitly releases an active emulated pointer.
Neither a stylus nor a mouse/trackpad enters this branch.
"""
def patch(source: str) -> str:
    marker="PDFCRAFT_ANDROID_ONE_FINGER_NAVIGATION"
    if marker in source:
        assert "PdfTouchMode::SinglePan" in source and "pdfcraft_single_started" in source
        return source
    def swap(a,b):
        nonlocal source
        n=source.count(a)
        if n!=1:
            raise ValueError(f"One-finger pinned overlay changed: {n} matches for {a[:100]!r}")
        source=source.replace(a,b,1)

    swap("enum PdfTouchMode { Pending, Scroll, Pinch }",
         "enum PdfTouchMode { Pending, Scroll, Pinch, SinglePan, SingleSelect }")
    swap("    pdfcraft_touch_held: bool,",
         """    pdfcraft_touch_held: bool,
    // PDFCRAFT_ANDROID_ONE_FINGER_NAVIGATION
    pdfcraft_single_started: Option<std::time::Instant>,
    pdfcraft_single_last: Option<PhysicalPosition<f64>>,""")
    swap("            pdfcraft_touch_held: false,",
         """            pdfcraft_touch_held: false,
            pdfcraft_single_started: None,
            pdfcraft_single_last: None,""")
    swap("""                    self.pdfcraft_touch_mode = PdfTouchMode::Pending;
                }
                false
            }
            MotionAction::PointerDown if count >= 2 => {""",
         """                    self.pdfcraft_touch_mode = PdfTouchMode::Pending;
                    self.pdfcraft_single_started = Some(std::time::Instant::now());
                    self.pdfcraft_single_last = Some(pointer_position(&p));
                }
                // Delay native text down until we can distinguish an ordinary
                // swipe from a deliberate long-press selection.
                true
            }
            MotionAction::PointerDown if count >= 2 => {""")
    swap("""                if !self.pdfcraft_touch_held {
                    if let Some((id, location)) = self.pdfcraft_touch_first.take() {
                        // The first finger was delivered as a normal touch on Down.
                        // Cancel it BEFORE any synthesized wheel event: no accidental
                        // text selection or lingering pressed pointer state.
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::Touch(event::Touch {
                                device_id, phase: event::TouchPhase::Cancelled,
                                location, id, force: None,
                            }),
                        }, self.window_target());
                    }
                }
                self.pdfcraft_touch_held = true;""",
         """                if !self.pdfcraft_touch_held {
                    if let Some((id, location)) = self.pdfcraft_touch_first.take() {
                        if self.pdfcraft_touch_mode == PdfTouchMode::SingleSelect {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::Touch(event::Touch {
                                    device_id, phase: event::TouchPhase::Cancelled,
                                    location, id, force: None,
                                }),
                            }, self.window_target());
                            // egui-winit's touch-cancel branch calls PointerGone but
                            // does not release its emulated primary mouse button.
                            // Without this, 2-finger panning keeps selecting text.
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::MouseInput {
                                    device_id, state: event::ElementState::Released,
                                    button: event::MouseButton::Left,
                                },
                            }, self.window_target());
                        }
                    }
                }
                self.pdfcraft_single_started = None;
                self.pdfcraft_single_last = None;
                self.pdfcraft_touch_held = true;""")
    swap("""            MotionAction::Move if self.pdfcraft_touch_held => {""",
         """            // One finger: navigate immediately on a swipe; edit/select on
            // long press. This keeps Select's ability to highlight actual PDF
            // text while allowing ordinary one-finger document navigation.
            MotionAction::Move if !self.pdfcraft_touch_held && count == 1 => {
                let pointer = motion.pointer_at_index(0);
                let pos = pointer_position(&pointer);
                let Some((id, start)) = self.pdfcraft_touch_first else { return true; };
                let last = self.pdfcraft_single_last.unwrap_or(start);
                let dx_from_start = pos.x - start.x;
                let dy_from_start = pos.y - start.y;
                let moved = (dx_from_start*dx_from_start + dy_from_start*dy_from_start).sqrt();
                if self.pdfcraft_touch_mode == PdfTouchMode::Pending {
                    let held_long_enough = self.pdfcraft_single_started
                        .is_some_and(|when| when.elapsed() >= std::time::Duration::from_millis(300));
                    if held_long_enough {
                        self.pdfcraft_touch_mode = PdfTouchMode::SingleSelect;
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::Touch(event::Touch {
                                device_id, phase: event::TouchPhase::Started,
                                location: start, id, force: None,
                            }),
                        }, self.window_target());
                    } else if moved >= 12.0 {
                        self.pdfcraft_touch_mode = PdfTouchMode::SinglePan;
                    }
                }
                match self.pdfcraft_touch_mode {
                    PdfTouchMode::SinglePan => {
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::CursorMoved {
                                device_id, position: pos,
                            },
                        }, self.window_target());
                        let delta_x = pos.x - last.x;
                        let delta_y = pos.y - last.y;
                        if delta_x != 0.0 || delta_y != 0.0 {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::MouseWheel {
                                    device_id,
                                    delta: event::MouseScrollDelta::PixelDelta(
                                        PhysicalPosition { x: delta_x * 1.5, y: delta_y * 1.5 }
                                    ),
                                    phase: event::TouchPhase::Moved,
                                },
                            }, self.window_target());
                        }
                    }
                    PdfTouchMode::SingleSelect => {
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::Touch(event::Touch {
                                device_id, phase: event::TouchPhase::Moved,
                                location: pos, id, force: None,
                            }),
                        }, self.window_target());
                    }
                    _ => {}
                }
                self.pdfcraft_single_last = Some(pos);
                true
            }
            MotionAction::Move if self.pdfcraft_touch_held => {""")
    swap("""            MotionAction::Up | MotionAction::Cancel => {
                self.pdfcraft_touch_first = None;
                false
            }""",
         """            MotionAction::Up | MotionAction::Cancel => {
                if let Some((id, start)) = self.pdfcraft_touch_first.take() {
                    let pos = if count == 1 {
                        pointer_position(&motion.pointer_at_index(0))
                    } else {
                        self.pdfcraft_single_last.unwrap_or(start)
                    };
                    if self.pdfcraft_touch_mode == PdfTouchMode::Pending
                        && motion.action() == MotionAction::Up {
                        // Tap: native document button actions still receive down/up.
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::Touch(event::Touch {
                                device_id, phase: event::TouchPhase::Started,
                                location: start, id, force: None,
                            }),
                        }, self.window_target());
                    }
                    if self.pdfcraft_touch_mode == PdfTouchMode::Pending
                        || self.pdfcraft_touch_mode == PdfTouchMode::SingleSelect {
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::Touch(event::Touch {
                                device_id, phase: if motion.action() == MotionAction::Cancel {
                                    event::TouchPhase::Cancelled
                                } else {
                                    event::TouchPhase::Ended
                                },
                                location: pos, id, force: None,
                            }),
                        }, self.window_target());
                    }
                }
                self.pdfcraft_single_started = None;
                self.pdfcraft_single_last = None;
                self.pdfcraft_touch_mode = PdfTouchMode::Pending;
                true
            }""")
    # An interrupted two-finger session may end with one finger; it must
    # never convert that residual movement into a text-select gesture.
    assert "PDFCRAFT_ANDROID_ONE_FINGER_NAVIGATION" in source
    return source
