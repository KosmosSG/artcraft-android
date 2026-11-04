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
    pdfcraft_trackpad_cursor: Option<PhysicalPosition<f64>>,
    // PDFCRAFT_ANDROID_TRACKPAD_PINCH
    pdfcraft_trackpad_origin: Option<(PhysicalPosition<f64>, f64)>,
    pdfcraft_trackpad_spread: Option<f64>,
    pdfcraft_trackpad_pinching: bool,""")
    swap("            pdfcraft_touch_held: false,",
         """            pdfcraft_touch_held: false,
            pdfcraft_trackpad_last: None,
            pdfcraft_trackpad_cursor: None,
            pdfcraft_trackpad_origin: None,
            pdfcraft_trackpad_spread: None,
            pdfcraft_trackpad_pinching: false,""")
    swap("""                match motion_event.action() {
                    // Hover: the cursor moves without any button held.""",
         """                // Android SOURCE_TOUCHPAD is POSITION-class, not POINTER-class.
                // Therefore the shared "Scroll if pointer_class" branch silently
                // drops ACTION_SCROLL from a real trackpad. HONOR can also report
                // trackpads as SOURCE_MOUSE (pointer-class) with two pointers.
                let touchpad_source = matches!(
                    motion_event.source(), Source::Touchpad | Source::TouchNavigation
                );
                let mouse_source = matches!(
                    motion_event.source(), Source::Mouse | Source::MouseRelative
                );
                if touchpad_source || mouse_source {
                    // PDFCRAFT_ANDROID_PRECISE_TRACKPAD_SCROLL: no per-move allocation.
                    let mut pointers = motion_event.pointers();
                    let first = pointers.next();
                    let second = pointers.next();
                    let first_position = first.as_ref().map(pointer_position);
                    let second_position = second.as_ref().map(pointer_position);
                    let point_count = motion_event.pointer_count();
                    if matches!(motion_event.action(),
                        MotionAction::HoverMove | MotionAction::HoverEnter | MotionAction::Move
                    ) && point_count == 1 {
                        if mouse_source || self.pdfcraft_trackpad_cursor.is_none() {
                            self.pdfcraft_trackpad_cursor = first_position;
                        }
                    }
                    let axes = first.as_ref().map(|pointer| {
                        (pointer.axis_value(Axis::Vscroll), pointer.axis_value(Axis::Hscroll))
                    }).unwrap_or((0.0, 0.0));
                    let has_scroll_axes = axes.0.is_finite() && axes.1.is_finite()
                        && (axes.0 != 0.0 || axes.1 != 0.0);
                    let fractional_scroll = axes.0.fract() != 0.0
                        || axes.1.fract() != 0.0;
                    // Some HONOR two-finger trackpads report fractional
                    // SOURCE_MOUSE VSCROLL/HSCROLL, not moving touch pointers.
                    // Coarse physical mouse notches still use stock winit wheels.
                    let precision_trackpad = touchpad_source
                        || (mouse_source && (fractional_scroll || point_count >= 2));
                    let axis_action = matches!(motion_event.action(),
                        MotionAction::Scroll | MotionAction::Move);
                    if precision_trackpad && has_scroll_axes && axis_action {
                        let pos = self.pdfcraft_trackpad_cursor.or(first_position);
                        if let Some(position) = pos {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                        }
                        // PanGesture reaches egui as a *Point* wheel and
                        // bypasses laggy eased line-wheel smoothing.
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::PanGesture {
                                device_id,
                                delta: PhysicalPosition {
                                    x: (axes.1 * POINTS_PER_LINE).clamp(-192.0, 192.0),
                                    y: (axes.0 * POINTS_PER_LINE).clamp(-192.0, 192.0),
                                },
                                phase: event::TouchPhase::Moved,
                            },
                        }, self.window_target());
                        self.pdfcraft_trackpad_last = None;
                        self.pdfcraft_trackpad_origin = None;
                        self.pdfcraft_trackpad_spread = None;
                        self.pdfcraft_trackpad_pinching = false;
                        return input_status;
                    }
                    if let (Some(a), Some(b)) = (first_position, second_position) {
                        let mid = PhysicalPosition { x: (a.x+b.x)/2.0, y: (a.y+b.y)/2.0 };
                        let old = self.pdfcraft_trackpad_last.replace(mid);
                        let spread = ((a.x-b.x).powi(2)+(a.y-b.y).powi(2)).sqrt();
                        let previous_spread = self.pdfcraft_trackpad_spread.replace(spread);
                        let (origin, initial_spread) = *self.pdfcraft_trackpad_origin
                            .get_or_insert((mid, spread));
                        let translated = ((mid.x-origin.x).powi(2)+(mid.y-origin.y).powi(2)).sqrt();
                        let expanded = (spread-initial_spread).abs();
                        if !self.pdfcraft_trackpad_pinching
                            && expanded > (initial_spread*0.04).max(12.0)
                            && expanded > 1.2 * translated
                        {
                            self.pdfcraft_trackpad_pinching = true;
                        }
                        if let Some(position) = self.pdfcraft_trackpad_cursor.or(Some(mid)) {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                        }
                        if motion_event.action() == MotionAction::Move {
                            if self.pdfcraft_trackpad_pinching {
                                if let Some(previous) = previous_spread.filter(|v| *v > 0.0) {
                                    if spread > 0.0 {
                                        callback(event::Event::WindowEvent {
                                            window_id,
                                            event: event::WindowEvent::PinchGesture {
                                                device_id,
                                                delta: (spread/previous).ln().clamp(-0.06, 0.06),
                                                phase: event::TouchPhase::Moved,
                                            },
                                        }, self.window_target());
                                    }
                                }
                            } else if let Some(last) = old {
                                let delta = PhysicalPosition {
                                    x: (mid.x-last.x).clamp(-160.0, 160.0),
                                    y: (mid.y-last.y).clamp(-160.0, 160.0),
                                };
                                if delta.x != 0.0 || delta.y != 0.0 {
                                    callback(event::Event::WindowEvent {
                                        window_id,
                                        event: event::WindowEvent::PanGesture {
                                            device_id,
                                            delta: PhysicalPosition { x: delta.x as f32, y: delta.y as f32 },
                                            phase: event::TouchPhase::Moved,
                                        },
                                    }, self.window_target());
                                }
                            }
                        }
                        return input_status; // Never select PDF text during a trackpad gesture.
                    } else {
                        self.pdfcraft_trackpad_last = None;
                        self.pdfcraft_trackpad_origin = None;
                        self.pdfcraft_trackpad_spread = None;
                        self.pdfcraft_trackpad_pinching = false;
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
    assert marker in source and "PDFCRAFT_ANDROID_PRECISE_TRACKPAD_SCROLL" in source
    return source
