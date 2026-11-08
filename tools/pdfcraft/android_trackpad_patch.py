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
    swap("        let redraw_flag = SharedFlag::new();",
         """        // PDFCRAFT_ANDROID_GESTURE_AXES_34: request the Android 14+
        // hardware trackpad scroll-distance axes, as well as legacy
        // mouse wheel axes. NativeActivity may expose them without opt-in,
        // while GameActivity requires explicit enablement.
        android_app.enable_motion_axis(Axis::Vscroll);
        android_app.enable_motion_axis(Axis::Hscroll);
        android_app.enable_motion_axis(Axis::from(50u32));
        android_app.enable_motion_axis(Axis::from(51u32));
        let redraw_flag = SharedFlag::new();""")
    swap("    pdfcraft_touch_held: bool,",
         """    pdfcraft_touch_held: bool,
    // PDFCRAFT_ANDROID_TRACKPAD_SCROLL
    pdfcraft_trackpad_last: Option<PhysicalPosition<f64>>,
    pdfcraft_trackpad_cursor: Option<PhysicalPosition<f64>>,
    // PDFCRAFT_ANDROID_TRACKPAD_PINCH
    pdfcraft_trackpad_origin: Option<(PhysicalPosition<f64>, f64)>,
    pdfcraft_trackpad_spread: Option<f64>,
    pdfcraft_trackpad_pinching: bool,
    // PDFCRAFT_ANDROID_TRACKPAD_PHASED_SCROLL
    pdfcraft_trackpad_pan_active: bool,
    pdfcraft_precision_stream: crate::pdfcraft_input::PrecisionStream,""")
    swap("            pdfcraft_touch_held: false,",
         """            pdfcraft_touch_held: false,
            pdfcraft_trackpad_last: None,
            pdfcraft_trackpad_cursor: None,
            pdfcraft_trackpad_origin: None,
            pdfcraft_trackpad_spread: None,
            pdfcraft_trackpad_pinching: false,
            pdfcraft_trackpad_pan_active: false,
            pdfcraft_precision_stream: Default::default(),""")
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
                if (touchpad_source || mouse_source) && motion_event.button_state().0 == 0 {
                    // PDFCRAFT_ANDROID_PRECISE_TRACKPAD_SCROLL: no per-move allocation.
                    let mut pointers = motion_event.pointers();
                    let first = pointers.next();
                    let second = pointers.next();
                    let first_position = first.as_ref().map(pointer_position);
                    let second_position = second.as_ref().map(pointer_position);
                    let point_count = motion_event.pointer_count();
                    // PDFCRAFT_ANDROID_TRACKPAD_END: native PDF gestures need
                    // a true End phase for PDFCraft's fling/momentum model.
                    if self.pdfcraft_trackpad_pan_active && matches!(
                        motion_event.action(),
                        MotionAction::Up | MotionAction::PointerUp | MotionAction::Cancel
                    ) {
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::PanGesture {
                                device_id,
                                delta: PhysicalPosition { x: 0.0, y: 0.0 },
                                phase: if motion_event.action() == MotionAction::Cancel { event::TouchPhase::Cancelled } else { event::TouchPhase::Ended },
                            },
                        }, self.window_target());
                        self.pdfcraft_trackpad_pan_active = false;
                    }
                    // PDFCRAFT_ANDROID_TRACKPAD_NO_SIDEBAR_CLICK:
                    // A finger-down on a trackpad is not a mouse-button click.
                    // Suppress it before the generic pointer-class path can
                    // press a tool in the left sidebar. Actual mouse clicks
                    // retain their normal button-state dispatch below.
                    // PDFCRAFT_ANDROID_HONOR_FINGER_MOUSE: HONOR trackpads
                    // can classify two-finger contacts as SOURCE_MOUSE with
                    // ToolType::Finger. Do not let either contact click a
                    // sidebar tool. A real mouse reports ToolType::Mouse and
                    // retains all buttons.
                    // PDFCRAFT_ANDROID4_TRACKPAD_NO_BUTTON_NO_CLICK:
                    // MagicOS may label *both* trackpad contacts as Mouse,
                    // not Finger. A pointer down with no pressed button is
                    // a trackpad contact, never a sidebar/tool click.
                    // Preserve real mouse clicks (button_state != 0).
                    if matches!(motion_event.action(),
                            MotionAction::Down | MotionAction::PointerDown)
                    {
                        self.pdfcraft_trackpad_last = None;
                        return input_status;
                    }
                    if (touchpad_source || self.pdfcraft_trackpad_origin.is_some() || self.pdfcraft_trackpad_pan_active)
                        && matches!(motion_event.action(), MotionAction::Down | MotionAction::Up
                        | MotionAction::PointerUp | MotionAction::Cancel) {
                        self.pdfcraft_precision_stream.reset();
                        self.pdfcraft_trackpad_last = None;
                        self.pdfcraft_trackpad_origin = None;
                        self.pdfcraft_trackpad_spread = None;
                        self.pdfcraft_trackpad_pinching = false;
                        if motion_event.action() != MotionAction::Down { return input_status; }
                    }
                    if matches!(motion_event.action(),
                        MotionAction::HoverMove | MotionAction::HoverEnter | MotionAction::Move
                    ) && point_count == 1 {
                        if mouse_source || self.pdfcraft_trackpad_cursor.is_none() {
                            self.pdfcraft_trackpad_cursor = first_position;
                        }
                    }
                    // PDFCRAFT_ANDROID_BATCHED_SCROLL: Android axes 50/51 are
                    // relative PER SAMPLE. The latest sample excludes motion history.
                    let mut batch = crate::pdfcraft_input::ScrollBatch::default();
                    if matches!(motion_event.action(), MotionAction::Move | MotionAction::Scroll) {
                        let mut history_count = 0;
                        for historical in motion_event.pdfcraft_history() {
                            history_count += 1;
                            if let Some(p) = historical.pointers().next() {
                                batch.push([p.axis_value(9i32.into()), p.axis_value(10i32.into()),
                                    p.axis_value(50i32.into()), p.axis_value(51i32.into())], true);
                            }
                        }
                        crate::pdfcraft_input::history(history_count, batch.historical_nonzero);
                    }
                    if let Some(p) = first.as_ref() {
                        batch.push([p.axis_value(Axis::Vscroll), p.axis_value(Axis::Hscroll),
                            p.axis_value(Axis::from(50u32)), p.axis_value(Axis::from(51u32))], false);
                    }
                    let combined = batch.axes();
                    let axes = (combined[0], combined[1]);
                    let gesture_axes = (combined[2], combined[3]);
                    let has_scroll_axes = axes.0 != 0.0 || axes.1 != 0.0;
                    let fractional_scroll = batch.fractional;
                    let has_gesture_scroll = gesture_axes.0.is_finite()
                        && gesture_axes.1.is_finite()
                        && (gesture_axes.0 != 0.0 || gesture_axes.1 != 0.0);
                    // Some HONOR two-finger trackpads report fractional
                    // SOURCE_MOUSE VSCROLL/HSCROLL, not moving touch pointers.
                    // Coarse physical mouse notches still use stock winit wheels.
                    // PDFCRAFT_ANDROID_STICKY_PRECISION: integer/zero samples within
                    // the same stream must not enter egui's accelerated Line path.
                    let evidence = touchpad_source || has_gesture_scroll
                        || (mouse_source && (tool_type == ToolType::Finger || fractional_scroll || point_count >= 2));
                    let precision_trackpad = self.pdfcraft_precision_stream.classify(
                        motion_event.device_id(), motion_event.event_time(), evidence);
                    crate::pdfcraft_input::record(motion_event.source().into(),
                        motion_event.action().into(), motion_event.event_time(),
                        has_scroll_axes || has_gesture_scroll);
                    let axis_action = matches!(motion_event.action(),
                        MotionAction::Scroll | MotionAction::Move);
                    if precision_trackpad && (has_scroll_axes || has_gesture_scroll) && axis_action {
                        // Android scroll-distance axes are physical display
                        // pixels, with the opposite sign from winit PanGesture.
                        // Chrome's Android bridge likewise negates these axes.
                        let delta = if has_gesture_scroll {
                            PhysicalPosition {
                                x: -gesture_axes.0,
                                y: -gesture_axes.1,
                            }
                        } else {
                            PhysicalPosition {
                                x: axes.1 * POINTS_PER_LINE,
                                y: axes.0 * POINTS_PER_LINE,
                            }
                        };
                        if !delta.x.is_finite() || !delta.y.is_finite() { return input_status; }
                        let pos = self.pdfcraft_trackpad_cursor.or(first_position);
                        if let Some(position) = pos {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                        }
                        // Axis scroll streams may already contain Android momentum.
                        // Do not invent Start/End (and an additional client fling).
                        // PanGesture reaches egui as a *Point* wheel and
                        // bypasses laggy eased line-wheel smoothing.
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::PanGesture {
                                device_id,
                                delta,
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
                        // PDFCRAFT_ANDROID_TRACKPAD_SCROLL_LOCK:
                        // A parallel swipe inevitably changes the apparent
                        // separation a little as each pointer arrives on a
                        // different input frame. The earlier permissive 12 px
                        // threshold accidentally latched Scroll -> Pinch,
                        // repeatedly zooming and cancelling PDFCraft's fling.
                        // Commit to a real pinch only BEFORE a scroll starts,
                        // with strong relative separation evidence.
                        if !self.pdfcraft_trackpad_pinching
                            && !self.pdfcraft_trackpad_pan_active
                            && expanded > (initial_spread*0.12).max(30.0)
                            && expanded > 2.5 * translated
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
                                    x: mid.x-last.x,
                                    y: mid.y-last.y,
                                };
                                if delta.x.is_finite() && delta.y.is_finite()
                                    && (delta.x != 0.0 || delta.y != 0.0) {
                                    if !self.pdfcraft_trackpad_pan_active && translated > 3.0 {
                                        self.pdfcraft_trackpad_pan_active = true;
                                        callback(event::Event::WindowEvent {
                                            window_id,
                                            event: event::WindowEvent::PanGesture {
                                                device_id,
                                                delta: PhysicalPosition { x: 0.0, y: 0.0 },
                                                phase: event::TouchPhase::Started,
                                            },
                                        }, self.window_target());
                                    }
                                    if self.pdfcraft_trackpad_pan_active {
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
                        }
                        return input_status; // Never select PDF text during a trackpad gesture.
                    } else {
                        // Zero-axis/hover samples are not finger-lift signals.
                        // Preserve a raw two-pointer gesture until its real terminal event.
                        if self.pdfcraft_trackpad_pan_active { return input_status; }
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
    assert "PDFCRAFT_ANDROID_HONOR_FINGER_MOUSE" in source
    assert "PDFCRAFT_ANDROID_TRACKPAD_SCROLL_LOCK" in source
    assert "PDFCRAFT_ANDROID_TRACKPAD_PHASED_SCROLL" in source
    assert "PDFCRAFT_ANDROID4_TRACKPAD_NO_BUTTON_NO_CLICK" in source
    assert "phase: event::TouchPhase::Started" in source
    assert "else { event::TouchPhase::Ended }" in source
    assert "PDFCRAFT_ANDROID_GESTURE_AXES_34" in source
    assert "Axis::from(50u32)" in source and "Axis::from(51u32)" in source
    return source
