"""Android.17: selectively port proven MostafaXS1 VectorCraft Android behaviour.

Reference: MostafaXS1/artcraft-android main/adapters/vectorcraft
- Nonblocking Android startup (no persistent custom cover / fake first-frame gate)
- Reconstruct physical key modifier state, preserving incoming authoritative flags
- Wake native event loop after Save Changes actions and SAF file picker transitions
- Restore focus to native SurfaceView after leaving keyboard/dialog
Scoped to VectorCraft generated adapter; all owner features remain in place.
"""
from pathlib import Path
from backend_stability import once


def patch(root: Path) -> None:
    java = root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s = java.read_text()

    # The reference Android VectorCraft shows the editor directly. Our previous
    # custom full-window cover was still present at t=83s with 0 PixelCopy
    # callbacks, and a hardware ESC was required to see other UI changes.
    # Keep the platform Android 12 splash, but let Android dismiss it with the
    # first window content frame, never gate on the broken PixelCopy probe.
    s = once(s, '''        splash.setKeepOnScreenCondition(() -> !nativeEditorReady);''',
        '''        // Reference VectorCraft: platform splash follows the native first draw.
        // Never park the entire UI behind an unverified custom overlay.
        // No custom keep-on-screen condition: Android owns splash timing.''')
    s = once(s, '''        showStartupCover();
        applyImmersiveFullscreen();''',
        '''        // The custom cover was never dismissed on HONOR MagicOS.
        // NativeActivity's real Vulkan surface is now exposed immediately.
        nativeEditorReady = true;
        startupStage("reference_direct_native_surface");
        applyImmersiveFullscreen();''')
    s = once(s, '''        // JNI is a signal to START checking; it is not presentation proof.
        runOnUiThread(() -> {
            if (firstFrameProbeStartMs == 0) firstFrameProbeStartMs = System.currentTimeMillis();
            probeFirstPresentedFrame();
        });''',
        '''        // The native editor is not gated by a PixelCopy-only watchdog.
        // A failing SurfaceView probe must never block a working editor.
        startupStage("reference_native_ui_ready");
        nativeEditorReady = true;''')

    # Prefer MostafaXS1's "wakeNativeLoop" behaviour instead of depending on
    # post-frame repaint requests that cannot wake a sleeping Android event
    # loop. UNKNOWN is a neutral key event, not a synthetic ESC or text key.
    s = once(s, '''    public String vcDiagnosticSnapshot() {''',
        '''    private volatile int vcDiagNativeWakes = 0;
    public void vcWakeNativeLoop() {
        runOnUiThread(() -> {
            try {
                dispatchKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_UNKNOWN));
                dispatchKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_UNKNOWN));
                getWindow().getDecorView().postInvalidateOnAnimation();
                vcDiagNativeWakes++;
            } catch (Throwable error) {
                Log.w(TAG, "Could not request native UI wake", error);
            }
        });
    }
    public String vcDiagnosticSnapshot() {''')
    s = once(s, '''            + "\\nframe_probe_stage=" + vcDiagFrameProbeStage''',
        '''            + "\\nframe_probe_stage=" + vcDiagFrameProbeStage
            + "\\nnative_wake_requests=" + vcDiagNativeWakes''')

    # Drop stale physical queue on *every* modal/canvas mode transition, not
    # merely typing-mode 0. Previously queued D/S/C could spill into a canvas
    # frame after D closed its document and change an unrelated tool.
    s = once(s, '''        hardwareShortcutMode = mode;
        if (mode == 0) physicalShortcutKeys.clear();''',
        '''        if (hardwareShortcutMode != mode) physicalShortcutKeys.clear();
        hardwareShortcutMode = mode;''')

    # Focus recovery after the modal closes must not touch any active IME
    # editing. This is done only when switching into idle-canvas mode.
    s = once(s, '''        if (mode == 1 && imeWanted) vcEndTypeEditing();''',
        '''        if (mode == 1 && imeWanted) vcEndTypeEditing();
        if (mode == 1 && !imeWanted) {
            runOnUiThread(() -> {
                if (hardwareShortcutMode != 1 || imeWanted) return;
                SurfaceView surface = findNativeSurface(getWindow().getDecorView());
                if (surface != null && surface.isShown() &&
                        surface.getHolder().getSurface().isValid()) {
                    surface.setFocusable(true);
                    surface.setFocusableInTouchMode(true);
                    surface.requestFocus();
                }
            });
        }''')
    java.write_text(s)

    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    s=once(s,'''    fn diagnostic_snapshot(&self) -> Result<String, String> {''',
        '''    fn wake_native_loop(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcWakeNativeLoop"),
                jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn diagnostic_snapshot(&self) -> Result<String, String> {''')
    s=once(s, '''                self.vc_modal_followup_repaints = 8;
                ctx.request_repaint();''',
        '''                self.vc_modal_followup_repaints = 8;
                if let Err(error) = self.bridge.wake_native_loop() {
                    log::warn!("Modal native event loop wake failed: {error}");
                }
                ctx.request_repaint();''')
    rust.write_text(s)

    # Restore physical modifier state reconstruction from the reference
    # VectorCraft; earlier overlays disabled it completely. Unlike blindly
    # rewriting every event, prefer incoming Ctrl/Alt/Shift if already set,
    # falling back to physically held modifiers only when the event is empty.
    mods=root/"adapters/vectorcraft/src/android_modifiers.rs"
    s=mods.read_text()
    s=once(s,'''pub fn apply_android_modifiers(_state: &mut AndroidModifiers, _raw: &mut egui::RawInput) {
    // The final winit backend forwards authoritative per-event Android meta
    // snapshots. Do not overwrite egui's modifiers with incomplete key history.
}''',
    '''pub fn apply_android_modifiers(state: &mut AndroidModifiers, raw: &mut egui::RawInput) {
    let mut kept = Vec::with_capacity(raw.events.len() + 2);
    for mut event in raw.events.drain(..) {
        match &mut event {
            egui::Event::Key { key, physical_key, pressed, modifiers, .. } => {
                let physical = physical_key.unwrap_or(*key);
                let index = match physical {
                    egui::Key::ShiftLeft => Some(0),
                    egui::Key::ShiftRight => Some(1),
                    egui::Key::ControlLeft => Some(2),
                    egui::Key::ControlRight => Some(3),
                    egui::Key::AltLeft => Some(4),
                    egui::Key::AltRight => Some(5),
                    _ => None,
                };
                if let Some(index) = index { state.held[index] = *pressed; }
                let from_hardware = state.modifiers();
                let incoming = *modifiers;
                let incoming_nonempty = incoming.ctrl || incoming.alt ||
                    incoming.shift || incoming.command || incoming.mac_cmd;
                if !incoming_nonempty {
                    *modifiers = from_hardware;
                }
                kept.push(event);
            }
            egui::Event::PointerButton { modifiers, .. } |
            egui::Event::MouseWheel { modifiers, .. } => {
                let from_hardware = state.modifiers();
                if !modifiers.ctrl && !modifiers.alt && !modifiers.shift &&
                    !modifiers.command && !modifiers.mac_cmd {
                    *modifiers = from_hardware;
                }
                kept.push(event);
            }
            egui::Event::Text(_) if state.modifiers().ctrl => {
                // Do not leak the typed character of Ctrl+W/Q or another
                // modified shortcut into an editable document.
            }
            egui::Event::WindowFocused(false) => {
                *state = AndroidModifiers::default();
                kept.push(egui::Event::ModifiersChanged(state.modifiers()));
                kept.push(event);
            }
            _ => kept.push(event),
        }
    }
    raw.events = kept;
}''')
    mods.write_text(s)
    print("PASS: VectorCraft Android.17 selectively adopts reference startup, modifier tracking and native event-loop wakes")

if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
