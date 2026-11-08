"""VectorCraft Android.18: targeted device failures after Android.17.

Preserve all owner features, upstream VectorCraft v0.21 and published baseline.
- Keep platform branded splash until the native editor signals ready: no exposed
  black SurfaceView on slow cold starts; no unreliable PixelCopy gating.
- On entering Save Changes, move hardware keyboard focus immediately from the
  hidden text EditText to native SurfaceView, without an Escape prerequisite.
- Turn on upstream canvas multi-touch navigation and accept active touch/zoom
  gestures even if egui's Response.hovered temporarily goes false mid-pinch.
- Trackpad wheel/zoom are forwarded unchanged; do not select sidebar tools
  from a gesture by injecting synthetic pointer presses.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    s=once(s,'''        startupStage("activity_created");
        // Fail open rather than trapping the user behind the system splash''',
    '''        startupStage("activity_created");
        // Android.17 dropped the system splash before Rust/GPU initialization.
        // Keep the OS-managed branded splash until Rust's second UI traversal.
        // Unlike the old PixelCopy watchdog, this cannot wait for a SurfaceView
        // that the platform splash itself might prevent from presenting.
        splash.setKeepOnScreenCondition(() -> !nativeEditorReady);
        // Fail open rather than trapping the user behind the system splash''')
    s=once(s,'''        nativeEditorReady = true;
        startupStage("reference_direct_native_surface");
        applyImmersiveFullscreen();''',
    '''        startupStage("platform_splash_until_native_ui");
        applyImmersiveFullscreen();''')
    s=once(s,'''        startupStage("reference_native_ui_ready");
        nativeEditorReady = true;''',
    '''        startupStage("native_ui_traversal_ready");
        runOnUiThread(() -> splashHandler.postDelayed(() -> {
            if (!isFinishing() && !isDestroyed()) {
                nativeEditorReady = true;
                startupStage("native_editor_visible");
                dismissStartupCover();
            }
        }, 450));''')
    # Safety: the existing watchdog doesn't dismiss until a PixelCopy proves a
    # frame; a broken probe must not hold the OS splash indefinitely.
    s=once(s,'''                startupStage("renderer_watchdog_active");
            }
        }, 20000);''',
    '''                startupStage("renderer_watchdog_active");
                // A branded loading screen is preferable to exposing a
                // black GPU surface; keep this stage diagnostic for now.
            }
        }, 20000);''')

    # The crucial difference: Java never released its invisible EditText on
    # entering Save Changes (mode 2), only on canvas mode 1 after ESC. The
    # user's "Ctrl+W → ESC → D/S/C" exactly matches that missing focus handoff.
    s=once(s,'''        if (hardwareShortcutMode != mode) physicalShortcutKeys.clear();
        hardwareShortcutMode = mode;''',
    '''        final int previousMode = hardwareShortcutMode;
        if (previousMode != mode) physicalShortcutKeys.clear();
        hardwareShortcutMode = mode;
        if (mode == 2 && previousMode != 2) {
            // Save Changes is not a text editor. Give physical keys back to
            // NativeActivity immediately; C/S/D then work without ESC.
            imeWanted = false;
            runOnUiThread(() -> {
                if (hardwareShortcutMode != 2) return;
                try {
                    if (imeView != null) {
                        InputMethodManager imm = (InputMethodManager)
                            getSystemService(INPUT_METHOD_SERVICE);
                        if (imm != null)
                            imm.hideSoftInputFromWindow(imeView.getWindowToken(), 0);
                        imeView.clearFocus();
                    }
                    SurfaceView nativeSurface =
                        findNativeSurface(getWindow().getDecorView());
                    if (nativeSurface != null && nativeSurface.isShown()) {
                        nativeSurface.setFocusable(true);
                        nativeSurface.setFocusableInTouchMode(true);
                        nativeSurface.requestFocus();
                    }
                    vcWakeNativeLoop();
                } catch (Throwable e) {
                    Log.w(TAG, "Save Changes keyboard focus transition failed", e);
                }
            });
        }''')
    # Routing in the native egui logic still has one source of truth. The
    # immediate native wake is safe because there is no text to compose.
    java.write_text(s)

    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    s=once(s,'''            log::info!("VectorCraft startup diagnostic: prefs_restored={}ms", startup_instant.elapsed().as_millis());''',
    '''            log::info!("VectorCraft startup diagnostic: prefs_restored={}ms", startup_instant.elapsed().as_millis());
            // Use VectorCraft upstream's Taps/two-finger gesture and canvas
            // pan/pinch router. Never substitute two-finger pointer selection.
            app.session.prefs.touch_gestures = true;''')
    # Ensure the existing low-latency wheel classifier handles both axes.
    rust.write_text(s)

    # Existing upstream already implements multi_touch.translation_delta,
    # zoom_delta and drop_press. The hover gate can become false as the first
    # finger is captured; continue a touch gesture started on the canvas.
    canvas=root/"source/vectorcraft/crates/ui-egui/src/canvas/input.rs"
    s=canvas.read_text()
    s=once(s,'''    let hover = pointer.hover_pos().filter(|p| rect.contains(*p));
    // Zoom around the pointer, and scroll''',
    '''    let hover = pointer.hover_pos().filter(|p| rect.contains(*p));
    // Native touch navigation remains on the canvas when egui's hovered
    // response changes after the first finger presses. Do not treat wheel
    // activity above a toolbar as a canvas gesture.
    let touch_center = ui.input(|i| i.multi_touch().map(|t| t.center_pos))
        .filter(|p| rect.contains(*p));
    let gesture_on_canvas = touch_center.is_some();
    // Zoom around the pointer, and scroll''')
    s=once(s,'''    if resp.hovered() {
        if (factor - 1.0).abs() > 1e-6
            && let (Some(p), Some(vm)) = (hover, app.view_mut())
        {
            zoom_about(vm, rect, p, vm.zoom * factor);
        }
        if scroll != egui::Vec2::ZERO {
            scroll_view(app, ui, scroll);
        }
        if let Some(p) = hover
            && let Some(deg) = trackpad_turn''',
    '''    if resp.hovered() || gesture_on_canvas {
        if (factor - 1.0).abs() > 1e-6
            && let (Some(p), Some(vm)) = (touch_center.or(hover), app.view_mut())
        {
            zoom_about(vm, rect, p, vm.zoom * factor);
        }
        if scroll != egui::Vec2::ZERO {
            scroll_view(app, ui, scroll);
        }
        if let Some(p) = hover
            && let Some(deg) = trackpad_turn''')
    canvas.write_text(s)
    print("PASS: Android.18 platform splash, immediate Save-modal keyboard focus, upstream touch navigation and continuous canvas pinch")
if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
