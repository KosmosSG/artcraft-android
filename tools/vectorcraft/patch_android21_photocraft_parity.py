"""VectorCraft Android.21: PhotoCraft-style cold start and direct popup scrolling.

Reference tested on HONOR MagicPad 4 2026-11-09:
PhotoCraft reaches editor in roughly 2s with NativeActivity's default
first-draw splash; no custom cover, PixelCopy gate, or delayed dismissal.
PhotoCraft forwards wheel input once to egui without a second menu
momentum integrator. VectorCraft Android.20 freezes a red 'Vc' cover while
its own UI is initializing, and applies another per-frame wheel easer.

This patch ONLY changes startup overlay usage and popup scroll routing.
It deliberately does not alter the *working* Android.20 physical keyboard,
typing, Ctrl+W/D/S/C, IME, font, updater, gestures or canvas input patches.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    activity=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    java=activity.read_text()
    # Follow PhotoCraft, which lets Android own the native startup splash
    # and draws the editor as soon as its first native buffer is available.
    # The VectorCraft-specific overlay was delaying visibility to ~10s.
    java=once(java,'''        SplashScreen splash = SplashScreen.installSplashScreen(this);''',
    '''        // PhotoCraft-compatible cold start: Android owns the platform
        // splash and dismisses it on NativeActivity's first native draw.
        // Do not add a custom static/animated cover over the editor.
        // Keep the approved Vc launcher icon; no launcher/theme change.''')
    java=once(java,'''        final long vcSplashDeadline = android.os.SystemClock.uptimeMillis() + 1200L;
        splash.setKeepOnScreenCondition(() -> !nativeEditorReady
            && android.os.SystemClock.uptimeMillis() < vcSplashDeadline);''',
    '''        // Do NOT gate the platform splash on PixelCopy or Rust's UI
        // traversal: the native frame should be visible immediately.''')
    java=once(java,'''        startupStage("platform_splash_until_native_ui");
        showStartupCover();
        applyImmersiveFullscreen();''',
    '''        startupStage("photocraft_direct_native_launch");
        applyImmersiveFullscreen();''')
    # Do not retain an idle full-screen overlay or PixelCopy timer; the
    # UI-ready callback now only records diagnostics and requests a draw.
    java=once(java,'''        startupStage("native_ui_traversal_ready");
        runOnUiThread(() -> splashHandler.postDelayed(() -> {
            if (!isFinishing() && !isDestroyed()) {
                nativeEditorReady = true;
                startupStage("native_editor_ui_ready");
                dismissStartupCover();
            }
        }, 420));''',
    '''        startupStage("native_ui_traversal_ready");
        runOnUiThread(() -> {
            nativeEditorReady = true;
            startupStage("native_editor_ui_ready");
            getWindow().getDecorView().postInvalidateOnAnimation();
        });''')
    activity.write_text(java)
    adapter=root/"adapters/vectorcraft/src/lib.rs"
    rust=adapter.read_text()
    rust=once(rust,'''        self.menu_scroll.apply(ctx, raw);''',
    '''        // PhotoCraft parity: let egui's one native popup scroll integrator
        // handle the full Android trackpad wheel stream without re-batching,
        // momentum replay or clamped step intervals. Preserve all wheel
        // sources/phases and the separate canvas pinch/zoom router.''')
    adapter.write_text(rust)
    print("PASS: PhotoCraft-style first native frame/no custom splash; direct menu wheel, no extra smoothing; keyboard left unchanged")

if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
