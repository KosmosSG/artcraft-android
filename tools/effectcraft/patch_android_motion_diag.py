#!/usr/bin/env python3
"""EffectCraft Android.10: reliable, direct Android logcat MotionEvent diagnosis.

Diagnose ignored trackpad MotionEvents, avoiding tracing-subscriber dependence.
Staged only into the disposable pinned winit checkout. Never log raw
coordinates, device identifiers, keystrokes, text, or personal documents.
"""
from pathlib import Path

ANCHOR = """                match motion_event.action() {
                    // Hover:"""
FFI_ANCHOR = "static HAS_FOCUS: AtomicBool = AtomicBool::new(true);"
FFI = r"""
// Diagnostic-only native Android logger; no tracing subscriber is required.
#[link(name = "log")]
unsafe extern "C" {
    fn __android_log_write(
        priority: std::ffi::c_int,
        tag: *const std::ffi::c_char,
        text: *const std::ffi::c_char,
    ) -> std::ffi::c_int;
}
"""
REPLACEMENT = r"""                // Temporary diagnostic: preserve native dispatch, report sampled
                // events from ALL input-source classes. A generic MotionEvent
                // source must not suppress the diagnosis of HONOR Smart Touch.
                let ec10_action = motion_event.action();
                static EC10_MOVE_COUNT: std::sync::atomic::AtomicUsize =
                    std::sync::atomic::AtomicUsize::new(0);
                static EC10_HOVER_COUNT: std::sync::atomic::AtomicUsize =
                    std::sync::atomic::AtomicUsize::new(0);
                let ec10_sample = match ec10_action {
                    MotionAction::Scroll => true,
                    MotionAction::Down | MotionAction::Up |
                    MotionAction::PointerDown | MotionAction::PointerUp |
                    MotionAction::Cancel => true,
                    MotionAction::Move =>
                        EC10_MOVE_COUNT.fetch_add(1, Ordering::Relaxed) % 8 == 0,
                    MotionAction::HoverMove =>
                        EC10_HOVER_COUNT.fetch_add(1, Ordering::Relaxed) % 32 == 0,
                    _ => false,
                };
                if ec10_sample {
                    let (v, h, x48, y49, x50, y51, scale52) =
                        motion_event.pointers().next().map(|p| (
                            p.axis_value(Axis::Vscroll), p.axis_value(Axis::Hscroll),
                            p.axis_value(Axis::__Unknown(48)), p.axis_value(Axis::__Unknown(49)),
                            p.axis_value(Axis::__Unknown(50)), p.axis_value(Axis::__Unknown(51)),
                            p.axis_value(Axis::__Unknown(52)),
                        )).unwrap_or((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0));
                    if let Ok(line) = std::ffi::CString::new(format!(
                        "EC10 event action={:?} source={:?} tool={:?} contacts={} mouseclass={} \
                         vscroll={:.3} hscroll={:.3} gesture48={:.5} gesture49={:.5} \
                         scroll50={:.3} scroll51={:.3} pinch52={:.4}",
                        ec10_action, motion_event.source(), tool_type,
                        motion_event.pointer_count(), pointer_class,
                        v, h, x48, y49, x50, y51, scale52,
                    )) {
                        // Android log priority 4 = INFO. Direct liblog bypasses
                        // tracing filters and makes grep/tag-based capture reliable.
                        unsafe {
                            __android_log_write(
                                4,
                                b"EffectCraftMotion\0".as_ptr().cast(),
                                line.as_ptr(),
                            );
                        }
                    }
                }
                match motion_event.action() {
                    // Hover:"""

def apply(root: Path):
    path = root / "src/platform_impl/android/mod.rs"
    src = path.read_text(encoding="utf-8")
    if "EC10 event action=" in src:
        raise RuntimeError("STOP: Android.10 diagnostic already applied")
    if src.count(ANCHOR) != 1 or src.count(FFI_ANCHOR) != 1:
        raise RuntimeError("STOP: pinned-winit input/logger anchor drift")
    for key in ("MotionAction::Scroll => {", "MotionAction::Move if pointer_class",
                "Axis::__Unknown(50)", "Axis::__Unknown(52)"):
        if key not in src:
            raise RuntimeError("STOP: expected Android.8 gesture handling absent: " + key)
    src = src.replace(FFI_ANCHOR, FFI_ANCHOR + "\n" + FFI, 1)
    src = src.replace(ANCHOR, REPLACEMENT, 1)
    path.write_text(src, encoding="utf-8")
    print("PASS: EffectCraft Android.10 direct native liblog diagnostic installed")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_android_motion_diag.py <pinned-vendor-winit>")
    apply(Path(sys.argv[1]))
