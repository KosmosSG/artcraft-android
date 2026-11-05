#!/usr/bin/env python3
"""PhotoCraft-only native adaptive cursor; keep shared runtime protected."""
import argparse
from pathlib import Path
from photocraft_v0201_keyboard_diagnostics_overlay import patch

p = argparse.ArgumentParser()
p.add_argument('--adapter', type=Path, required=True)
a = p.parse_args().adapter
assets = Path(__file__).parent / 'photocraft_keyboard_repair'
host = a / 'src/lib.rs'
act = a / 'java/com/artcraft/photocraft/PhotoCraftActivity.java'
(a / 'src/adaptive_cursor.rs').write_text((assets / 'adaptive_cursor.rs').read_text())
(act.parent / 'PcAdaptiveCursor.java').write_text((assets / 'PcAdaptiveCursor.java').read_text())
patch(a / 'Cargo.toml', 'version = "0.20.1-android.3"', 'version = "0.20.1-android.4"')
patch(host, 'mod hardware_keys;', 'mod hardware_keys;\nmod adaptive_cursor;')
patch(host, 'impl AndroidFileBridge {\n    fn new(app: AndroidApp) -> Result<Self, String> {', '''impl AndroidFileBridge {
    fn pc_cursor(&self, name: &str) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let name = env.new_string(name)?;
            env.call_method(&*activity, jni_str!("pcSetCursor"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&name)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
    fn new(app: AndroidApp) -> Result<Self, String> {
''')
patch(host, '        match pc_action {', '''        // Read the cursor after the editor and diagnostic UI have resolved it.
        if ui.ctx().input(|i| i.pointer.hover_pos().is_some()) {
            let icon = ui.ctx().output(|o| o.cursor_icon);
            let _ = self.bridge.pc_cursor(adaptive_cursor::android_icon(icon));
        }
        match pc_action {''')
patch(act, '    private final PcHardwareKeyGate pcHardwareKeyGate = new PcHardwareKeyGate();', '''    private final PcAdaptiveCursor pcAdaptiveCursor = new PcAdaptiveCursor(this);
    public void pcSetCursor(String name) { pcAdaptiveCursor.request(name); }
    private final PcHardwareKeyGate pcHardwareKeyGate = new PcHardwareKeyGate();''')
patch(act, '        super.onWindowFocusChanged(hasFocus);', '''        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) pcAdaptiveCursor.reset();''')
print('PASS: PhotoCraft native cursor bridge staged; shared runtime unchanged')
