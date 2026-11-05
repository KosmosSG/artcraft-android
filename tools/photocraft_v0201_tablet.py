"""Integrate tablet input and the reference Shortcut Pad with the tested NativeActivity host."""
import argparse
import shutil
from pathlib import Path
from photocraft_v0201_keyboard_diagnostics_overlay import patch
p = argparse.ArgumentParser()
for name in ('upstream','adapter','vendor'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
src=a.adapter/'src'
host=src/'lib.rs'
lib=a.vendor/'android-activity/src'
winit=a.vendor/'winit/src/platform_impl/android/mod.rs'
ui=a.upstream/'crates/ui-egui/src'
files=Path(__file__).parent/'photocraft_tablet'
patch(a.adapter/'Cargo.toml','version = "0.20.1-android.8"','version = "0.20.1-android.10"')
patch(a.adapter/'Cargo.toml','serde_json = { workspace = true }','''serde_json = { workspace = true }
serde = { workspace = true }
craft-ui = { workspace = true }
photocraft-format = { workspace = true }''')
shutil.copytree(files/'pad',src/'shortcut_pad',dirs_exist_ok=True)
(src/'shortcut_pad.rs').write_text((src/'shortcut_pad/mod.rs').read_text())
(src/'shortcut_pad/mod.rs').unlink()
shutil.copyfile(files/'pen_input.rs',src/'pen_input.rs')
shutil.copyfile(files/'native_pen.rs',lib/'pc_pen.rs')
with (lib/'lib.rs').open('a') as f:
    f.write('\n#[cfg(feature = "native-activity")]\npub mod pc_pen;\n')
patch(lib/'native_activity/mod.rs','                let ptr = m.ptr().as_ptr();','''                let ptr = m.ptr().as_ptr();
                unsafe { crate::pc_pen::observe(ptr); }''')
patch(winit,'                                let location =\n                                    PhysicalPosition { x: pointer.x() as _, y: pointer.y() as _ };','''                                if matches!(pointer.tool_type(), ToolType::Stylus | ToolType::Eraser | ToolType::Palm) {
                                    continue; // Copied with full motion history into the native pen queue.
                                }
                                let mut phase = phase;
                                if pointer.tool_type() == ToolType::Finger {
                                    match android_activity::pc_pen::finger(motion_event.device_id(),pointer.pointer_id(),
                                        pointer.x(),pointer.y(),phase==event::TouchPhase::Started,
                                        matches!(phase,event::TouchPhase::Ended|event::TouchPhase::Cancelled)) {
                                        1 => continue,
                                        2 => phase=event::TouchPhase::Cancelled,
                                        _ => {}
                                    }
                                }
                                let location =
                                    PhysicalPosition { x: pointer.x() as _, y: pointer.y() as _ };''')
patch(host,'mod shortcut_pad;', 'mod shortcut_pad;\nmod pen_input;')
patch(host,'    shortcut_pad: shortcut_pad::ShortcutPad,','    shortcut_pad: shortcut_pad::ShortcutPad,\n    pen_input: pen_input::PenInput,')
patch(host,'                shortcut_pad: shortcut_pad::ShortcutPad::new','                pen_input: Default::default(),\n                shortcut_pad: shortcut_pad::ShortcutPad::new')
patch(host,'    android_activity::photocraft_input_owner(0);','    android_activity::pc_pen::reset();\n    android_activity::photocraft_input_owner(0);')
patch(host,'        self.shortcut_pad.inject_controls(raw);','        self.pen_input.apply(&mut self.inner, ctx, raw, self.modifiers);')
patch(host,'        apply_android_modifiers(&mut self.modifiers, raw);','        self.shortcut_pad.input(ctx,raw);\n        apply_android_modifiers(&mut self.modifiers, raw);')
patch(host,'        self.canvas_gesture.apply(&mut self.inner);','''        self.canvas_gesture.apply(&mut self.inner);
        self.shortcut_pad.run_pending(&mut self.inner,ctx);
        if self.shortcut_pad.take_keyboard_tap() {
            if self.shortcut_pad.keyboard_on { let _=self.bridge.hide_native_keyboard(); }
            else { let _=self.bridge.show_native_keyboard(); }
            self.shortcut_pad.keyboard_on = !self.shortcut_pad.keyboard_on;
        }''')
patch(host,'            13..=16 => {','            19 => self.shortcut_pad.open_settings(),\n            13..=16 => {')
patch(ui/'panels/brand.rs','                    action(ui, "Dock Right", 12);','                    action(ui, "Dock Right", 12);\n                    action(ui, "Shortcut Pad Settings…", 19);')
patch(ui/'menus/items.rs','            ("window.artcraft.shortcutPad.toggle",','            ("window.artcraft.shortcutPad.settings", "Shortcut Pad Settings…", None),\n            ("window.artcraft.shortcutPad.toggle",')
patch(ui/'menus/invoke.rs','            "window.artcraft.shortcutPad.toggle" =>','            "window.artcraft.shortcutPad.settings" => super::artcraft_queue_pc_menu_action(19),\n            "window.artcraft.shortcutPad.toggle" =>')
patch(winit,'                match motion_event.action() {\n                    // Hover:', '''                if motion_event.pointers().any(|p| matches!(p.tool_type(),ToolType::Stylus|ToolType::Eraser)) {
                    self.window_target.p.redraw_requester.request_redraw();
                }
                match motion_event.action() {
                    // Hover:''')
gest=src/'canvas_gesture.rs'
patch(host,'self.canvas_gesture.route(ctx, raw);','self.canvas_gesture.route(ctx, raw, self.shortcut_pad.finger_mode());')
patch(gest,'ctx: &egui::Context, raw: &mut RawInput)', 'ctx: &egui::Context, raw: &mut RawInput, mode: crate::shortcut_pad::config::FingerMode)')
patch(gest,'        let mut gesture = self.previous.is_some();','''        use crate::shortcut_pad::config::FingerMode;
        let mut gesture = self.previous.is_some() || (mode != FingerMode::Draw && !self.fingers.is_empty());''')
patch(gest,'                            self.fingers.push(Finger { id, pos });','''                            self.fingers.push(Finger { id, pos });
                            gesture |= mode != FingerMode::Draw;''')
patch(gest,'                        if let Some(f) = self.fingers.iter_mut().find(|f| f.id == id) {','''                        let single = self.fingers.len() == 1;
                        if let Some(f) = self.fingers.iter_mut().find(|f| f.id == id) {
                            if single && mode == FingerMode::Pan {
                                self.moves.push(ViewMove { from:f.pos, to:pos, scale:1.0, degrees:0.0 });
                            }''')

patch(host, "        self.inner.ui(ui, _frame);", "        self.inner.ui(ui, _frame);\n        self.pen_input.paint_hover(ui.ctx());")
