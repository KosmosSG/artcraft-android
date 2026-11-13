"""Final, isolated v0.24.1 wheel isolation and confirmed-quit lifecycle overlay."""
from pathlib import Path
import sys, shutil
from patch_android8_wheel_touch import once

def patch(root):
    host = root/'adapters/vectorcraft/src/lib.rs'
    java = root/'adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java'
    ui = root/'source/vectorcraft/crates/ui-egui/src'
    once(host, '        self.stylus_wheel.capture(ctx, raw, wheel_blocked);\n        self.inner.raw_input_hook(ctx, raw);',
         '        self.inner.raw_input_hook(ctx, raw);\n        self.stylus_wheel.capture(ctx, raw, wheel_blocked);')
    # Canvas input must not see native samples or cached pointer state either.
    # This frame-local flag is overwritten on EVERY raw input hook, never a lock.
    once(ui/'canvas/input.rs',
         '    let (pointer, m, space, hover) = wheel_view(app, ui, resp, rect);',
         '''    #[cfg(target_os = "android")]
    if ui.data(|d| d.get_temp::<bool>(egui::Id::new("vc-wheel-input-owned")).unwrap_or(false)) {
        let view = app.view_info();
        drop_press(app, ui, view);
        app.session.tool_hover_ended(view);
        let _ = tool_frame_moves(ui, app, false); // drain native stylus samples
        ui.data_mut(|d| {
            d.remove::<Drag>(drag_id());
            d.insert_temp(egui::Id::unique("canvas-hovered"), false);
        });
        return;
    }
    #[cfg(target_os = "android")]
    ui.data_mut(|d| {
        let id = egui::Id::new("vc-canvas-input-frames");
        let frames = d.get_temp::<u64>(id).unwrap_or(0);
        d.insert_temp(id, frames + 1);
    });
    let (pointer, m, space, hover) = wheel_view(app, ui, resp, rect);''')
    once(host, '            let diagnostic_java = self.vc_diag_snapshot.clone();',
         '''            let diagnostic_java = format!("{}\\nwheel_consumed_events={} canvas_input_frames={}",
                self.vc_diag_snapshot, self.stylus_wheel.diagnostic_counts(),
                ui.data(|d| d.get_temp::<u64>(egui::Id::new("vc-canvas-input-frames")).unwrap_or(0)));''')
    once(host, '                    self.vc_diag_snapshot,', '                    diagnostic_java,')
    # Do not route native long-press arrows into the preview/customizer.
    wheel = root/'adapters/vectorcraft/src/stylus_wheel.rs'
    once(java, '    public void vcFinishAfterQuit() {',
         '''    // Set only by android_main AFTER eframe returned and saved preferences.
    // Normal backgrounding, rotation and file pickers must never exit the process.
    private volatile boolean vcConfirmedNativeQuit = false;
    public void vcFinishAfterQuit() {
        vcConfirmedNativeQuit = true;''')
    once(java, '        vcMarkNativeQuitStage("on_destroy_return");',
         '''        vcMarkNativeQuitStage("on_destroy_return");
        if (vcConfirmedNativeQuit && !isChangingConfigurations()) {
            // NativeActivity teardown has now acknowledged native thread completion.
            // No sleeps, watchdog kill, UI-thread join, or app-data clearing.
            Log.i(TAG, "VC_LIFECYCLE2 process_exit pid=" + android.os.Process.myPid()
                + " uptime_ms=" + android.os.SystemClock.uptimeMillis());
            android.os.Process.killProcess(android.os.Process.myPid());
        }''')
    once(java, '        startupStage("activity_created");',
         '''        Log.i(TAG, "VC_LIFECYCLE2 activity_create pid=" + android.os.Process.myPid()
            + " uptime_ms=" + android.os.SystemClock.uptimeMillis());
        startupStage("activity_created");''')
    once(java, '        Log.i(TAG, "VC_QUIT4 stage=" + stage);',
         '''        Log.i(TAG, "VC_QUIT4 stage=" + stage + " pid=" + android.os.Process.myPid()
            + " uptime_ms=" + android.os.SystemClock.uptimeMillis());''')
    # Observe a presented frame with one asynchronous PixelCopy. No retries, no gate.
    once(java, '    public void vcNativeUiReady() {',
         '''    private boolean vcFirstBufferSampled;
    private void vcObserveFirstBuffer() {
        if (vcFirstBufferSampled || isFinishing() || isDestroyed()) return;
        vcFirstBufferSampled = true;
        SurfaceView surface = findNativeSurface(getWindow().getDecorView());
        if (surface == null || !surface.getHolder().getSurface().isValid()) {
            startupStage("first_buffer_unavailable");
            return;
        }
        final android.graphics.Bitmap sample = android.graphics.Bitmap.createBitmap(
            1, 1, android.graphics.Bitmap.Config.ARGB_8888);
        try {
            PixelCopy.request(surface, sample, result -> {
                startupStage(result == PixelCopy.SUCCESS ? "first_buffer_observed" : "first_buffer_not_ready");
                sample.recycle();
            }, splashHandler);
        } catch (RuntimeException error) {
            sample.recycle();
            startupStage("first_buffer_probe_failed");
        }
    }
    public void vcNativeUiReady() {''')
    once(java, '            splashHandler.postDelayed(this::dismissStartupCover, 120);',
         '''            // Main looper has handled the native-ready handoff. Dismiss on
            // the next UI frame; no arbitrary 120ms wait or PixelCopy dependency.
            getWindow().getDecorView().postOnAnimation(() -> {
                dismissStartupCover();
                vcObserveFirstBuffer();
                startupStage("main_ready_after_native_ui");
            });''')
    once(java, '                    Log.i(TAG, "VC_IME12 first_edit_rebind completed");',
         '''                    startupStage("ime_first_edit_rebind");
                    Log.i(TAG, "VC_IME12 first_edit_rebind completed");''')
    # Compile/run actual wheel behavior in the host UI crate, using its exact egui.
    source=wheel.read_text().replace('//! Experimental, opt-in VectorCraft Magic-Pencil 4s wheel. TEST ONLY.', '')
    shutil.copyfile(wheel.with_name('stylus_wheel_vc.rgba'), ui/'stylus_wheel_vc.rgba')
    (ui/'android_wheel_tests.rs').write_text('use crate as vectorcraft_ui_egui;\n'+source)
    with (ui/'lib.rs').open('a') as f:
        f.write('\n#[cfg(test)]\nmod android_wheel_tests;\n')
    print('PASS: v0.24.1 frame-local canvas isolation, native samples drained, confirmed-quit process boundary, startup diagnostics')

if __name__=='__main__': patch(Path(sys.argv[1]))
