"""VectorCraft Android.20: remove ESC-only keyboard wake and frozen static splash.

Device evidence: Android.19 (2026-11-09) ctrl+w D/S/C and tool shortcuts
only update after ESC; 15s Vc system splash has a pixel sampling deadlock.

MostafaXS1 Android native input backend remains intact. Fix the owner
Activity's swallowing of real hardware key events, and use the UI callback
rather than PixelCopy(Window) beneath an opaque Android system splash.

Strict replacement guards: preserve all owner font, menu, updater, cursor,
touch/trackpad and document paths. This is a disposable ARM64 test only.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    java = root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s = java.read_text()

    # A static Android 12 system splash cannot draw a progress indicator.
    # PixelCopy(Window) is unable to prove paint while that splash obscures
    # the window. The previous 15s deadline explains the reported frozen Vc.
    s = once(s,'''        final long vcSplashDeadline = android.os.SystemClock.uptimeMillis() + 15000L;
        splash.setKeepOnScreenCondition(() -> !nativeEditorReady
            && android.os.SystemClock.uptimeMillis() < vcSplashDeadline);''',
    '''        final long vcSplashDeadline = android.os.SystemClock.uptimeMillis() + 1200L;
        splash.setKeepOnScreenCondition(() -> !nativeEditorReady
            && android.os.SystemClock.uptimeMillis() < vcSplashDeadline);''')

    # Branded animated Java cover is responsive even when Vulkan initialization
    # is slow. Remove from a second UI traversal with a bounded presentation
    # delay; no dependency on PixelCopy(Window) which samples the overlay itself.
    s = once(s,'''        startupStage("platform_splash_until_native_ui");
        applyImmersiveFullscreen();''',
    '''        startupStage("platform_splash_until_native_ui");
        showStartupCover();
        applyImmersiveFullscreen();''')
    s = once(s,'''        contents.addView(label, title);

        cover.addView(contents''',
    '''        contents.addView(label, title);
        android.widget.ProgressBar progress = new android.widget.ProgressBar(this);
        progress.setIndeterminate(true);
        LinearLayout.LayoutParams progressLayout = new LinearLayout.LayoutParams(
                splashDp(30), splashDp(30));
        progressLayout.topMargin = splashDp(24);
        progressLayout.gravity = Gravity.CENTER_HORIZONTAL;
        contents.addView(progress, progressLayout);
        label.setText("VectorCraft is loading…");

        cover.addView(contents''')
    s = once(s,'''        startupStage("native_ui_traversal_ready");
        runOnUiThread(() -> {
            if (vcProbeWindowStartMs == 0L)
                vcProbeWindowStartMs = android.os.SystemClock.uptimeMillis();
            vcProbeWindowFrame();
        });''',
    '''        startupStage("native_ui_traversal_ready");
        runOnUiThread(() -> splashHandler.postDelayed(() -> {
            if (!isFinishing() && !isDestroyed()) {
                nativeEditorReady = true;
                startupStage("native_editor_ui_ready");
                dismissStartupCover();
            }
        }, 420));''')
    # Remove only the no-longer-used Window PixelCopy method. Keep the
    # original diagnostics and SurfaceView probe available for troubleshooting.
    begin=s.index("    private long vcProbeWindowStartMs = 0L;")
    end=s.index("    private int splashDp(int dp) {",begin)
    unused=s[begin:end]
    assert "private void vcProbeWindowFrame()" in unused and "PixelCopy.request(source, bitmap" in unused
    s=s[:begin]+s[end:]

    # MostafaXS1 2026-11-05 provides a JNI bridge into the native Android
    # event-loop waker. Unlike dispatching KEYCODE_UNKNOWN through Java, this
    # wakes an idle native poll immediately even for InputConnection commits.
    # Keep the existing fallback for older/missing JNI and other device paths.
    s = once(s, '''    public void vcWakeNativeLoop() {
        runOnUiThread(() -> {''',
    '''    public void vcWakeNativeLoop() {
        try {
            com.artcraft.ime.ArtCraftIme.wake();
        } catch (Throwable error) {
            Log.d(TAG, "Native IME loop wake unavailable; using Java fallback");
        }
        runOnUiThread(() -> {''')

    # When Java enqueues a hardware key and returns true, NativeActivity's
    # event loop never sees that key: requests sit pending until ESC wakes it.
    # Forward the ORIGINAL event to the native backend, not a KEYCODE_UNKNOWN
    # synthetic event. Rust will de-duplicate the matching queued physical key.
    s = once(s, '''            return true;
        }
        final int mode = hardwareShortcutMode;''',
    '''            // Keep native winit's looper awake for the actual Ctrl+W/Q.
            return super.dispatchKeyEvent(event);
        }
        final int mode = hardwareShortcutMode;''')
    s = once(s, '''            // Key-up must be consumed alongside Down to avoid leaking a
            // stranded release event to the upstream keyboard state.
            return true;
        }
        return super.dispatchKeyEvent(event);''',
    '''            // The real key is needed by NativeActivity to wake its looper.
            // Rust drops the duplicate native key when a Java-queued fallback
            // is present, retaining exactly one editor/tool action.
            return super.dispatchKeyEvent(event);
        }
        return super.dispatchKeyEvent(event);''')
    # The actual Custom "offer shortcut" path consumes event in helper.
    s = once(s, '''        physicalShortcutKeys.offer(code);
        vcWakeNativeLoop();
        return true;''',
    '''        physicalShortcutKeys.offer(code);
        vcWakeNativeLoop();
        return true;''') if False else s

    # NativeActivity does not always expose a Java SurfaceView to focus:
    # prior device diagnostics showed zero SurfaceView PixelCopy samples.
    # Put hardware keyboard focus back on the native activity's decor root
    # if SurfaceView is unavailable; never do this while editing text.
    s = once(s, '''                } else {
                    Log.w(TAG, "Native SurfaceView not yet present for keyboard focus");
                }
                // The hidden EditText can generate''',
    '''                } else {
                    View decor = getWindow().getDecorView();
                    decor.setFocusable(true);
                    decor.setFocusableInTouchMode(true);
                    decor.requestFocus();
                    Log.i(TAG, "Type exit returned keyboard to NativeActivity decor");
                }
                // The hidden EditText can generate''')
    s = once(s, '''                    if (nativeSurface != null && nativeSurface.isShown()) {
                        nativeSurface.setFocusable(true);
                        nativeSurface.setFocusableInTouchMode(true);
                        nativeSurface.requestFocus();
                    }
                    vcWakeNativeLoop();''',
    '''                    if (nativeSurface != null && nativeSurface.isShown()) {
                        nativeSurface.setFocusable(true);
                        nativeSurface.setFocusableInTouchMode(true);
                        nativeSurface.requestFocus();
                    } else {
                        View decor = getWindow().getDecorView();
                        decor.setFocusable(true);
                        decor.setFocusableInTouchMode(true);
                        decor.requestFocus();
                    }
                    vcWakeNativeLoop();''')
    s = once(s, '''                if (surface != null && surface.isShown() &&
                        surface.getHolder().getSurface().isValid()) {
                    surface.setFocusable(true);
                    surface.setFocusableInTouchMode(true);
                    surface.requestFocus();
                }
            });
        }''',
    '''                if (surface != null && surface.isShown() &&
                        surface.getHolder().getSurface().isValid()) {
                    surface.setFocusable(true);
                    surface.setFocusableInTouchMode(true);
                    surface.requestFocus();
                } else {
                    View decor = getWindow().getDecorView();
                    decor.setFocusable(true);
                    decor.setFocusableInTouchMode(true);
                    decor.requestFocus();
                }
            });
        }''')
    java.write_text(s)

    rust = root/"adapters/vectorcraft/src/lib.rs"
    s = rust.read_text()
    # A Type editor can leave stale egui TextEdit focus for a few frames.
    # Scope the grace period to a real Type->canvas transition, never a
    # normal property text field or active IME composition.
    s = once(s, "    last_type_editing: bool,",
        "    last_type_editing: bool,\n    vc_after_type_exit_frames: u8,")
    s = once(s, "                last_type_editing: false,",
        "                last_type_editing: false,\n                vc_after_type_exit_frames: 0,")
    s = once(s, '''        if self.last_type_editing && !editing_now {
            ui.ctx().memory_mut(|memory| {''',
    '''        if self.last_type_editing && !editing_now {
            self.vc_after_type_exit_frames = 6;
            ui.ctx().memory_mut(|memory| {''')
    s = once(s, '''        let hardware_mode = if modal_save {''',
    '''        let just_exited_type = self.vc_after_type_exit_frames > 0
            && !editing && !composing;
        if just_exited_type && field_focused && !modal {
            ctx.memory_mut(|memory| {
                if let Some(id) = memory.focused() { memory.surrender_focus(id); }
            });
        }
        self.vc_after_type_exit_frames =
            self.vc_after_type_exit_frames.saturating_sub(1);
        let hardware_mode = if modal_save {''')
    s = once(s, '''!modal && !editing && !field_focused && !composing''',
        '''!modal && !editing && (!field_focused || just_exited_type) && !composing''')
    # The Java queue and native winit both describe the SAME hardware press.
    # Filter matching native key/Text from the current input frame before
    # re-inserting the Java fallback; do not touch actual IME composition.
    anchor='''            if let Some(key) = key {
                // Do not deliver letters to normal Gboard / Type editing.'''
    s=once(s,anchor,'''            if let Some(key) = key {
                // Java forwarded this physical key to native winit to wake
                // the looper. Remove the duplicate before egui sees it.
                raw.events.retain(|event| match event {
                    egui::Event::Key { key: native, physical_key, .. } =>
                        physical_key.unwrap_or(*native) != key,
                    egui::Event::Text(text) if hardware_mode == 1 =>
                        !text.eq_ignore_ascii_case(key.name()),
                    _ => true,
                });
                // Do not deliver letters to normal Gboard / Type editing.''')
    rust.write_text(s)
    print("PASS: Android.20 native-key wake, UI-based splash, focus fallback; preserve existing VectorCraft features")

if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
