"""VectorCraft Android.7: same-direction canvas trackpad pan + relaunch ANR mitigation.

Applied LAST after Android.6 candidate staging, ONLY to isolated test sources.
Native pinch detector, menu directions, touchscreen pan/zoom, shortcuts and
unsaved-document native-loop-first Ctrl+Q must remain unchanged.
"""
from pathlib import Path


def once(s: str, old: str, new: str, label: str) -> str:
    n=s.count(old)
    if n != 1:
        raise ValueError(f"Android.7 {label} anchor count={n}, refusing change")
    return s.replace(old,new,1)


def patch(root: Path) -> None:
    adapter=root/"adapters/vectorcraft/src/lib.rs"
    s=adapter.read_text()
    s=once(s,'''        }
        // Trigger high-refresh redraws only during actual gestures''',
    '''        } else {
            // Android.7 canvas-only HONOR touchpad natural pan:
            // finger swipe UP/LEFT moves artwork UP/LEFT; DOWN/RIGHT moves
            // artwork DOWN/RIGHT. MagicOS's native scroll-distance axes
            // describe viewport movement, while egui consumes content
            // movement: reverse both PixelDelta axes, ONCE, before egui
            // builds its smoothing/inertia. Keep popup menu's Android.5
            // tested direction and touchscreen's Android.6 gestures intact.
            let canvas_target = self.inner.canvas_rect.is_some_and(|canvas| {
                ctx.pointer_hover_pos().map_or(true, |pos| canvas.contains(pos))
            });
            if canvas_target
                && !raw.events.iter().any(|event| matches!(event, egui::Event::Touch { .. }))
            {
                for event in &mut raw.events {
                    if let egui::Event::MouseWheel {
                        unit: egui::MouseWheelUnit::Point,
                        source: egui::MouseWheelSource::Trackpad
                            | egui::MouseWheelSource::Unknown,
                        modifiers,
                        delta, ..
                    } = event {
                        if !modifiers.any() {
                            // A small, bounded response gain helps short
                            // two-finger glides without replay or momentum
                            // engines, and never changes pinch Event::Zoom.
                            delta.x *= -1.15;
                            delta.y *= -1.15;
                        }
                    }
                }
            }
        }
        // Trigger high-refresh redraws only during actual gestures''',
    "canvas trackpad wheel direction")
    for must in (
        "delta.x *= -1.15;", "delta.y *= -1.15;",
        "vc_quit_after_native",
        "if egui::Popup::is_any_open(ctx)",
    ):
        if must not in s:
            raise ValueError(f"Android.7 guard missing adapter token: {must}")
    adapter.write_text(s)
    canvas=(root/"source/vectorcraft/crates/ui-egui/src/canvas/input.rs").read_text()
    if "trackpad_pinch_needs_anchor" not in canvas:
        raise ValueError("Android.7 required Android.5 canvas pinch guard missing")

    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    j=java.read_text()
    # Report the worst main-looper callback delay after an ANR recovery.
    # This tells us if the main thread was blocked in NativeActivity startup
    # or if a separate native render/Vulkan worker was unresponsive.
    j=once(j,'''    private volatile boolean nativeEditorReady;''',
    '''    // Android.7 diagnostic: lightweight main-thread heartbeat to distinguish
    // startup UI-thread stalls from a slow native renderer. No user content,
    // coordinates, text, filenames or private data are captured.
    private final Handler vcMainWatchHandler = new Handler(Looper.getMainLooper());
    private volatile long vcMainWatchMaxDelayMs = 0L;
    private volatile String vcMainWatchMaxStage = "none";
    private boolean vcMainWatchActive = false;
    private long vcMainWatchNextMs = 0L;
    private final Runnable vcMainWatchTick = new Runnable() {
        @Override public void run() {
            if (!vcMainWatchActive) return;
            long now = android.os.SystemClock.uptimeMillis();
            long delay = Math.max(0L, now - vcMainWatchNextMs);
            if (delay > vcMainWatchMaxDelayMs) {
                vcMainWatchMaxDelayMs = delay;
                vcMainWatchMaxStage = vcDiagStartupStage;
                if (delay > 1500L)
                    Log.w(TAG, "VC_MAIN7 main_looper_delay_ms=" + delay
                        + " stage=" + vcMainWatchMaxStage);
            }
            vcMainWatchNextMs = now + 400L;
            vcMainWatchHandler.postDelayed(this, 400L);
        }
    };
    private volatile boolean nativeEditorReady;''',
    "main looper measurement")
    j=once(j,'''        startupStage("android25_before_native_onCreate");
        super.onCreate(savedInstanceState);''',
    '''        vcMainWatchActive = true;
        vcMainWatchNextMs = android.os.SystemClock.uptimeMillis() + 400L;
        vcMainWatchHandler.postDelayed(vcMainWatchTick, 400L);
        startupStage("android25_before_native_onCreate");
        super.onCreate(savedInstanceState);''',
    "track main thread through native super.onCreate")
    j=once(j,'''    protected void onDestroy() {
        vcMarkNativeQuitStage("on_destroy_enter");''',
    '''    protected void onDestroy() {
        vcMainWatchActive = false;
        vcMainWatchHandler.removeCallbacks(vcMainWatchTick);
        vcMarkNativeQuitStage("on_destroy_enter");''',
    "stop heartbeat on destruction")
    j=once(j,'''return "java_stage=" + vcDiagStartupStage
            + "\\nprior_process_stage=" + vcDiagPreviousStage''',
    '''return "java_stage=" + vcDiagStartupStage
            + "\\nmain_looper_max_delay_ms=" + vcMainWatchMaxDelayMs
            + "; main_looper_max_delay_stage=" + vcMainWatchMaxStage
            + "\\nprior_process_stage=" + vcDiagPreviousStage''',
    "augment existing private diagnostics")
    # Previous Android.4 sessions never sampled the native surface yet spent
    # ~2.8 seconds repeatedly looking for it on the MAIN looper. In the user
    # trace, java_stage=android24_buffer_probe_timeout; this probe is NOT an
    # editor readiness signal. Return to tested direct splash dismissal after
    # first native UI traversal, without changing native startup or frame pacing.
    j=once(j,'''splashHandler.post(this::vcAndroid24RevealNativeBuffer);''',
    '''// Android.7: do not spam the UI thread with repeated SurfaceView
            // lookup and PixelCopy when the OEM never exposes the native surface.
            // Keep the existing fail-open startup cover and native editor callback.
            splashHandler.postDelayed(this::dismissStartupCover, 120);''',
    "remove unproductive repeated startup buffer probes")
    for must in (
        "main_looper_max_delay_ms", "vcMainWatchHandler", "VC_MAIN7",
        "splashHandler.postDelayed(this::dismissStartupCover, 120);",
        'vcMarkNativeQuitStage("on_destroy_return")',
    ):
        if must not in j:
            raise ValueError(f"Android.7 Java guard missing {must}")
    java.write_text(j)
    print("PASS: Android.7 canvas-only trackpad X/Y natural pan, separate menu/touch/pinch, bounded startup probe, main-thread ANR diagnostics")


if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
