"""Tag Android glass two-finger wheel packets; reverse only on VectorCraft's canvas.

The published Android.9 native backend recognises two-finger touchscreen
panning BEFORE egui and sends a MouseWheel PixelDelta, while suppressing
per-contact egui Touch events. The previous canvas multi_touch sign patch
therefore had no effect. Keep native delta unchanged for menus; tag its source
with a tiny atomic packet count and route only the canvas pan differently.
No change to IME, Android.10, stylus or native touchpad gesture math.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sys

GLASS_MARKER = 'crate::platform::android::vc_glass_pan_note();'
NATIVE_OLD = '''                            GestureStep::Pan(delta) => {
                                trace!("Two-finger scroll {device_id:?} {delta:?}");'''
NATIVE_NEW = '''                            GestureStep::Pan(delta) => {
                                // Android glass gesture: egui receives a wheel event,
                                // NOT a multi_touch() event. Tag its actual source;
                                // the canvas adapter changes the sign only on canvas.
                                crate::platform::android::vc_glass_pan_note();
                                trace!("Two-finger scroll {device_id:?} {delta:?}");'''
ANDROID_API = '''
// VectorCraft Android.9 touch-glass pan provenance. Counts events only,
// never stores pointer positions, device identifiers, text or document data.
static VC_GLASS_PAN_PENDING: std::sync::atomic::AtomicUsize =
    std::sync::atomic::AtomicUsize::new(0);

pub(crate) fn vc_glass_pan_note() {
    VC_GLASS_PAN_PENDING.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
}

pub fn vc_glass_pan_take() -> usize {
    VC_GLASS_PAN_PENDING.swap(0, std::sync::atomic::Ordering::AcqRel)
}
'''

def once(s: str, old: str, new: str, label: str) -> str:
    n=s.count(old)
    if n != 1:
        raise ValueError(f"{label}: expected one reviewed anchor, found {n}: {old[:65]}")
    return s.replace(old,new,1)


def patch_native(winit: Path) -> None:
    rust = winit / "src/platform_impl/android/mod.rs"
    api = winit / "src/platform/android.rs"
    source = rust.read_text()
    if GLASS_MARKER in source or "vc_glass_pan_take" in api.read_text():
        raise ValueError("already patched or mixed native glass pan provenance; stop")
    if 'Classification::TwoFingerSwipe' not in source:
        raise ValueError("unknown native Android input backend")
    if source.count("GestureStep::Pan(delta)") != 1:
        raise ValueError("unexpected two-finger glass gesture path")
    source=once(source,NATIVE_OLD,NATIVE_NEW,"glass touch-to-wheel dispatch")
    assert source.count("event::MouseScrollDelta::PixelDelta(delta)") >= 1
    assert source.count(GLASS_MARKER) == 1
    # The native wheels keep their original delta (menus remain unchanged).
    rust.write_text(source)
    api.write_text(api.read_text()+ANDROID_API)
    print("PASS: Android glass two-finger source tag in native wheel dispatch; pinch/trackpad delta unchanged")


def patch_staged(root: Path) -> None:
    rust=root / "adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    s=once(s,'        self.ime.poll(raw);',
'''        // Always consume the native provenance once per frame, even in menus.
        // Do not retain a previous menu gesture for a subsequent canvas wheel.
        let vc_glass_pan_packets = winit::platform::android::vc_glass_pan_take();
        self.ime.poll(raw);''',
         "frame-local glass provenance")
    s=once(s,
'''            let canvas_target = self.inner.canvas_rect.is_some_and(|canvas| {''',
'''            // Native Android touchscreen gestures are translated to wheel
            // events by winit and never appear in egui multi_touch().
            // Change sign ONLY for confirmed glass pan wheels on the canvas.
            let vc_glass_candidate_wheels = raw.events.iter().filter(|event|
                matches!(event, egui::Event::MouseWheel {
                    unit: egui::MouseWheelUnit::Point,
                    source: egui::MouseWheelSource::Trackpad
                        | egui::MouseWheelSource::Unknown, ..
                })
            ).count();
            let vc_glass_canvas_pan = vc_glass_pan_packets > 0
                && vc_glass_pan_packets == vc_glass_candidate_wheels;
            let canvas_target = self.inner.canvas_rect.is_some_and(|canvas| {''',
        "canvas wheel source separation")
    s=once(s,
'''                            delta.x *= -1.15;
                            delta.y *= -1.15;''',
'''                            // Android.9 keeps the approved trackpad inversion.
                            // Glass native wheels took that same path but must
                            // have the OPPOSITE sign on canvas. Menus untouched.
                            let gain = if vc_glass_canvas_pan { 1.15 } else { -1.15 };
                            delta.x *= gain;
                            delta.y *= gain;''',
        "glass vs trackpad canvas wheel sign")
    for required in ("vc_glass_pan_take()", "vc_glass_pan_packets == vc_glass_candidate_wheels",
                     "let gain = if vc_glass_canvas_pan { 1.15 } else { -1.15 };",
                     'if egui::Popup::is_any_open(ctx)', 'self.inner.canvas_rect'):
        assert required in s, required
    rust.write_text(s)
    print("PASS: Android.9 canvas-only glass-wheel reversal with original trackpad/menu routing")


def install_hook(root: Path) -> None:
    import shutil
    src=Path(__file__)
    dst=root / "tools/vectorcraft_glass_pan_source.py"
    if dst.exists():
        raise ValueError("native glass source tag already installed")
    shutil.copyfile(src,dst)
    sh=root / "lib/build-common.sh"
    source=sh.read_text()
    anchor='    python3 "$ROOT/tools/vectorcraft_android1_trackpad.py" "$SRC/vendor/winit" --winit'
    source=once(source,anchor,anchor+'\n    python3 "$ROOT/tools/vectorcraft_glass_pan_source.py" "$SRC/vendor/winit" --winit',
                "native post-trackpad vendoring hook")
    sh.write_text(source)
    print("PASS: final builder applies glass source tag AFTER native trackpad winit overlay")


def probe(root: Path) -> None:
    with TemporaryDirectory(prefix="vectorcraft-glass-probe-") as directory:
        temp=Path(directory)
        for relative in ("src/platform_impl/android/mod.rs","src/platform/android.rs"):
            output=temp/relative
            output.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(root/relative,output)
        patch_native(temp)
        source=(temp/"src/platform_impl/android/mod.rs").read_text()
        api=(temp/"src/platform/android.rs").read_text()
        assert source.count(GLASS_MARKER)==1
        assert api.count("pub fn vc_glass_pan_take() -> usize")==1
        assert "GestureStep::Pinch(factor)" in source
        assert "PadGesture::Scroll" in source
        print("PASS: source probe proves actual glass wheel path tagged, native touchpad and pinch preserved")


if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("usage: script ROOT --staged|--winit|--install-hook|--probe")
    root=Path(sys.argv[1]); option=sys.argv[2]
    if option=="--staged": patch_staged(root)
    elif option=="--winit": patch_native(root)
    elif option=="--install-hook": install_hook(root)
    elif option=="--probe": probe(root)
    else: raise SystemExit("unknown operation "+option)
