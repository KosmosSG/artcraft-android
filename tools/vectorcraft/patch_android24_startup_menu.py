"""Android.24: frame-aware startup reveal, popup wheel tuning, trackpad packet fidelity.

Applied strictly after Android.23 to the disposable test candidate only.
No IME/keyboard, modal D/S/C, font, updater, or release-signing changes.
The startup cover is retained until the first *sampled* native buffer rather
than being removed an arbitrary 120ms after the Rust UI traversal. PixelCopy
is asynchronous, with a bounded fail-open watchdog (no 15s splash trap).
"""
from pathlib import Path
import shutil
import sys


def once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Android.24 unreviewed source anchor ({count} matches): {old[:100]!r}")
    return source.replace(old, new, 1)


def patch(root: Path) -> None:
    java = root / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s = java.read_text()
    s = once(s, "splashHandler.postDelayed(this::dismissStartupCover, 120);",
             "splashHandler.post(this::vcAndroid24RevealNativeBuffer);")
    s = once(s, "    private void dismissStartupCover() {", """    // Android.23 removed the cover 120ms after Rust's first UI traversal,
    // which can precede the Vulkan swapchain's first presented buffer.
    // PixelCopy of the SurfaceView is nonblocking and excludes our Java cover.
    // The bounded fallback prevents a permanent cover if MagicOS refuses
    // PixelCopy, while the startupStage log tells us which path occurred.
    private long vcAndroid24ProbeStartedMs = 0L;
    private int vcAndroid24ProbeAttempts = 0;
    private void vcAndroid24RevealNativeBuffer() {
        if (isFinishing() || isDestroyed() || startupCover == null) return;
        final long now = android.os.SystemClock.uptimeMillis();
        if (vcAndroid24ProbeStartedMs == 0L) {
            vcAndroid24ProbeStartedMs = now;
            startupStage("android24_ui_callback_reached");
        }
        if (now - vcAndroid24ProbeStartedMs > 2800L) {
            startupStage("android24_buffer_probe_timeout");
            dismissStartupCover();
            return;
        }
        SurfaceView surface = findNativeSurface(getWindow().getDecorView());
        if (surface == null || surface.getHolder().getSurface() == null
                || !surface.getHolder().getSurface().isValid()
                || surface.getWidth() < 2 || surface.getHeight() < 2) {
            splashHandler.postDelayed(this::vcAndroid24RevealNativeBuffer, 48);
            return;
        }
        final Bitmap sample = Bitmap.createBitmap(20, 12, Bitmap.Config.ARGB_8888);
        vcAndroid24ProbeAttempts++;
        try {
            PixelCopy.request(surface, sample, code -> {
                boolean editorPixels = false;
                if (code == PixelCopy.SUCCESS) {
                    // A uniform initial black Vulkan clear is not an editor
                    // frame. A tiny inexpensive sample avoids false success.
                    int min = 255, max = 0;
                    for (int y = 0; y < sample.getHeight(); y++) {
                        for (int x = 0; x < sample.getWidth(); x++) {
                            int color = sample.getPixel(x, y);
                            int brightness = (Color.red(color) * 3
                                    + Color.green(color) * 6
                                    + Color.blue(color)) / 10;
                            min = Math.min(min, brightness);
                            max = Math.max(max, brightness);
                        }
                    }
                    editorPixels = max - min >= 18;
                }
                sample.recycle();
                if (isFinishing() || isDestroyed() || startupCover == null) return;
                if (editorPixels) {
                    startupStage("android24_first_buffer_visible");
                    Log.i(TAG, "VC_ANDROID24 first_buffer_samples="
                            + vcAndroid24ProbeAttempts);
                    dismissStartupCover();
                } else {
                    splashHandler.postDelayed(this::vcAndroid24RevealNativeBuffer, 48);
                }
            }, splashHandler);
        } catch (RuntimeException error) {
            sample.recycle();
            Log.w(TAG, "VC_ANDROID24 first-buffer copy unavailable", error);
            splashHandler.postDelayed(this::vcAndroid24RevealNativeBuffer, 80);
        }
    }

    private void dismissStartupCover() {""")
    java.write_text(s)

    dropdown = root / "source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
    s = dropdown.read_text()
    # One wheel owner remains egui. Slightly reduce batched wheel displacement
    # ONLY inside dropdowns. Touchscreen inertial scrolling is untouched.
    s = once(s, ".wheel_scroll_multiplier(egui::vec2(1.0, 1.0))",
             ".wheel_scroll_multiplier(egui::vec2(1.0, 0.90))")
    dropdown.write_text(s)
    print("PASS: Android.24 first-buffer reveal probe and menu-only 0.90 wheel tuning")


def patch_winit(root: Path) -> None:
    # This runs AFTER the Android.23 tested backend patch on the final vendored
    # winit. The old hard limits were throwing away large batched MagicOS
    # trackpad packets, making pans and pinches lag behind the fingers.
    p = root / "src/platform_impl/android/mod.rs"
    s = p.read_text()
    s = once(s, "(current.x - previous.x).clamp(-48.0, 48.0)",
             "(current.x - previous.x).clamp(-160.0, 160.0)")
    s = once(s, "(current.y - previous.y).clamp(-48.0, 48.0)",
             "(current.y - previous.y).clamp(-160.0, 160.0)")
    s = once(s, "factor.clamp(0.94, 1.06)",
             "factor.clamp(0.75, 1.33)")
    p.write_text(s)
    print("PASS: Android.24 bounded but responsive multi-pointer pan and pinch packets")


def install_backend_hook(root: Path) -> None:
    # The builder replaces upstream winit DURING build.sh. Apply after the
    # existing proven patch, never to the owner's published application.
    tools = root / "tools"
    tools.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__), tools / "vectorcraft_android24.py")
    script = root / "lib/build-common.sh"
    s = script.read_text()
    if "vectorcraft_android24.py" in s:
        raise ValueError("Android.24 backend hook already installed")
    old = 'python3 "$ROOT/tools/vectorcraft_backend_stability.py" "$SRC/vendor/winit"'
    s = once(s, old, old + '\n    python3 "$ROOT/tools/vectorcraft_android24.py" "$SRC/vendor/winit" --winit')
    script.write_text(s)
    print("PASS: Android.24 hook installed immediately after pinned winit patch")


if __name__ == "__main__":
    root = Path(sys.argv[1])
    if "--winit" in sys.argv[2:]:
        patch_winit(root)
    elif "--install-backend-hook" in sys.argv[2:]:
        install_backend_hook(root)
    else:
        patch(root)
