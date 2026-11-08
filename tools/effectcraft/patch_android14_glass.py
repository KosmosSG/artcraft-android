#!/usr/bin/env python3
"""EffectCraft-only Android.14 touchscreen two-finger gesture recognizer.

Adapted conceptually from MostafaXS1/artcraft-android's winit Android gesture
implementation. Keep the successful Android.13 Mouse/Finger Smart Touch path
untouched. Installed after app-private native diagnostic so all events log
before gesture routing. Only matches Source::Touchscreen + ToolType::Finger.
"""
from pathlib import Path

ANCHOR = """                match motion_event.action() {
                    // Hover:"""

INSERT = r'''                // Android.14: real touchscreen two-finger gestures.
                // The upstream MostafaXS1 Android fork recognises pan vs pinch
                // inside a deadzone and cancels the initial finger press, so
                // egui cannot select a box when finger two lands. Replicate
                // only that touchscreen rule; never touch our working trackpad,
                // physical mouse, stylus, keyboard or actual click dispatch.
                if matches!(motion_event.source(), Source::Touchscreen)
                    && tool_type == ToolType::Finger
                    && !pointer_class
                {
                    #[derive(Clone)]
                    struct Ec14Glass {
                        first: Option<(i32, PhysicalPosition<f64>)>,
                        multi: bool,
                        origin: Option<(f64, f64, f64)>,
                        previous: Option<(f64, f64, f64)>,
                        // 0 undecided; 1 pan; 2 pinch.
                        mode: u8,
                    }
                    impl Default for Ec14Glass {
                        fn default() -> Self {
                            Self {
                                first: None, multi: false, origin: None,
                                previous: None, mode: 0,
                            }
                        }
                    }
                    std::thread_local! {
                        static EC14_GLASS: std::cell::RefCell<Ec14Glass> =
                            std::cell::RefCell::new(Ec14Glass::default());
                    }
                    let action = motion_event.action();
                    match action {
                        MotionAction::Down => {
                            let first = if motion_event.pointer_count() == 1 {
                                let pointer = motion_event.pointer_at_index(0);
                                Some((pointer.pointer_id(),
                                    PhysicalPosition {
                                        x: pointer.x() as f64,
                                        y: pointer.y() as f64,
                                    }))
                            } else { None };
                            EC14_GLASS.with(|last| {
                                let mut state = last.borrow_mut();
                                *state = Ec14Glass::default();
                                state.first = first;
                            });
                            // Single-finger taps, drags, stylus and typing unchanged.
                        },
                        MotionAction::PointerDown if motion_event.pointer_count() >= 2 => {
                            let a = motion_event.pointer_at_index(0);
                            let b = motion_event.pointer_at_index(1);
                            let center = ((a.x() as f64 + b.x() as f64) * 0.5,
                                          (a.y() as f64 + b.y() as f64) * 0.5);
                            let spread = ((a.x() as f64 - b.x() as f64).powi(2)
                                         + (a.y() as f64 - b.y() as f64).powi(2)).sqrt();
                            let first = EC14_GLASS.with(|last| {
                                let mut state = last.borrow_mut();
                                let saved = state.first.take().or_else(|| Some((
                                    a.pointer_id(),
                                    PhysicalPosition {
                                        x: a.x() as f64,
                                        y: a.y() as f64,
                                    }
                                )));
                                state.multi = true;
                                state.origin = Some((center.0, center.1, spread));
                                state.previous = Some((center.0, center.1, spread));
                                state.mode = 0;
                                saved
                            });
                            // Immediately cancel the first finger's already-forwarded
                            // Touch Started so the viewer stops selecting/drawing.
                            if let Some((id, location)) = first {
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::Touch(event::Touch {
                                        device_id,
                                        phase: event::TouchPhase::Cancelled,
                                        location, id: id as u64, force: None,
                                    }),
                                }, self.window_target());
                            }
                            return InputStatus::Handled;
                        },
                        MotionAction::Move if motion_event.pointer_count() >= 2 => {
                            let a = motion_event.pointer_at_index(0);
                            let b = motion_event.pointer_at_index(1);
                            let x = (a.x() as f64 + b.x() as f64) * 0.5;
                            let y = (a.y() as f64 + b.y() as f64) * 0.5;
                            let spread = ((a.x() as f64 - b.x() as f64).powi(2)
                                         + (a.y() as f64 - b.y() as f64).powi(2)).sqrt();
                            // Always mark touchscreen two-finger Move as a gesture;
                            // some devices skip the second PointerDown in a frame.
                            let step = EC14_GLASS.with(|last| {
                                let mut s = last.borrow_mut();
                                if !s.multi {
                                    s.multi = true;
                                    s.mode = 0;
                                    s.origin = Some((x, y, spread));
                                    s.previous = Some((x, y, spread));
                                    return None;
                                }
                                let (ox, oy, od) = s.origin.unwrap_or((x, y, spread));
                                let (px, py, pd) = s.previous.unwrap_or((x, y, spread));
                                let move_from_origin = ((x-ox).powi(2) + (y-oy).powi(2)).sqrt();
                                let spread_change = (spread - od).abs();
                                if s.mode == 0 {
                                    // Same 12px pan / 36px pinch deadzones as fork;
                                    // classification sticks until fingers lift.
                                    if spread_change > 36.0
                                        && spread_change > 1.5 * move_from_origin {
                                        s.mode = 2;
                                    } else if move_from_origin > 12.0 {
                                        s.mode = 1;
                                    }
                                } else if s.mode == 1 && spread_change > 72.0
                                    && spread_change > 1.5 * move_from_origin {
                                    s.mode = 2;
                                }
                                s.previous = Some((x, y, spread));
                                if s.mode == 1 {
                                    Some((1u8, (x-px)*1.5, (y-py)*1.5, 1.0))
                                } else if s.mode == 2 {
                                    // First pinch sample starts at unity to avoid jump.
                                    let scale = if pd > 1.0 {
                                        (spread / pd).clamp(0.75, 1.25)
                                    } else { 1.0 };
                                    Some((2u8, 0.0, 0.0, scale))
                                } else { None }
                            });
                            if let Some((mode, dx, dy, scale)) = step {
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::CursorMoved {
                                        device_id,
                                        position: PhysicalPosition { x, y },
                                    },
                                }, self.window_target());
                                if mode == 1 && dx.is_finite() && dy.is_finite()
                                    && (dx.abs() + dy.abs()) > 0.01 {
                                    callback(event::Event::WindowEvent {
                                        window_id,
                                        event: event::WindowEvent::MouseWheel {
                                            device_id,
                                            delta: event::MouseScrollDelta::PixelDelta(
                                                PhysicalPosition {
                                                    x: dx.clamp(-100.0, 100.0),
                                                    y: dy.clamp(-100.0, 100.0),
                                                }
                                            ),
                                            phase: event::TouchPhase::Moved,
                                        },
                                    }, self.window_target());
                                } else if mode == 2 && scale.is_finite()
                                    && (scale - 1.0).abs() > 0.002 {
                                    callback(event::Event::WindowEvent {
                                        window_id,
                                        event: event::WindowEvent::PinchGesture {
                                            device_id,
                                            delta: scale.ln(), // winit/eframe zoom factor
                                            phase: event::TouchPhase::Moved,
                                        },
                                    }, self.window_target());
                                }
                            }
                            return InputStatus::Handled;
                        },
                        MotionAction::PointerUp | MotionAction::Up
                        | MotionAction::Cancel => {
                            let was_multi = EC14_GLASS.with(|last| {
                                let mut s = last.borrow_mut();
                                let multi = s.multi;
                                if action == MotionAction::Up
                                    || action == MotionAction::Cancel {
                                    *s = Ec14Glass::default();
                                }
                                multi
                            });
                            if was_multi {
                                // The first touch was already cancelled when finger
                                // two landed, so do NOT send a stray touch release.
                                return InputStatus::Handled;
                            }
                        },
                        MotionAction::Move => {
                            // After the second finger lifts, consume residual moves
                            // until all contacts are gone (the first touch was cancelled).
                            let was_multi = EC14_GLASS.with(|last| last.borrow().multi);
                            if was_multi { return InputStatus::Handled; }
                        },
                        _ => {},
                    }
                }
                match motion_event.action() {
                    // Hover:'''

def apply(root: Path):
    path = root / "src/platform_impl/android/mod.rs"
    original = path.read_text(encoding="utf-8")
    if "EC14_GLASS" in original:
        raise RuntimeError("STOP: Android.14 glass patch already applied")
    if original.count(ANCHOR) != 1 or "EC13_PAD_CONTACT" not in original:
        raise RuntimeError("STOP: missing Android.13 working gesture bridge")
    for fragment in ("MotionAction::Move if pointer_class",
                     "MotionAction::Scroll => {", "Axis::__Unknown(51)",
                     "EC11 time_ms=", "MouseInput", "ImeResetCompleted"):
        if fragment not in original:
            raise RuntimeError("STOP: Android.14 baseline drift: " + fragment)
    path.write_text(original.replace(ANCHOR, INSERT, 1), encoding="utf-8")
    print("PASS: Android.14 glass two-contact pan/pinch guards staged; trackpad unchanged")

if __name__ == "__main__":
    import sys
    if len(sys.argv)!=2:
        raise SystemExit("Usage: patch_android14_glass.py <isolated-winit-root>")
    apply(Path(sys.argv[1]))
