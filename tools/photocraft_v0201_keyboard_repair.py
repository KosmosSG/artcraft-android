#!/usr/bin/env python3
"""Candidate-only keyboard repair, after all earlier compatibility overlays.

Fail closed on changed anchors. Production adapter sources are never edited.
"""
import argparse
from pathlib import Path
from photocraft_v0201_keyboard_diagnostics_overlay import patch, PIN
import subprocess


def section(path, start, end, replacement):
    text = path.read_text()
    assert text.count(start) == text.count(end) == 1, path
    old = text[text.index(start):text.index(end)]
    patch(path, old, replacement)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--upstream', type=Path, required=True)
    cli.add_argument('--adapter', type=Path, required=True)
    opt = cli.parse_args()
    assert subprocess.check_output(['git', '-C', str(opt.upstream), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    host = opt.adapter / 'src/lib.rs'
    act = opt.adapter / 'java/com/artcraft/photocraft/PhotoCraftActivity.java'

    patch(opt.adapter / 'Cargo.toml', 'version = "0.20.1-android.1"', 'version = "0.20.1-android.2"')

    # The Activity retained the original V/T/B-only outer gate even after the
    # inner pcRememberHardwareKey allowlist grew to A-Z.
    section(act, '        int code = event.getKeyCode();\n        int action = event.getAction();\n',
            '        return super.dispatchKeyEvent(event);',
            '        pcRememberHardwareKey(event);\n')
    patch(act, '''                && code != KeyEvent.KEYCODE_ESCAPE
                && code != KeyEvent.KEYCODE_ENTER) return;
''', '''                && code != KeyEvent.KEYCODE_ESCAPE
                && code != KeyEvent.KEYCODE_SHIFT_LEFT && code != KeyEvent.KEYCODE_SHIFT_RIGHT
                && code != KeyEvent.KEYCODE_CTRL_LEFT && code != KeyEvent.KEYCODE_CTRL_RIGHT
                && code != KeyEvent.KEYCODE_ALT_LEFT && code != KeyEvent.KEYCODE_ALT_RIGHT
                && code != KeyEvent.KEYCODE_ENTER) return;
''')

    # Remove the second tool dispatcher. It overwrote custom mappings and
    # bypassed both the upstream modal guard and Shift/group selection policy.
    patch(host, "    artcraft_tool_pending: Option<&'static str>,\n", '')
    patch(host, '                artcraft_tool_pending: None,\n', '')
    section(host, '        if let Some(command) = self.artcraft_tool_pending.take() {\n',
            '    }\n\n    fn ui(&mut self, ui:', '')
    section(host, '                if !modifiers.ctrl && !modifiers.alt && !modifiers.shift\n',
            '        self.canvas_gesture.route(ctx, raw);',
            '            }\n        }\n')

    patch(host, 'if let egui::Event::Key { key, pressed: true, modifiers, .. } = event {\n                if *key == egui::Key::Escape', 'if let egui::Event::Key { key, pressed: true, .. } = event {\n                if *key == egui::Key::Escape')

    # Let the upstream editor process this pass's text before the Escape
    # fallback commits. The old logic-tail fallback could run before ui().
    section(host, '        // On some Android NativeActivity builds the 0.19 IME reset ACK never\n',
            '    }\n\n    fn ui(&mut self, ui:', '')
    patch(host, '        self.inner.ui(ui, _frame);\n', '''        self.inner.ui(ui, _frame);
        if self.artcraft_esc_pending && self.inner.ui.text_edit.is_some()
            && !ui.ctx().text_edit_focused()
            && !photocraft_ui_egui::menus::artcraft_discard_active(&self.inner)
        {
            photocraft_ui_egui::type_tool::commit(&mut self.inner);
        }
        self.artcraft_esc_pending = false;
        if pc_typing_before_ui && self.inner.ui.text_edit.is_none() && !ui.ctx().text_edit_focused() {
            let _ = self.bridge.hide_native_keyboard();
        }
        self.inner.finish_type_reset_pass(ui.ctx());
''')

    # No guessing hardware keys from Text (including input to a newly focused
    # widget). Only actual Key events may activate commands or answer prompts.
    section(host, '        hardware_keys::recover_text_keys(\n',
            '        trackpad_wheel::route(&self.bridge, ctx, raw);', '')
    patch(host, '        hardware_keys::inject(&self.bridge, raw);\n',
          '''        let pc_received = hardware_keys::inject(&self.bridge, raw, &mut self.modifiers);
        if !pc_typing && pc_received > 0 {
            self.pc_keyboard_diag.push(format!("JNI received: {pc_received} transitions"));
        }
''')
    # Retire the direct modal queue: upstream consumes Y/N/C in the dialog,
    # once, with its normal focus and save semantics.
    dialog = opt.upstream / 'crates/ui-egui/src/dialogs/discard_ui.rs'
    # Remove just the known injected block, preserving all upstream handling.
    block = '''    #[cfg(target_os = "android")]
    {
        let direct = match crate::menus::artcraft_take_dialog_key() {
            1 => Some(Answer::Save), 2 => Some(Answer::Discard),
            3 => Some(Answer::Cancel), _ => None,
        };
        if direct.is_some() { answer = direct; }
    }
'''
    if block in dialog.read_text():
        patch(dialog, block, '')

    # Keep diagnostics off while typing: key names also reveal typed text.
    patch(act, '        int code = e.getKeyCode();\n', '''        int code = e.getKeyCode();
        if (imeWanted && code != KeyEvent.KEYCODE_ESCAPE) return;
''')
    patch(host, '        self.pc_keyboard_diag.note_keys("Native/egui", raw);\n', '''        let pc_typing = self.inner.ui.text_edit.is_some() || ctx.text_edit_focused();
        if !pc_typing { self.pc_keyboard_diag.note_keys("Native/egui", raw); }
''')
    patch(host, '        self.pc_keyboard_diag.note_keys("After bridge", raw);\n',
          '        if !pc_typing { self.pc_keyboard_diag.note_keys("After bridge", raw); }\n')
    patch(host, '        self.inner.logic(ctx, frame);\n', '''        let pc_before = self.inner.ui.tool;
        let pc_key_pass = ctx.input(|i| i.events.iter().any(|e| matches!(e, egui::Event::Key { pressed: true, .. })));
        if pc_key_pass && self.inner.ui.text_edit.is_none() && !ctx.text_edit_focused() {
            self.pc_keyboard_diag.push(format!("Before dispatch: {pc_before:?}; widget focus={}, modal={}",
                ctx.egui_wants_keyboard_input(), photocraft_ui_egui::menus::artcraft_discard_active(&self.inner)));
        }
        self.inner.logic(ctx, frame);
        for (id, outcome) in photocraft_ui_egui::shortcut_dispatch::take_log(ctx) {
            let status = match outcome {
                photocraft_ui_egui::shortcut_dispatch::Outcome::Ran => "executed",
                photocraft_ui_egui::shortcut_dispatch::Outcome::Disabled(_) => "disabled",
                photocraft_ui_egui::shortcut_dispatch::Outcome::Failed(_) => "failed",
            };
            if id.starts_with("tools.") || id == "file.close" {
                self.pc_keyboard_diag.push(format!("Command {id}: {status}"));
            }
        }
        if pc_key_pass && self.inner.ui.text_edit.is_none() && !ctx.text_edit_focused() {
            self.pc_keyboard_diag.push(format!("Upstream logic tool: {pc_before:?} -> {:?}", self.inner.ui.tool));
        }
''')
    patch(host, '        self.inner.ui(ui, _frame);\n', '''        let pc_before_ui = self.inner.ui.tool;
        let pc_typing_before_ui = self.inner.ui.text_edit.is_some();
        self.inner.ui(ui, _frame);
        if pc_before_ui != self.inner.ui.tool {
            self.pc_keyboard_diag.push(format!("UI tool transition: {pc_before_ui:?} -> {:?}", self.inner.ui.tool));
        }
''')
    patch(host, 'Ok(Some(value)) => self.pc_keyboard_diag.push(format!("Android | {value}")),',
          'Ok(Some(value)) => { if !pc_typing { self.pc_keyboard_diag.push(format!("Android | {value}")); } },')
    (opt.adapter / 'src/hardware_keys.rs').write_text(
        (Path(__file__).parent / 'photocraft_keyboard_repair/hardware_keys.rs').read_text())
    assert 'artcraft_tool_pending' not in host.read_text()
    print('Candidate keyboard repair staged; device behavior remains unverified')


if __name__ == '__main__':
    main()
