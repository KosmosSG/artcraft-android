#!/usr/bin/env python3
"""LightCraft-only Android hover input backport for pinned storytold/winit.
Fails closed if upstream changes; does not replace existing IME/touch backend.
"""
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text(encoding="utf-8")
anchor='''                let phase = match motion_event.action() {
                    MotionAction::Down | MotionAction::PointerDown => {'''
if s.count(anchor)!=1 or s.count("None // TODO mouse events")!=1:
    raise SystemExit("STOP: pinned LightCraft winit Android hover source drift")
patch='''                // LightCraft Android: translate hardware mouse/trackpad/stylus
                // hover motion into winit cursor events. Previously ignored
                // (the existing match ends in TODO mouse events), leaving egui
                // menu items unable to react to pointer hover.
                match motion_event.action() {
                    MotionAction::HoverEnter | MotionAction::HoverMove | MotionAction::HoverExit => {
                        if let Some(pointer) = motion_event.pointers().next() {
                            let position = PhysicalPosition {
                                x: pointer.x() as f64,
                                y: pointer.y() as f64,
                            };
                            if motion_event.action() == MotionAction::HoverEnter {
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::CursorEntered { device_id },
                                }, self.window_target());
                            }
                            callback(event::Event::WindowEvent {
                                window_id,
                                event: event::WindowEvent::CursorMoved { device_id, position },
                            }, self.window_target());
                            if motion_event.action() == MotionAction::HoverExit {
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::CursorLeft { device_id },
                                }, self.window_target());
                            }
                        }
                        return InputStatus::Handled;
                    }
                    _ => {}
                }

'''
p.write_text(s.replace(anchor,patch+anchor,1),encoding="utf-8")
print("PASS: LightCraft pinned winit Android hover translation added; touch/IME intact")
