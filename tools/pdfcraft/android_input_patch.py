"""Guarded PDFCraft-only Android keyboard metadata + two-finger canvas gestures.

Apply only to the vendored winit v0.30 Android backend in the *ephemeral*
PDFCraft staging source. Physical keyboard shortcuts must receive a proper
ModifiersChanged event; on HONOR/Android, some Ctrl combinations arrive only
in the KeyEvent meta_state with no separate Ctrl key event. Two-finger glass
drag must be MouseWheel rather than two independent text-selection touches.
"""
from __future__ import annotations

from pathlib import Path


def patch(android: str) -> str:
    marker = "pdfcraft_android_gesture"
    if marker in android:
        for required in ("fn pdfcraft_android_gesture", "pdfcraft_key_mods", "ModifiersChanged(mods.into())"):
            if required not in android:
                raise ValueError("Incomplete PDFCraft Android input patch")
        return android

    def swap(a: str, b: str):
        nonlocal android
        n = android.count(a)
        if n != 1:
            raise ValueError(f"PDFCraft pinned Android winit changed: {n} occurrences of {a[:90]!r}")
        android = android.replace(a, b, 1)

    swap("use crate::error::EventLoopError;",
         "use crate::error::EventLoopError;\nuse crate::keyboard::ModifiersState;")
    swap("const POINTS_PER_LINE: f32 = 40.0;",
         """const POINTS_PER_LINE: f32 = 40.0;

// The PDF editor retains one-finger tap/drag for selecting and editing PDF text.
// Two fingers take over only after the second finger touches the glass.
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
enum PdfTouchMode { Pending, Scroll, Pinch }
""")
    swap("    combining_accent: Option<char>,",
         """    combining_accent: Option<char>,
    pdfcraft_key_mods: ModifiersState,
    pdfcraft_touch_first: Option<(u64, PhysicalPosition<f64>)>,
    pdfcraft_touch_origin: Option<(PhysicalPosition<f64>, f64)>,
    pdfcraft_touch_last: Option<(PhysicalPosition<f64>, f64)>,
    pdfcraft_touch_mode: PdfTouchMode,
    pdfcraft_touch_held: bool,""")
    swap("            combining_accent: None,",
         """            combining_accent: None,
            pdfcraft_key_mods: ModifiersState::empty(),
            pdfcraft_touch_first: None,
            pdfcraft_touch_origin: None,
            pdfcraft_touch_last: None,
            pdfcraft_touch_mode: PdfTouchMode::Pending,
            pdfcraft_touch_held: false,""")

    hook = "    fn handle_input_event<F>(\n"
    if android.count(hook) != 1:
        raise ValueError("Cannot locate event handler method")
    fn = """    // Android KeyEvent.meta_state is authoritative for physical keyboard chords
    // (META_CTRL_ON 0x1000, SHIFT_ON 0x1, ALT_ON 0x2, META_ON 0x10000).
    // Do not assume Android emits a separate Ctrl-down event before Ctrl+S.
    fn pdfcraft_android_key_modifiers<F>(
        &mut self,
        key: &android_activity::input::KeyEvent<'_>,
        callback: &mut F,
    ) where F: FnMut(event::Event<T>, &RootAEL) {
        let meta = key.meta_state();
        let mut mods = ModifiersState::empty();
        mods.set(ModifiersState::SHIFT, meta.shift_on() || meta.shift_left_on() || meta.shift_right_on());
        mods.set(ModifiersState::ALT, meta.alt_on() || meta.alt_left_on() || meta.alt_right_on());
        mods.set(ModifiersState::CONTROL, meta.ctrl_on() || meta.ctrl_left_on() || meta.ctrl_right_on());
        mods.set(ModifiersState::SUPER, meta.meta_on() || meta.meta_left_on() || meta.meta_right_on());
        // A modifier's own Up event may report the *old* meta bits; the key
        // event's action wins for that modifier alone.
        let down = key.action() == KeyAction::Down;
        match key.key_code() {
            Keycode::CtrlLeft | Keycode::CtrlRight => mods.set(ModifiersState::CONTROL, down),
            Keycode::ShiftLeft | Keycode::ShiftRight => mods.set(ModifiersState::SHIFT, down),
            Keycode::AltLeft | Keycode::AltRight => mods.set(ModifiersState::ALT, down),
            Keycode::MetaLeft | Keycode::MetaRight => mods.set(ModifiersState::SUPER, down),
            _ => {}
        }
        if mods != self.pdfcraft_key_mods {
            self.pdfcraft_key_mods = mods;
            callback(event::Event::WindowEvent {
                window_id: window::WindowId(WindowId),
                event: event::WindowEvent::ModifiersChanged(mods.into()),
            }, self.window_target());
        }
    }

    // Return true if a glass touch belongs to the two-finger pan/pinch and
    // MUST NOT be forwarded to PDF text selection, annotation or widgets.
    fn pdfcraft_android_gesture<F>(
        &mut self,
        motion: &android_activity::input::MotionEvent<'_>,
        window_id: window::WindowId,
        device_id: event::DeviceId,
        callback: &mut F,
    ) -> bool where F: FnMut(event::Event<T>, &RootAEL) {
        let count = motion.pointer_count();
        let centroid_spread = || -> Option<(PhysicalPosition<f64>, f64)> {
            if count != 2 { return None; }
            let mut p = motion.pointers().map(|p| pointer_position(&p));
            let a = p.next()?;
            let b = p.next()?;
            let mid = PhysicalPosition { x: (a.x+b.x)/2.0, y: (a.y+b.y)/2.0 };
            let spread = ((a.x-b.x).powi(2)+(a.y-b.y).powi(2)).sqrt();
            Some((mid, spread))
        };
        match motion.action() {
            MotionAction::Down => {
                if count == 1 {
                    let p = motion.pointer_at_index(0);
                    self.pdfcraft_touch_first = Some((p.pointer_id() as u64, pointer_position(&p)));
                    self.pdfcraft_touch_held = false;
                    self.pdfcraft_touch_origin = None;
                    self.pdfcraft_touch_last = None;
                    self.pdfcraft_touch_mode = PdfTouchMode::Pending;
                }
                false
            }
            MotionAction::PointerDown if count >= 2 => {
                if !self.pdfcraft_touch_held {
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
                self.pdfcraft_touch_held = true;
                self.pdfcraft_touch_origin = centroid_spread();
                self.pdfcraft_touch_last = self.pdfcraft_touch_origin;
                if let Some((mid, _)) = self.pdfcraft_touch_origin {
                    // egui-winit's TouchPhase::Cancelled sends PointerGone;
                    // restoring a hover point over the PDF is required for
                    // rect_contains_pointer() in PDFCraft's zoom/scroll path.
                    callback(event::Event::WindowEvent {
                        window_id,
                        event: event::WindowEvent::CursorMoved { device_id, position: mid },
                    }, self.window_target());
                }
                self.pdfcraft_touch_mode = PdfTouchMode::Pending;
                true
            }
            MotionAction::Move if self.pdfcraft_touch_held => {
                if let Some((mid, spread)) = centroid_spread() {
                    // Keep the active pointer over the PDF. Wheel input and
                    // pinch zoom are ignored by the canvas without a pointer.
                    callback(event::Event::WindowEvent {
                        window_id,
                        event: event::WindowEvent::CursorMoved { device_id, position: mid },
                    }, self.window_target());
                    if let (Some((origin, original_spread)), Some((last, last_spread))) =
                        (self.pdfcraft_touch_origin, self.pdfcraft_touch_last)
                    {
                        let travelled = ((mid.x-origin.x).powi(2) + (mid.y-origin.y).powi(2)).sqrt();
                        let expansion = (spread-original_spread).abs();
                        if self.pdfcraft_touch_mode == PdfTouchMode::Pending {
                            if expansion > 36.0 && expansion > 1.5 * travelled {
                                self.pdfcraft_touch_mode = PdfTouchMode::Pinch;
                            } else if travelled > 12.0 {
                                self.pdfcraft_touch_mode = PdfTouchMode::Scroll;
                            }
                        }
                        match self.pdfcraft_touch_mode {
                            PdfTouchMode::Scroll => {
                                // Physical pixel delta follows fingers, regardless of
                                // Select, Text, Comment or Hand tool.
                                let dx = (mid.x-last.x)*1.5;
                                let dy = (mid.y-last.y)*1.5;
                                if dx != 0.0 || dy != 0.0 {
                                    callback(event::Event::WindowEvent {
                                        window_id,
                                        event: event::WindowEvent::MouseWheel {
                                            device_id,
                                            delta: event::MouseScrollDelta::PixelDelta(
                                                PhysicalPosition { x: dx, y: dy }
                                            ),
                                            phase: event::TouchPhase::Moved,
                                        },
                                    }, self.window_target());
                                }
                            }
                            PdfTouchMode::Pinch if last_spread > 0.0 && spread > 0.0 => {
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::PinchGesture {
                                        device_id, delta: (spread/last_spread).ln(),
                                        phase: event::TouchPhase::Moved,
                                    },
                                }, self.window_target());
                            }
                            _ => {}
                        }
                    }
                    self.pdfcraft_touch_last = Some((mid, spread));
                }
                true
            }
            MotionAction::PointerUp if self.pdfcraft_touch_held => {
                // Suppress up for a canceled touch: do not accidentally select or
                // reactivate the last remaining finger as a document drag.
                self.pdfcraft_touch_origin = None;
                self.pdfcraft_touch_last = None;
                true
            }
            MotionAction::Up | MotionAction::Cancel if self.pdfcraft_touch_held => {
                self.pdfcraft_touch_held = false;
                self.pdfcraft_touch_first = None;
                self.pdfcraft_touch_origin = None;
                self.pdfcraft_touch_last = None;
                self.pdfcraft_touch_mode = PdfTouchMode::Pending;
                true
            }
            MotionAction::Up | MotionAction::Cancel => {
                self.pdfcraft_touch_first = None;
                false
            }
            MotionAction::Move if count != 1 => true,
            _ => self.pdfcraft_touch_held,
        }
    }

"""
    android = android.replace(hook, fn + hook, 1)
    swap('                match motion_event.action() {\n',
         '''                // Only physical fingers take the new gesture path. A stylus
                // still edits/inks, while mouse/trackpad remain untouched.
                if !pointer_class && (tool_type == ToolType::Finger
                    || (motion_event.source() == Source::Touchscreen
                        && tool_type == ToolType::Unknown))
                    && self.pdfcraft_android_gesture(
                        motion_event, window_id, device_id, callback,
                    )
                {
                    return input_status;
                }

                match motion_event.action() {
''')
    swap('            InputEvent::KeyEvent(key) => {\n                match key.key_code() {',
         '''            InputEvent::KeyEvent(key) => {
                self.pdfcraft_android_key_modifiers(key, callback);
                match key.key_code() {''')
    for check in ("fn pdfcraft_android_gesture", "pdfcraft_android_key_modifiers", "ModifiersChanged(mods.into())"):
        assert check in android
    return android


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1])
    path.write_text(patch(path.read_text()))
    print("PASS: PDFCraft Android two-finger scroll and native key modifier metadata")
