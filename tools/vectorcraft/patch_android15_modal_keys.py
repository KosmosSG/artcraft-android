"""VectorCraft Android.15 — Save Changes S/D fix + source-aware diagnostics.

After Android.14 diagnostic overlay, preserve the native Save/Don't Save buttons
and keep C/ESC unchanged. Route S/D through the same upstream dialog callbacks
as those buttons, from either Android Java IME host or egui text/key events.
Never process typed text outside the saveChanges modal.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    s=once(s, '    public int vcPollPhysicalShortcut() {', '''
    // Physical keyboards can deliver to EditText.onKeyDown, Activity, or an
    // InputConnection even after Rust has switched to the Save Changes modal.
    // Queue only a single *modal* action, and never capture document text.
    private long vcLastModalKeyDownTime = Long.MIN_VALUE;
    private int vcLastModalKey = -1;
    private boolean vcOfferModalShortcut(int key, long downTime, boolean shift,
            boolean alt, boolean meta, boolean ctrl) {
        if (hardwareShortcutMode != 2 || imeWanted || shift || alt || meta) return false;
        // Ctrl can remain latched after Ctrl+W on MagicOS; modal owns D/S/C.
        if (key != KeyEvent.KEYCODE_D && key != KeyEvent.KEYCODE_S
                && key != KeyEvent.KEYCODE_C && key != KeyEvent.KEYCODE_ESCAPE) {
            return false;
        }
        if (downTime != vcLastModalKeyDownTime || key != vcLastModalKey) {
            if (physicalShortcutKeys.size() < 32) {
                physicalShortcutKeys.offer(key);
                vcLastModalKeyDownTime = downTime;
                vcLastModalKey = key;
            }
        }
        return true;
    }

    private boolean vcOfferModalCommit(CharSequence value) {
        if (hardwareShortcutMode != 2 || imeWanted || value == null ||
                value.length() != 1) return false;
        final char c = Character.toLowerCase(value.charAt(0));
        final int code = c == 'd' ? KeyEvent.KEYCODE_D
            : c == 's' ? KeyEvent.KEYCODE_S
            : c == 'c' ? KeyEvent.KEYCODE_C : 0;
        if (code == 0) return false;
        if (physicalShortcutKeys.size() >= 32) return false;
        physicalShortcutKeys.offer(code);
        return true;
    }
    public int vcPollPhysicalShortcut() {''')

    # Some physical keyboard drivers route the key via the hidden IME's
    # InputConnection, not through Activity.dispatchKeyEvent / winit.
    s=once(s, '''                            if (text != null && text.length() > 0) {
                                imeEvents.offer("c" + text);
                            }
                            return super.commitText(text, newCursorPosition);''',
    '''                            if (vcOfferModalCommit(text)) return true;
                            if (text != null && text.length() > 0) {
                                imeEvents.offer("c" + text);
                            }
                            return super.commitText(text, newCursorPosition);''')
    s=once(s, '''                        public boolean sendKeyEvent(KeyEvent event) {
                            if (event.getAction() == KeyEvent.ACTION_DOWN) {''',
    '''                        public boolean sendKeyEvent(KeyEvent event) {
                            if (event.getAction() == KeyEvent.ACTION_DOWN &&
                                    event.getRepeatCount() == 0 &&
                                    vcOfferModalShortcut(event.getKeyCode(), event.getDownTime(),
                                        event.isShiftPressed(), event.isAltPressed(),
                                        event.isMetaPressed(), event.isCtrlPressed())) {
                                return true;
                            }
                            if (event.getAction() == KeyEvent.ACTION_UP &&
                                    hardwareShortcutMode == 2 &&
                                    (event.getKeyCode() == KeyEvent.KEYCODE_D ||
                                     event.getKeyCode() == KeyEvent.KEYCODE_S ||
                                     event.getKeyCode() == KeyEvent.KEYCODE_C ||
                                     event.getKeyCode() == KeyEvent.KEYCODE_ESCAPE)) {
                                return true;
                            }
                            if (event.getAction() == KeyEvent.ACTION_DOWN) {''')
    s=once(s, '''                    // Let hardware key events fall through to the native input queue (winit), exactly
                    // as they did before this view existed; the soft keyboard talks to us through the
                    // InputConnection instead. This keeps physical keyboards working.
                    return false;''',
    '''                    // Only Save Changes steals D/S/C. Ordinary editing
                    // and all other physical key paths remain untouched.
                    if (event.getRepeatCount() == 0 &&
                            vcOfferModalShortcut(keyCode, event.getDownTime(),
                                event.isShiftPressed(), event.isAltPressed(),
                                event.isMetaPressed(), event.isCtrlPressed())) return true;
                    return false;''')
    s=once(s, '''                public boolean onKeyUp(int keyCode, KeyEvent event) {
                    return false;
                }''',
    '''                public boolean onKeyUp(int keyCode, KeyEvent event) {
                    return hardwareShortcutMode == 2 && !imeWanted &&
                        (keyCode == KeyEvent.KEYCODE_D || keyCode == KeyEvent.KEYCODE_S ||
                         keyCode == KeyEvent.KEYCODE_C || keyCode == KeyEvent.KEYCODE_ESCAPE);
                }''')
    # Activity's normal dispatch route already intercepts modal keys; this
    # extends its guard against stale Ctrl only in a Save Changes modal.
    s=once(s, '''        if (plain && (canvasKey || dialogKey)) {''',
    '''        if ((plain && canvasKey) ||
                (dialogKey && !event.isShiftPressed() && !event.isAltPressed()
                    && !event.isMetaPressed())) {''')
    java.write_text(s)

    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    old='''            let modal_key = raw.events.iter().find_map(|event| match event {
                egui::Event::Key {
                    key, physical_key, pressed: true, repeat: false, modifiers, ..
                } if !modifiers.command && !modifiers.ctrl && !modifiers.alt
                    && !modifiers.shift =>
                {
                    let key = physical_key.unwrap_or(*key);
                    matches!(key, egui::Key::S | egui::Key::D |
                        egui::Key::C | egui::Key::Escape).then_some(key)
                }
                _ => None,
            });
            if let Some(key) = modal_key {
                if self.inner.android_owner_unsaved_key(key) {
                    raw.events.retain(|event| !matches!(event,
                        egui::Event::Key {
                            pressed: true, key: logical, physical_key, ..
                        } if physical_key.unwrap_or(*logical) == key));
                    ctx.request_repaint();
                }
            }'''
    new='''            // Java can emit physical Key events, while MagicOS/IME sometimes
            // delivers only single-character Text into the native queue.
            // This branch runs solely for the unsaved-changes modal; never
            // interpret normal Type editing text as a shortcut.
            let modal_key = raw.events.iter().find_map(|event| match event {
                egui::Event::Key {
                    key, physical_key, pressed: true, repeat: false, modifiers, ..
                } if !modifiers.alt && !modifiers.shift && !modifiers.mac_cmd =>
                {
                    let key = physical_key.unwrap_or(*key);
                    matches!(key, egui::Key::S | egui::Key::D |
                        egui::Key::C | egui::Key::Escape).then_some((key,"key"))
                }
                egui::Event::Text(text) if text.len() == 1 => {
                    let key = match text.as_str() {
                        "s" | "S" => Some(egui::Key::S),
                        "d" | "D" => Some(egui::Key::D),
                        "c" | "C" => Some(egui::Key::C),
                        _ => None,
                    };
                    key.map(|k|(k,"text"))
                }
                _ => None,
            });
            if let Some((key,source)) = modal_key {
                let before_docs = self.inner.session.documents().len();
                let before_uid = self.inner.ui.dialog.as_ref()
                    .and_then(|d| d.fields.get("uid"))
                    .and_then(serde_json::Value::as_u64);
                if self.inner.android_owner_unsaved_key(key) {
                    // Prevent upstream duplicate handling, including a paired
                    // Text event. Keep all unrelated input events unchanged.
                    raw.events.retain(|event| match event {
                        egui::Event::Key {key: logical, physical_key,pressed:true,..}
                            => physical_key.unwrap_or(*logical) != key,
                        egui::Event::Text(t) if t.len()==1 => !matches!(
                            (key,t.as_str()),
                            (egui::Key::S,"s"|"S") |
                            (egui::Key::D,"d"|"D") |
                            (egui::Key::C,"c"|"C")
                        ),
                        _ => true,
                    });
                    let after_docs = self.inner.session.documents().len();
                    let after_dialog = self.inner.ui.dialog.as_ref()
                        .map(|d|d.kind.as_str()).unwrap_or("none");
                    self.vc_diag_last_modal_action = format!(
                        "key={key:?} route={source} docs={before_docs}->{after_docs} \
                         prior_uid_present={} dialog_after={after_dialog}",
                        before_uid.is_some());
                    if self.vc_diag_recording {
                        self.vc_diag_history.push_back(format!("+{}ms modal_action {}",
                            self.vc_diag_started.map_or(0,|t|t.elapsed().as_millis()),
                            self.vc_diag_last_modal_action));
                    }
                    ctx.request_repaint();
                }
            }'''
    s=once(s,old,new)
    s=once(s, '''    vc_diag_egui_shortcuts: u64,''',
    '''    vc_diag_egui_shortcuts: u64,
    vc_diag_last_modal_action: String,''')
    s=once(s, '''                vc_diag_egui_shortcuts: 0,''',
    '''                vc_diag_egui_shortcuts: 0,
                vc_diag_last_modal_action: "none".into(),''')
    s=once(s, '''                    "VectorCraft Android.14 Diagnostic Session\\n\\
                     elapsed_ms={elapsed}\\n\\
                     egui_shortcut_receipts={}\\n\\
                     tool={} editing={} composing={} dialog={}\\n\\
                     last_keyboard_gate={}\\n\\
                     last_keyboard_command={}\\n\\
                     java_snapshot:\\n{}\\n\\
                     transition_log:\\n{}\\n",''',
    '''                    "VectorCraft Android.15 Diagnostic Session\\n\\
                     elapsed_ms={elapsed}\\n\\
                     egui_shortcut_receipts={}\\n\\
                     tool={} editing={} composing={} dialog={}\\n\\
                     last_keyboard_gate={}\\n\\
                     last_keyboard_command={}\\n\\
                     last_modal_action={}\\n\\
                     java_snapshot:\\n{}\\n\\
                     transition_log:\\n{}\\n",''')
    s=once(s, '''                    self.vc_diag_snapshot,
                    self.vc_diag_history.iter().cloned().collect::<Vec<_>>().join("\\n"));''',
    '''                    self.vc_diag_last_modal_action,
                    self.vc_diag_snapshot,
                    self.vc_diag_history.iter().cloned().collect::<Vec<_>>().join("\\n"));''')
    rust.write_text(s)
    print("PASS: Android.15 scoped Save Changes S/D/C fallback: hardware/IME/Text and post-action result diagnostic")

if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
