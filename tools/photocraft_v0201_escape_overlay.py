#!/usr/bin/env python3
"""Android.3: first-observed hardware DOWN and non-text Escape diagnostics."""
import argparse
import subprocess
from pathlib import Path
from photocraft_v0201_keyboard_diagnostics_overlay import patch, PIN


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--upstream', type=Path, required=True)
    cli.add_argument('--adapter', type=Path, required=True)
    opt = cli.parse_args()
    assert subprocess.check_output(['git', '-C', str(opt.upstream), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    host = opt.adapter / 'src/lib.rs'
    act = opt.adapter / 'java/com/artcraft/photocraft/PhotoCraftActivity.java'
    patch(opt.adapter / 'Cargo.toml', 'version = "0.20.1-android.2"', 'version = "0.20.1-android.3"')
    gate = Path(__file__).parent / 'photocraft_keyboard_repair/PcHardwareKeyGate.java'
    (act.parent / gate.name).write_text('package com.artcraft.photocraft;\n' + gate.read_text())
    patch(act, '''    private long artcraftLastKeyTime = -1L;
    private int artcraftLastKeyCode = -1;
    private int artcraftLastKeyAction = -1;
''', '''    private final PcHardwareKeyGate pcHardwareKeyGate = new PcHardwareKeyGate();
''')
    patch(act, '        if (action == KeyEvent.ACTION_DOWN && event.getRepeatCount() != 0) return;\n', '')
    patch(act, '''        if (event.getEventTime() == artcraftLastKeyTime
                && code == artcraftLastKeyCode && action == artcraftLastKeyAction) return;
        artcraftLastKeyTime = event.getEventTime();
        artcraftLastKeyCode = code;
        artcraftLastKeyAction = action;
''', '''        if (!pcHardwareKeyGate.accept(code, action, event.getRepeatCount(),
                event.getEventTime(), event.getDownTime(), event.getDeviceId())) return;
''')
    patch(act, '        super.onWindowFocusChanged(hasFocus);\n',
          '        super.onWindowFocusChanged(hasFocus);\n        if (!hasFocus) pcHardwareKeyGate.clear();\n')
    patch(act, '''        if (!pcDiagEnabled || e.getAction() != KeyEvent.ACTION_DOWN
                || e.getRepeatCount() != 0) return;
''', '''        if (!pcDiagEnabled || (e.getAction() != KeyEvent.ACTION_DOWN
                && e.getAction() != KeyEvent.ACTION_UP)) return;
''')
    patch(act, '        pcDiagKeys.offer(route + " | " + KeyEvent.keyCodeToString(code)\n',
          '''        pcDiagKeys.offer(route + " | " + KeyEvent.keyCodeToString(code)
            + (e.getAction() == KeyEvent.ACTION_DOWN ? " DOWN" : " UP")
            + " repeat=" + e.getRepeatCount()
''')
    # Key names of typed letters stay suppressed; Escape is never text.
    for source in ('Native/egui', 'After bridge'):
        patch(host, f'        if !pc_typing {{ self.pc_keyboard_diag.note_keys("{source}", raw); }}\n',
              f'''        if self.pc_keyboard_diag.visible {{
            let mut diagnostic_input = raw.clone();
            if pc_typing {{
                diagnostic_input.events.retain(|e| matches!(e,
                    egui::Event::Key {{ key: egui::Key::Escape, .. }}));
            }}
            self.pc_keyboard_diag.note_keys("{source}", &diagnostic_input);
        }}
''')
    patch(host, 'if let egui::Event::Key { key, pressed: true, modifiers, .. } = event {\n                if matches!(key,',
          'if let egui::Event::Key { key, pressed, modifiers, .. } = event {\n                if matches!(key,')
    patch(host, 'self.push(format!("{source} | {key:?}{}",\n',
          'self.push(format!("{source} | {key:?} down={pressed}{}",\n')
    patch(host, 'if !pc_typing && pc_received > 0 {', 'if pc_received > 0 {')
    patch(host, 'JNI received: {pc_received} transitions', 'JNI polled: {pc_received} records (not proof of a press)')
    patch(host, 'if !pc_typing { self.pc_keyboard_diag.push(format!("Android | {value}")); }',
          'if !pc_typing || value.contains("KEYCODE_ESCAPE ") { self.pc_keyboard_diag.push(format!("Android | {value}")); }')
    patch(host, '''                    self.artcraft_esc_pending = true;
''', '''                    self.artcraft_esc_pending = true;
                    self.pc_keyboard_diag.push("Escape DOWN queued for active Type editor".into());
''')
    patch(host, '''        self.artcraft_esc_pending = false;
''', '''        if self.artcraft_esc_pending {
            self.pc_keyboard_diag.push(format!("Escape UI tail: Type editing={}", self.inner.ui.text_edit.is_some()));
        }
        self.artcraft_esc_pending = false;
''')
    print('Android.3 first-observed DOWN gate and Escape stage diagnostics staged')


if __name__ == '__main__':
    main()
