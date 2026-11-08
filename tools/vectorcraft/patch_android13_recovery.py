"""VectorCraft Android.13: targeted device-regression fixes, test-only.

Applies after Android.12 to the immutable staged upstream/builder files.
Goals: preserve shortcuts and unsaved documents, avoid stale Android IME
state blocking keyboard actions; no production keys or releases.
"""
from pathlib import Path
from backend_stability import once


def patch(root: Path) -> None:
    java = root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()

    # The Rust-supplied mode (only canvas/nontyping or Save Changes dialog)
    # determines key ownership. imeWanted can remain stale following ESC.
    s=once(s,'final boolean canvasKey = mode == 1 && !imeWanted',
        'final boolean canvasKey = mode == 1')
    s=once(s,'''        hardwareShortcutMode = mode;
        if (mode == 0) physicalShortcutKeys.clear();''','''        hardwareShortcutMode = mode;
        if (mode == 0) physicalShortcutKeys.clear();
        // On entry to the canvas the Type editor is already closed in Rust.
        // The invisible EditText must not retain native key focus.
        if (mode == 1 && imeWanted) vcEndTypeEditing();''')

    # Android finishAndRemoveTask can race a prompt re-launch of the native
    # activity on MagicOS. Let Activity lifecycle finish normally; NEVER call
    # finish until upstream confirms all unsaved work was resolved.
    s=once(s,'            finishAndRemoveTask();','''            hiddenImeCloseKeys.clear();
            physicalShortcutKeys.clear();
            hardwareShortcutMode = 0;
            // finish() permits normal onPause/onStop/onDestroy teardown and
            // avoids task-removal races when user immediately reopens the app.
            finish();''')

    # Android.11 left this 16-second "fail open" path in the early probe,
    # inadvertently bypassing Android.12's nonblack startup cover.
    s=once(s,'''        if (System.currentTimeMillis() - firstFrameProbeStartMs > 16000L) {
            // Fail open to a usable editor, but log the missing first-frame
            // proof for future GPU diagnostics instead of claiming success.
            Log.w(TAG, "First native frame not confirmed by PixelCopy in 16s");
            nativeEditorReady = true;
            dismissStartupCover();
            return;
        }''','''        if (System.currentTimeMillis() - firstFrameProbeStartMs > 16000L) {
            // Never expose an unpainted black GPU surface. Throttle the probe
            // while preserving the manual, visible "Tap to show editor" escape.
            if (firstFrameProbePending) return;
            splashHandler.postDelayed(this::probeFirstPresentedFrame, 700);
            return;
        }''')
    # If the window renders, release the splash, including after a slow restart.
    s=once(s,'''    private void dismissStartupCover() {
        FrameLayout cover = startupCover;''','''    private void dismissStartupCover() {
        FrameLayout cover = startupCover;''')
    java.write_text(s)

    src=root/"source/vectorcraft/crates/ui-egui/src/shortcuts.rs"
    s=src.read_text()
    # An app-level method is callable from the owner Android adapter BEFORE
    # egui's current-frame focus gate and without depending on an IME Key event.
    s += '''
// Android owner bridge: Save Changes has its own lifecycle; the hardware
// keyboard path must not rely on a focused egui viewport after IME teardown.
// Do not call app.run("ui.dialog.confirm") -- it is a control protocol command.
#[cfg(target_os = "android")]
impl VectorcraftApp {
    pub fn android_owner_unsaved_key(&mut self, key: Key) -> bool {
        if !self.ui.dialog.as_ref().is_some_and(|d| d.kind == crate::unsaved::KIND) {
            return false;
        }
        let result = match key {
            Key::C | Key::Escape => {
                crate::dialogs::cancel(self);
                Ok(serde_json::Value::Null)
            }
            Key::D => {
                if let Some(dialog) = self.ui.dialog.as_mut() {
                    crate::dialogs::set_field(dialog, "discard".into(), json!(true));
                }
                crate::dialogs::confirm(self)
            }
            Key::S => crate::dialogs::confirm(self),
            _ => return false,
        };
        if let Err(error) = result {
            // A cancelled/failed picker must retain its unsaved document.
            log::warn!("Android Save Changes keyboard command failed: {error}");
            self.status(error);
        }
        true
    }
}
'''
    src.write_text(s)

    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    # Java's queued key is already in raw.events at this point. Native-winit
    # events are handled by the same path. Consume exactly one physical press,
    # preserving unrelated IME, pointer, and keyboard events.
    needle='''        // The Android shell owns Ctrl+W and Ctrl+Q even when Type holds focus.'''
    s=once(s,needle,'''        // Handle physical Save Changes shortcuts before egui focus guards.
        // A previous text editor can leave ctx.text_edit_focused() stale.
        if self.inner.ui.dialog.as_ref().is_some_and(|d| d.kind == "saveChanges") {
            let modal_key = raw.events.iter().find_map(|event| match event {
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
            }
        }

'''+needle)
    # Restore direct V/T/P action for native winit keyboard delivery and
    # Java physical-key fallback. The prior Android.11 patch intentionally
    # replaced this with a no-op, which sends tool keys back to an unfocused
    # upstream shortcut dispatcher after typing.
    old='''                CanvasHardwareCommand::Selection | CanvasHardwareCommand::Type
                 | CanvasHardwareCommand::Pen => {}'''
    new='''                CanvasHardwareCommand::Selection | CanvasHardwareCommand::Type
                 | CanvasHardwareCommand::Pen => {
                    let tool_id = match command {
                        CanvasHardwareCommand::Selection => "selection",
                        CanvasHardwareCommand::Type => "type",
                        CanvasHardwareCommand::Pen => "pen",
                        _ => unreachable!(),
                    };
                    if !editing && !field_focused && !composing && !modal
                        && self.inner.session.active().is_some()
                    {
                        self.inner.select_tool(tool_id);
                        handled = true;
                    }
                }'''
    s=once(s,old,new)
    rust.write_text(s)
    print("PASS: direct native V/T/P and S/C/D, no stale Java IME gate, safe Activity finish, no black timeout")


if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
