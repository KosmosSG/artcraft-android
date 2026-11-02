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
    pdfcraft_trackpad_last: Option<PhysicalPosition<f64>>,""")
    swap("            pdfcraft_touch_held: false,",
         """            pdfcraft_touch_held: false,
            pdfcraft_trackpad_last: None,""")
    swap("""                match motion_event.action() {
                    // Hover: the cursor moves without any button held.""",
         """                // On an Android trackpad, two fingers can arrive as normal
                // Move events with two pointers instead of AXIS_VSCROLL.
                // Handle those before the general mouse-class hover branch.
                if motion_event.source() == Source::Touchpad {
                    let pointers: Vec<_> = motion_event.pointers().map(|p| pointer_position(&p)).collect();
                    if pointers.len() >= 2 {
                        let a = pointers[0]; let b = pointers[1];
                        let mid = PhysicalPosition { x: (a.x+b.x)/2.0, y: (a.y+b.y)/2.0 };
                        let old = self.pdfcraft_trackpad_last.replace(mid);
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::CursorMoved { device_id, position: mid },
                        }, self.window_target());
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
                        // Suppress pointer-class down/up: two-finger touchpad
                        // movement must NEVER start emulated text selection.
                        return input_status;
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
                        if let Some(position) = motion_event.pointers().next()
                            .map(|pointer| pointer_position(&pointer))
                        {
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                        }
                        let (vertical, horizontal) = motion_event""")
    assert marker in source
    return source
