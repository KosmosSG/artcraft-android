"""PDFCraft Android touchpad: scroll on 2-finger MOVE and preserve pointer at WHEEL.

Android/HONOR keyboards may send scroll as SOURCE_MOUSE AXIS_VSCROLL or as
SOURCE_TOUCHPAD two-pointer move. Both must reach egui's document scroll
container with a valid cursor position, never as text-selection drags.
"""
def patch(source: str) -> str:
    marker="PDFCRAFT_ANDROID_TRACKPAD_SCROLL"
    if marker in source:
        assert "pdfcraft_trackpad_last" in source
        return source
    def swap(a,b):
        nonlocal source
        n=source.count(a)
        if n!=1:raise ValueError(f"PDFCraft touchpad overlay expected one {a[:75]!r}, got {n}")
        source=source.replace(a,b,1)
    swap("    pdfcraft_touch_held: bool,",
         """    pdfcraft_touch_held: bool,
    // PDFCRAFT_ANDROID_TRACKPAD_SCROLL
    pdfcraft_trackpad_last: Option<PhysicalPosition<f64>>,
    pdfcraft_trackpad_cursor: Option<PhysicalPosition<f64>>,""")
    swap("            pdfcraft_touch_held: false,",
         """            pdfcraft_touch_held: false,
            pdfcraft_trackpad_last: None,
            pdfcraft_trackpad_cursor: None,""")
    swap("""                match motion_event.action() {
                    // Hover: the cursor moves without any button held.""",
         """                // Android SOURCE_TOUCHPAD is POSITION-class, not POINTER-class.
                // Therefore the shared "Scroll if pointer_class" branch silently
                // drops ACTION_SCROLL from a real trackpad. HONOR can also report
                // trackpads as SOURCE_MOUSE (pointer-class) with two pointers.
                let touchpad_source = motion_event.source() == Source::Touchpad;
                let mouse_source = motion_event.source() == Source::Mouse;
                if touchpad_source || mouse_source {
                    let points: Vec<_> = motion_event.pointers().map(|p| pointer_position(&p)).collect();
                    if motion_event.action() == MotionAction::HoverMove && points.len() == 1 {
                        self.pdfcraft_trackpad_cursor = points.first().copied();
                    }
                    let axes = motion_event.pointers().next().map(|pointer| {
                        (pointer.axis_value(Axis::Vscroll), pointer.axis_value(Axis::Hscroll))
                    }).unwrap_or((0.0, 0.0));
                    // Position-class SOURCE_TOUCHPAD ACTION_SCROLL would never reach
                    // the pointer-class wheel arm; handle it explicitly.
                    if touchpad_source && (motion_event.action() == MotionAction::Scroll
                        || (motion_event.action() == MotionAction::Move && points.len() == 1
                            && (axes.0 != 0.0 || axes.1 != 0.0)))
                    {
                        let pos = self.pdfcraft_trackpad_cursor.or_else(|| points.first().copied());
                        if let Some(position) = pos {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                        }
                        if axes.0 != 0.0 || axes.1 != 0.0 {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::MouseWheel {
                                    device_id,
                                    delta: event::MouseScrollDelta::PixelDelta(PhysicalPosition {
                                        x: f64::from(axes.1)*POINTS_PER_LINE as f64,
                                        y: f64::from(axes.0)*POINTS_PER_LINE as f64,
                                    }),
                                    phase: event::TouchPhase::Moved,
                                },
                            }, self.window_target());
                        }
                        return input_status;
                    }
                    if points.len() >= 2 {
                        let a = points[0]; let b = points[1];
                        let mid = PhysicalPosition { x: (a.x+b.x)/2.0, y: (a.y+b.y)/2.0 };
                        let old = self.pdfcraft_trackpad_last.replace(mid);
                        if let Some(position) = self.pdfcraft_trackpad_cursor.or(Some(mid)) {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                        }
                        if motion_event.action() == MotionAction::Move {
                            if let Some(last) = old {
                                let delta = PhysicalPosition {
                                    x: (mid.x-last.x)*1.5, y: (mid.y-last.y)*1.5,
                                };
                                if delta.x != 0.0 || delta.y != 0.0 {
                                    callback(event::Event::WindowEvent {
                                        window_id,
                                        event: event::WindowEvent::MouseWheel {
                                            device_id, delta: event::MouseScrollDelta::PixelDelta(delta),
                                            phase: event::TouchPhase::Moved,
                                        },
                                    }, self.window_target());
                                }
                            }
                        }
                        return input_status; // Never select PDF text while trackpad scrolling.
                    } else {
                        self.pdfcraft_trackpad_last = None;
                    }
                }

                match motion_event.action() {
                    // Hover: the cursor moves without any button held.""")
    swap("""                    MotionAction::Scroll if pointer_class => {
                        let (vertical, horizontal) = motion_event""",
         """                    MotionAction::Scroll if pointer_class => {
                        // Wheel events often arrive without a preceding HoverMove.
                        // PDFCraft ignores a wheel if the pointer is absent or outside canvas.
                        if let Some(position) = self.pdfcraft_trackpad_cursor.or_else(|| {
                            motion_event.pointers().next().map(|pointer| pointer_position(&pointer))
                        }) {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                        }
                        let (vertical, horizontal) = motion_event""")
    assert marker in source
    return source
