#!/usr/bin/env python3
"""EffectCraft Android.13: suppress synthetic finger-mouse presses on HONOR trackpad.

Evidence: exported Android.12 native log has Mouse/Finger Down->Cancel
sequences while two-finger menu scrolling, and scroll axis 51 values in Move
(not Scroll). Run after v020_winit_compat and patch_android_lifecycle, before
patch_android_local_diag. All changes remain in disposable EffectCraft winit.
"""
from pathlib import Path

ANCHOR = """                match motion_event.action() {
                    // Hover:"""
INSERT = r"""                // Android.13 HONOR Smart Touch: gestures arrive as Mouse/Finger
                // rather than Source::Touchpad, with repeated Down->Cancel.
                // Do not expose those provisional Down events as menu clicks.
                // Real BUTTON_PRIMARY presses and Mouse/ToolType::Mouse are
                // untouched; buttonless finger taps synthesize a click on Up.
                std::thread_local! {
                    static EC13_PAD_CONTACT: std::cell::RefCell<
                        Option<(i32, f32, f32, f32, f32, bool)>
                    > = std::cell::RefCell::new(None);
                }
                if matches!(motion_event.source(), Source::Mouse)
                    && tool_type == ToolType::Finger
                    && (motion_event.button_state().0 & 1) == 0
                {
                    let contact = if motion_event.pointer_count() > 0 {
                        let p = motion_event.pointer_at_index(0);
                        Some((p.x(), p.y()))
                    } else { None };
                    match motion_event.action() {
                        MotionAction::Down if motion_event.pointer_count() == 1 => {
                            if let Some((x, y)) = contact {
                                EC13_PAD_CONTACT.with(|last| {
                                    *last.borrow_mut() = Some((
                                        motion_event.device_id(), x, y, x, y, false
                                    ));
                                });
                                // Position must be known to egui to target hovered menu.
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::CursorMoved {
                                        device_id,
                                        position: PhysicalPosition {
                                            x: x as f64, y: y as f64
                                        },
                                    },
                                }, self.window_target());
                            }
                            return InputStatus::Handled;
                        },
                        MotionAction::PointerDown if motion_event.pointer_count() >= 2 => {
                            EC13_PAD_CONTACT.with(|last| *last.borrow_mut() = None);
                            // Existing >=2-finger pan/pinch route handles the event.
                        },
                        MotionAction::Move if motion_event.pointer_count() == 1 => {
                            if let Some((x, y)) = contact {
                                let p = motion_event.pointer_at_index(0);
                                let direct = p.axis_value(Axis::__Unknown(50)).abs() > 0.001
                                    || p.axis_value(Axis::__Unknown(51)).abs() > 0.001
                                    || {
                                        let z = p.axis_value(Axis::__Unknown(52));
                                        z > 0.0 && (z - 1.0).abs() > 0.002
                                    };
                                let delta = EC13_PAD_CONTACT.with(|last| {
                                    let mut state = last.borrow_mut();
                                    let Some((id, x0, y0, last_x, last_y, moved)) = *state else {
                                        return None;
                                    };
                                    if id != motion_event.device_id() {
                                        *state = None;
                                        return None;
                                    }
                                    let dx = x - last_x;
                                    let dy = y - last_y;
                                    *state = Some((id, x0, y0, x, y,
                                        moved || direct || dx.abs()+dy.abs() > 1.0));
                                    Some((dx, dy))
                                });
                                if direct {
                                    // Keep our last point and non-click state.
                                    // The existing axis-50/51/52 route emits wheel/pinch.
                                } else if let Some((dx, dy)) = delta {
                                    // MagicOS can omit axis 51 intermittently.
                                    // Finger-source/zero-button drag is still a
                                    // scroll gesture; no hover or mouse press here.
                                    if dx.is_finite() && dy.is_finite()
                                        && dx.abs()+dy.abs() >= 0.8
                                    {
                                        callback(event::Event::WindowEvent {
                                            window_id,
                                            event: event::WindowEvent::MouseWheel {
                                                device_id,
                                                delta: event::MouseScrollDelta::PixelDelta(
                                                    PhysicalPosition {
                                                        x: dx.clamp(-80.0, 80.0) as f64,
                                                        y: dy.clamp(-80.0, 80.0) as f64,
                                                    },
                                                ),
                                                phase: event::TouchPhase::Moved,
                                            },
                                        }, self.window_target());
                                    }
                                    return InputStatus::Handled;
                                } else {
                                    // Do not turn an unmatched finger drag into
                                    // a mouse-selection event after a Cancel.
                                    return InputStatus::Handled;
                                }
                            }
                        },
                        MotionAction::Up => {
                            let pending = EC13_PAD_CONTACT.with(|last| last.borrow_mut().take());
                            if let (Some((id, x0, y0, _, _, moved)), Some((x, y))) =
                                (pending, contact)
                            {
                                if id == motion_event.device_id()
                                    && !moved
                                    && (x-x0).abs()+(y-y0).abs() < 6.0
                                {
                                    callback(event::Event::WindowEvent {
                                        window_id,
                                        event: event::WindowEvent::CursorMoved {
                                            device_id,
                                            position: PhysicalPosition {
                                                x: x as f64, y: y as f64
                                            },
                                        },
                                    }, self.window_target());
                                    for state in [
                                        event::ElementState::Pressed,
                                        event::ElementState::Released,
                                    ] {
                                        callback(event::Event::WindowEvent {
                                            window_id,
                                            event: event::WindowEvent::MouseInput {
                                                device_id,
                                                state,
                                                button: event::MouseButton::Left,
                                            },
                                        }, self.window_target());
                                    }
                                }
                                return InputStatus::Handled;
                            }
                            // No deferred press: let ordinary button-release pass.
                        },
                        MotionAction::Cancel => {
                            if EC13_PAD_CONTACT.with(|last| last.borrow_mut().take().is_some()) {
                                return InputStatus::Handled;
                            }
                        },
                        _ => {},
                    }
                }
                match motion_event.action() {
                    // Hover:"""

def apply(root: Path):
    file = root / "src/platform_impl/android/mod.rs"
    s = file.read_text(encoding="utf-8")
    if "EC13_PAD_CONTACT" in s:
        raise RuntimeError("STOP: EffectCraft Android.13 trackpad patch already staged")
    if s.count(ANCHOR) != 1:
        raise RuntimeError("STOP: pinned winit input dispatch drift")
    for expected in ("MotionAction::Move if pointer_class",
                     "Axis::__Unknown(51)", "MouseInput", "MotionAction::Cancel"):
        if expected not in s:
            raise RuntimeError("STOP: approved keyboard/pointer/gesture baseline drift: "+expected)
    file.write_text(s.replace(ANCHOR, INSERT, 1), encoding="utf-8")
    print("PASS: EffectCraft Android.13 mouse-finger gesture vs tap classification staged")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_android13_input.py <disposable-winit-root>")
    apply(Path(sys.argv[1]))
