"""VectorCraft Android.19: selective Nov-05 MostafaXS1 Android input focus lifecycle.

Reference: MostafaXS1/artcraft-android main, commit 52308fbc (2026-11-05).
Preserve the owner's JNI IME protocol (c/p/f/d/a) and custom canvas/menus.

The preceding Android.18 patch still left a focusable, attached EditText
visible to the Android window-manager outside of typing. Mostafa's current
ArtCraftInputView is View.GONE and NOT focusable outside imeShow().
Apply exactly that lifecycle to our existing EditText without replacing it.
Also wake the native loop as soon as modal keys enter the queue, not only
after Rust has processed the action (which required another ESC on MagicOS).
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    s=once(s,'''            addContentView(imeView, params);
        } catch (Throwable error)''',
    '''            addContentView(imeView, params);
            // MostafaXS1 2026-11-05: physically hide and disable native
            // keyboard focus until a real Type editor requests IME input.
            imeView.setVisibility(View.GONE);
            imeView.setFocusable(false);
            imeView.setFocusableInTouchMode(false);
            imeView.clearFocus();
        } catch (Throwable error)''')
    s=once(s,'''                view.setFocusable(true);
                view.setFocusableInTouchMode(true);
                view.requestFocus();
                InputMethodManager imm =''',
    '''                view.setVisibility(View.VISIBLE);
                view.setFocusable(true);
                view.setFocusableInTouchMode(true);
                view.requestFocus();
                InputMethodManager imm =''')
    s=once(s,'''                    view.clearFocus();
                    view.setText("");
                }
                // A NativeActivity SurfaceView is normally''',
    '''                    view.clearFocus();
                    view.setFocusable(false);
                    view.setFocusableInTouchMode(false);
                    view.setVisibility(View.GONE);
                    view.setText("");
                }
                // A NativeActivity SurfaceView is normally''')
    s=once(s,'''                view.clearFocus();
                // Drop the scratch buffer between sessions so it cannot grow without bound.''',
    '''                view.clearFocus();
                view.setFocusable(false);
                view.setFocusableInTouchMode(false);
                view.setVisibility(View.GONE);
                // Drop the scratch buffer between sessions so it cannot grow without bound.''')
    # The Android.18 immediate modal focus code failed because the EditText
    # remained focusable and IME could reclaim it on the following frame.
    s=once(s,'''                        imeView.clearFocus();
                    }
                    SurfaceView nativeSurface =''',
    '''                        imeView.clearFocus();
                        imeView.setFocusable(false);
                        imeView.setFocusableInTouchMode(false);
                        imeView.setVisibility(View.GONE);
                    }
                    SurfaceView nativeSurface =''')

    # Enqueueing a physical S/D/C is NOT a native input event if the key was
    # absorbed by EditText. Wake the native loop in the same UI callback.
    s=once(s,'''                physicalShortcutKeys.offer(key);
                vcLastModalKeyDownTime = downTime;''',
    '''                physicalShortcutKeys.offer(key);
                vcWakeNativeLoop();
                vcLastModalKeyDownTime = downTime;''')
    s=once(s,'''        physicalShortcutKeys.offer(code);
        return true;''',
    '''        physicalShortcutKeys.offer(code);
        vcWakeNativeLoop();
        return true;''')
    s=once(s,'''                physicalShortcutKeys.offer(key);
            }
            // Key-up must be consumed alongside Down''',
    '''                physicalShortcutKeys.offer(key);
                // A Java-swallowed hardware key otherwise never wakes native
                // winit/egui until Escape or a touchscreen pointer moves.
                vcWakeNativeLoop();
            }
            // Key-up must be consumed alongside Down''')
    # Avoid the stale hidden EditText regrabbing focus after SAF/IME lifecycle.
    s=once(s,'''            if (!imeWanted && imeView != null && imeView.hasFocus()) {
                getWindow().getDecorView().post(this::vcEndTypeEditing);
            }''',
    '''            if (!imeWanted && imeView != null &&
                    (imeView.hasFocus() || imeView.getVisibility() != View.GONE)) {
                getWindow().getDecorView().post(this::vcEndTypeEditing);
            }''')

    # NativeActivity's content is a native Window, not necessarily a Java
    # SurfaceView. The older PixelCopy sampler never found a SurfaceView
    # (0 samples after 83s), so it cannot be a gate for cold startup.
    # Keep the platform-branded splash while probing the Window directly,
    # with a safety ceiling. This only changes splash; no app UI inputs.
    s=once(s,'''        splash.setKeepOnScreenCondition(() -> !nativeEditorReady);
        // Fail open rather than trapping the user behind the system splash''',
    '''        // Keep branded system splash until a painted *window* is verified.
        // NativeActivity may have no discoverable Java SurfaceView.
        // Hard ceiling avoids an app that can never expose its editor.
        final long vcSplashDeadline = android.os.SystemClock.uptimeMillis() + 15000L;
        splash.setKeepOnScreenCondition(() -> !nativeEditorReady
            && android.os.SystemClock.uptimeMillis() < vcSplashDeadline);
        // Fail open rather than trapping the user behind the system splash''')
    s=once(s,'''        startupStage("native_ui_traversal_ready");
        runOnUiThread(() -> splashHandler.postDelayed(() -> {
            if (!isFinishing() && !isDestroyed()) {
                nativeEditorReady = true;
                startupStage("native_editor_visible");
                dismissStartupCover();
            }
        }, 450));''',
    '''        startupStage("native_ui_traversal_ready");
        runOnUiThread(() -> {
            if (vcProbeWindowStartMs == 0L)
                vcProbeWindowStartMs = android.os.SystemClock.uptimeMillis();
            vcProbeWindowFrame();
        });''')
    s=once(s,'''    private int splashDp(int dp) {''',
    '''    private long vcProbeWindowStartMs = 0L;
    private int vcWindowPaintedSamples = 0;
    private boolean vcWindowFrameProbePending = false;

    private void vcProbeWindowFrame() {
        if (nativeEditorReady || vcWindowFrameProbePending ||
            isFinishing() || isDestroyed()) return;
        // The renderer can be slow when fonts/preferences first initialize.
        // Never let a native frame probe run forever or block document input.
        if (android.os.SystemClock.uptimeMillis() - vcProbeWindowStartMs > 14000L) {
            startupStage("window_frame_probe_timeout");
            return; // OS splash deadline independently releases the UI.
        }
        Window source = getWindow();
        View decor = source == null ? null : source.getDecorView();
        if (source == null || decor == null ||
                decor.getWidth() < 30 || decor.getHeight() < 30) {
            splashHandler.postDelayed(this::vcProbeWindowFrame, 110);
            return;
        }
        vcWindowFrameProbePending = true;
        final Bitmap bitmap = Bitmap.createBitmap(32, 20, Bitmap.Config.ARGB_8888);
        try {
            PixelCopy.request(source, bitmap, result -> {
                vcWindowFrameProbePending = false;
                int light = 0, dark = 0;
                if (result == PixelCopy.SUCCESS) {
                    for (int y = 0; y < bitmap.getHeight(); y++) {
                        for (int x = 0; x < bitmap.getWidth(); x++) {
                            int pixel = bitmap.getPixel(x, y);
                            int r = Color.red(pixel), g = Color.green(pixel), b = Color.blue(pixel);
                            if (Math.max(r, Math.max(g, b)) > 125) light++;
                            if (Math.max(r, Math.max(g, b)) < 75) dark++;
                        }
                    }
                }
                bitmap.recycle();
                boolean painted = result == PixelCopy.SUCCESS && light > 10 && dark > 10;
                vcWindowPaintedSamples = painted ? vcWindowPaintedSamples + 1 : 0;
                if (vcWindowPaintedSamples >= 2) {
                    nativeEditorReady = true;
                    startupStage("native_window_painted");
                    dismissStartupCover();
                } else {
                    splashHandler.postDelayed(this::vcProbeWindowFrame, 115);
                }
            }, splashHandler);
        } catch (Throwable error) {
            vcWindowFrameProbePending = false;
            bitmap.recycle();
            Log.w(TAG, "Window frame probe unavailable", error);
            splashHandler.postDelayed(this::vcProbeWindowFrame, 250);
        }
    }

    private int splashDp(int dp) {''')
    java.write_text(s)
    print("PASS: reference hidden/non-focusable input host, immediate modal key wake, window-level frame probe; owner IME/features unchanged")

if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
