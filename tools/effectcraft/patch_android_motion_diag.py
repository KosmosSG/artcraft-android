#!/usr/bin/env python3
"""EffectCraft-only Android 9: lightweight MotionEvent observability.

Inserted ONLY into the disposable pinned-winit runner checkout after compatibility
rebasing. Never log pointer coordinates, key events, text or identifiers.
"""
from pathlib import Path

ANCHOR = """                match motion_event.action() {
                    // Hover:"""
REPLACEMENT = """                // Temporary Android.9 diagnostic: rate-limited source/action/axis report.
                // HONOR Smart Touch reports Linux ABS_MT, so its framework translation
                // must be observed before another gesture-routing change.
                if matches!(motion_event.action(),
                    MotionAction::Scroll | MotionAction::Move | MotionAction::HoverMove)
                    && (pointer_class || matches!(motion_event.source(), Source::Touchpad))
                {
                    static EC_MOTION_SAMPLE: std::sync::atomic::AtomicUsize =
                        std::sync::atomic::AtomicUsize::new(0);
                    if EC_MOTION_SAMPLE.fetch_add(1, Ordering::Relaxed) % 12 == 0 {
                        let (v, h, x48, y49, x50, y51, scale52) =
                            motion_event.pointers().next().map(|p| (
                                p.axis_value(Axis::Vscroll), p.axis_value(Axis::Hscroll),
                                p.axis_value(Axis::__Unknown(48)),
                                p.axis_value(Axis::__Unknown(49)),
                                p.axis_value(Axis::__Unknown(50)),
                                p.axis_value(Axis::__Unknown(51)),
                                p.axis_value(Axis::__Unknown(52))
                            )).unwrap_or((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0));
                        tracing::warn!(
                            target: "EffectCraftGesture",
                            "EC9 motion action={:?} source={:?} tool={:?} contacts={} mouseclass={} vscroll={:.3} hscroll={:.3} gesture48={:.5} gesture49={:.5} scroll50={:.3} scroll51={:.3} pinch52={:.4}",
                            motion_event.action(), motion_event.source(), tool_type,
                            motion_event.pointer_count(), pointer_class, v, h,
                            x48, y49, x50, y51, scale52,
                        );
                    }
                }
                match motion_event.action() {
                    // Hover:"""

def apply(root: Path):
    path = root / "src/platform_impl/android/mod.rs"
    src = path.read_text(encoding="utf-8")
    if "EC9 motion action=" in src:
        raise RuntimeError("STOP: diagnostic already applied")
    if src.count(ANCHOR) != 1:
        raise RuntimeError("STOP: pinned-winit input dispatch drift")
    for key in ("MotionAction::Scroll => {", "MotionAction::Move if pointer_class", "Axis::__Unknown(50)"):
        if key not in src:
            raise RuntimeError("STOP: expected Android.8 pointer routing missing: "+key)
    path.write_text(src.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    print("PASS: narrow non-sensitive EffectCraft Android.9 source/gesture diagnostic installed")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_android_motion_diag.py <pinned-vendor-winit>")
    apply(Path(sys.argv[1]))
