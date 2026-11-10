"""VectorCraft v0.23 android.1: own Android 14+ native touchpad axes.

Stage AFTER Android.25 reference restore. Fail closed on unknown pinned winit.
Keep touchscreen/stylus, typing, keyboard, menus, fonts, update/signing intact.
"""
from pathlib import Path
import shutil
import sys

ORIGINAL = '                let pad_gesture = match motion_event.classification() {'
END = '\n                match motion_event.action() {\n                    // Hover:'

def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Unreviewed Android trackpad source anchor ({source.count(old)}): {old[:100]}")
    return source.replace(old, new, 1)

def patch_winit(root: Path, math_source: Path):
    module = root / 'src/platform_impl/android/mod.rs'
    source = module.read_text()
    assert source.count(ORIGINAL) == 1 and source.count(END) == 1
    a = source.index(ORIGINAL)
    b = source.index(END, a)
    original = source[a:b]
    for anchor in ('Classification::TwoFingerSwipe', 'Classification::Pinch',
                   'MotionAction::Move', 'pad_spread = Some(current)',
                   'event::WindowEvent::MouseWheel', 'event::WindowEvent::PinchGesture'):
        assert anchor in original, f"Missing pinned reference: {anchor}"
    source = once(source, 'mod device_kind;\n', 'mod device_kind;\nmod vectorcraft_pad_math;\n')
    source = once(source,
        '    pad_spread: Option<f64>,\n    modifiers_state: ModifiersState,',
        '    pad_spread: Option<f64>,\n'
        '    vc_pad_detector: vectorcraft_pad_math::Detector,\n'
        '    vc_pad_active: bool,\n'
        '    vc_pad_device: Option<i32>,\n'
        '    vc_pad_scale_previous: f64,\n'
        '    vc_pad_scale_confirmed: bool,\n'
        '    modifiers_state: ModifiersState,')
    source = once(source,
        '            pad_spread: None,\n            modifiers_state: ModifiersState::empty(),',
        '            pad_spread: None,\n'
        '            vc_pad_detector: vectorcraft_pad_math::Detector::default(),\n'
        '            vc_pad_active: false,\n'
        '            vc_pad_device: None,\n'
        '            vc_pad_scale_previous: 0.0,\n'
        '            vc_pad_scale_confirmed: false,\n'
        '            modifiers_state: ModifiersState::empty(),')
    source = source[:source.index(ORIGINAL)] + NEW_ROUTER + source[source.index(END, source.index(ORIGINAL)):]
    assert ORIGINAL not in source
    module.write_text(source)
    math_target = root / 'src/platform_impl/android/vectorcraft_pad_math.rs'
    if math_target.exists():
        raise ValueError("Trackpad math file already exists; refusing duplicate patch")
    shutil.copyfile(math_source, math_target)
    platform = root / 'src/platform/android.rs'
    ext = platform.read_text()
    if 'vc_pad_diagnostics' in ext:
        raise ValueError("Native trackpad counters already installed")
    platform.write_text(ext + DIAGNOSTICS)
    print("PASS: VectorCraft own native API 34 axes 50/51/52, 2-pointer fallback, suppression and aggregated route counts")

NEW_ROUTER = r'''
                // VectorCraft's own HONOR trackpad path. Android API 34+
                // provides pixel scroll distances (50, 51) and an INCREMENTAL
                // pinch scale (52) on pointer zero. The published reference
                // ignores these and incorrectly reads single-cursor movement
                // or two-pointer spread; it can produce no zoom or jerky pans.
                // The android-activity 0.6 Axis enum predates API 34, but
                // Axis::from(u32) supports forward-compatible numeric axes.
                let reported = match motion_event.classification() {
                    Classification::TwoFingerSwipe => PadGesture::Scroll,
                    Classification::Pinch => PadGesture::Pinch,
                    _ => PadGesture::None,
                };
                let pointer_count = motion_event.pointer_count();
                let source_device = motion_event.device_id();
                // Some MagicOS pads report the generic Mouse tool for both
                // fingers, so two pointer-class pointers also qualify.
                let is_two_pad = (pointer_class || touchpad) && pointer_count == 2;
                // Android 14+ trackpad gestures may be a *single-pointer*
                // stream with several historical relative-axis samples.
                // Official docs require processing EVERY historical sample,
                // then the current sample: our old code dropped all history.
                let mut native_axes = vectorcraft_pad_math::AxisTotals::default();
                let mut historical_pinch_samples = 0u32;
                if pointer_class || touchpad || reported != PadGesture::None {
                    if let Some(p) = motion_event.pointers().next() {
                        for history in p.history() {
                            let before = native_axes.zoom_count;
                            native_axes.add(
                                history.axis_value(Axis::from(50u32)) as f64,
                                history.axis_value(Axis::from(51u32)) as f64,
                                history.axis_value(Axis::from(52u32)) as f64);
                            if native_axes.zoom_count > before {
                                historical_pinch_samples += 1;
                            }
                        }
                        native_axes.add(
                            p.axis_value(Axis::from(50u32)) as f64,
                            p.axis_value(Axis::from(51u32)) as f64,
                            p.axis_value(Axis::from(52u32)) as f64);
                    }
                }
                let has_pad_axes = native_axes.has_data();
                if reported == PadGesture::Pinch { crate::platform::android::vc_pad_note(5); }
                if reported == PadGesture::Scroll { crate::platform::android::vc_pad_note(6); }
                if historical_pinch_samples > 0 { crate::platform::android::vc_pad_note(7); }
                if touchpad && !has_pad_axes && reported == PadGesture::None
                    && motion_event.action() == MotionAction::Move {
                    crate::platform::android::vc_pad_note(8);
                }
                let active_here = self.vc_pad_active
                    && self.vc_pad_device == Some(source_device);
                // A stale classified packet must not steal later one-finger
                // cursor motion. Unclassified 1-finger move terminates session.
                if active_here && pointer_count < 2
                    && reported == PadGesture::None && !has_pad_axes
                    && motion_event.action() == MotionAction::Move {
                    self.vc_pad_active = false;
                    self.vc_pad_device = None;
                    self.vc_pad_detector.reset();
                    self.vc_pad_scale_previous = 0.0;
                    self.vc_pad_scale_confirmed = false;
                    self.pad_position = None;
                    self.pad_spread = None;
                }
                let active_here = self.vc_pad_active
                    && self.vc_pad_device == Some(source_device);
                // CLASSIFICATION_PINCH / TWO_FINGER_SWIPE refer to a touchpad
                // even if an OEM's source/tool flags confused device_kind.
                // Never intercept ordinary touchscreen/stylus pointer moves.
                // Recognize two-finger trackpad packets even before MagicOS assigns
                // an explicit Swipe classification. Never hijack touchscreen
                // or stylus events: require touchpad source or pointer-class.
                let candidate = reported != PadGesture::None ||
                    ((pointer_class || touchpad) && (is_two_pad || has_pad_axes || active_here));
                if candidate {
                    let action = motion_event.action();
                    if matches!(action, MotionAction::Up | MotionAction::PointerUp | MotionAction::Cancel) {
                        self.vc_pad_active = false;
                        self.vc_pad_device = None;
                        self.vc_pad_detector.reset();
                        self.vc_pad_scale_previous = 0.0;
                        self.vc_pad_scale_confirmed = false;
                        self.pad_position = None;
                        self.pad_spread = None;
                        return input_status;
                    }
                    if !self.vc_pad_active || self.vc_pad_device != Some(source_device) {
                        self.vc_pad_active = true;
                        self.vc_pad_device = Some(source_device);
                        self.vc_pad_detector.reset();
                        self.vc_pad_scale_previous = 0.0;
                        self.vc_pad_scale_confirmed = false;
                        self.pad_position = None;
                        self.pad_spread = None;
                        // An initial one-finger pointer press may have reached
                        // egui before Android classified the second finger.
                        // Release it ONCE so a two-finger pan cannot select art.
                        callback(event::Event::WindowEvent {
                            window_id,
                            event: event::WindowEvent::MouseInput {
                                device_id,
                                state: event::ElementState::Released,
                                button: event::MouseButton::Left,
                            },
                        }, self.window_target());
                    }
                    if matches!(action, MotionAction::Down | MotionAction::PointerDown) {
                        self.pad_position = motion_event.pointers().next()
                            .map(|p| pointer_position(&p));
                        self.pad_spread = pointer_spread(&motion_event);
                        if pointer_count == 2 {
                            let mut iter = motion_event.pointers();
                            if let (Some(p), Some(q)) = (iter.next(), iter.next()) {
                                let x = (p.x() as f64 + q.x() as f64) * 0.5;
                                let y = (p.y() as f64 + q.y() as f64) * 0.5;
                                let spread = pointer_spread(&motion_event).unwrap_or(0.0);
                                self.vc_pad_detector.step(vectorcraft_pad_math::Sample { x, y, spread });
                            }
                        }
                        return input_status;
                    }
                    if matches!(action, MotionAction::Move | MotionAction::Scroll) {
                        let first = motion_event.pointers().next();
                        let position = first.as_ref().map(|p| pointer_position(p));
                        // Gesture axes are already relative to PREVIOUS event.
                        // Never smooth/replay them or multiply by wheel notches.
                        // Historical axes were accumulated above exactly
                        // once. For zoom, relative factors multiply, so the
                        // stable representation is sum(log(scale)).
                        let axis_x = native_axes.pan_x;
                        let axis_y = native_axes.pan_y;
                        let axis_scale = native_axes.scale();
                        let mut pan: Option<(f64, f64, usize)> = None;
                        let mut zoom: Option<(f64, usize)> = None;
                        // Inspect true two-pointer geometry in ALL classified
                        // modes: some MagicOS pinch gestures are continually
                        // reported as TwoFingerSwipe, never Classification::Pinch.
                        // The detector is hysteretic so a normal two-finger pan
                        // cannot flip to zoom from ordinary fingertip drift.
                        let inference = if is_two_pad {
                            let mut pair = motion_event.pointers();
                            if let (Some(a), Some(b)) = (pair.next(), pair.next()) {
                                self.vc_pad_detector.step(vectorcraft_pad_math::Sample {
                                    x: (a.x() as f64 + b.x() as f64) * 0.5,
                                    y: (a.y() as f64 + b.y() as f64) * 0.5,
                                    spread: pointer_spread(&motion_event).unwrap_or(0.0),
                                })
                            } else { vectorcraft_pad_math::Step::None }
                        } else { vectorcraft_pad_math::Step::None };
                        // API 34 scale is the factor SINCE the preceding packet,
                        // not a cumulative absolute zoom. Do not let a single
                        // +/-0.2% noise sample turn scrolling into zooming.
                        // A convincing 1.2% sample or two consecutive smaller
                        // same-direction changes are deliberate zoom intent.
                        let valid_scale = axis_scale.is_finite()
                            && (0.4..=2.5).contains(&axis_scale);
                        let scale_change = if valid_scale { axis_scale - 1.0 } else { 0.0 };
                        let successive_scale = scale_change.abs() >= 0.0025
                            && self.vc_pad_scale_previous.abs() >= 0.0025
                            && scale_change.signum() == self.vc_pad_scale_previous.signum();
                        let native_pinch = valid_scale && scale_change.abs() > 0.0003
                            && (reported == PadGesture::Pinch
                                || self.vc_pad_scale_confirmed
                                || scale_change.abs() >= 0.012
                                || (historical_pinch_samples >= 2
                                    && scale_change.abs() >= 0.004)
                                || successive_scale);
                        self.vc_pad_scale_previous = scale_change;
                        if native_pinch { self.vc_pad_scale_confirmed = true; }
                        let geometry_pinch = matches!(inference, vectorcraft_pad_math::Step::Pinch(_));
                        let locked_geometry_pinch = is_two_pad
                            && self.vc_pad_detector.mode() == vectorcraft_pad_math::Mode::Pinch;
                        // Prioritize real pinch packets even when the platform
                        // classified the entire stream as a swipe. Once pinch
                        // wins, ignore parallel scroll axes for this packet.
                        if native_pinch {
                            zoom = Some((axis_scale, 1));
                        } else if let vectorcraft_pad_math::Step::Pinch(factor) = inference {
                            zoom = Some((factor, 3));
                        } else if !self.vc_pad_scale_confirmed && !locked_geometry_pinch {
                            match reported {
                                PadGesture::Pinch => {
                                    if let Some(spread) = pointer_spread(&motion_event) {
                                        if let Some(last) = self.pad_spread {
                                            if last > 0.0 { zoom = Some((spread / last, 3)); }
                                        }
                                    }
                                }
                                PadGesture::Scroll | PadGesture::None => {
                                    if axis_x.is_finite() && axis_y.is_finite()
                                        && (axis_x != 0.0 || axis_y != 0.0) {
                                        pan = Some((axis_x, axis_y, 0));
                                    } else if reported == PadGesture::Scroll {
                                        if let Some(p) = position {
                                            if let Some(last) = self.pad_position {
                                                pan = Some((p.x-last.x, p.y-last.y, 2));
                                            }
                                        }
                                    } else if let vectorcraft_pad_math::Step::Pan(x,y) = inference {
                                        pan = Some((x,y,2));
                                    }
                                }
                            }
                        }
                        self.pad_position = position;
                        self.pad_spread = pointer_spread(&motion_event);
                        if let Some((x,y,route)) = pan {
                            if x.is_finite() && y.is_finite() && (x != 0.0 || y != 0.0)
                                && x.abs() <= 1024.0 && y.abs() <= 1024.0 {
                                crate::platform::android::vc_pad_note(route);
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::MouseWheel {
                                        device_id,
                                        delta: event::MouseScrollDelta::PixelDelta(
                                            PhysicalPosition { x, y }),
                                        phase: event::TouchPhase::Moved,
                                    },
                                }, self.window_target());
                            } else {
                                crate::platform::android::vc_pad_note(4);
                            }
                        } else if let Some((factor,route)) = zoom {
                            if factor.is_finite() && (0.4..=2.5).contains(&factor)
                                && (factor-1.0).abs() > 0.0001 {
                                crate::platform::android::vc_pad_note(route);
                                callback(event::Event::WindowEvent {
                                    window_id,
                                    event: event::WindowEvent::PinchGesture {
                                        device_id,
                                        delta: factor.ln(),
                                        phase: event::TouchPhase::Moved,
                                    },
                                }, self.window_target());
                            } else {
                                crate::platform::android::vc_pad_note(4);
                            }
                        } else {
                            crate::platform::android::vc_pad_note(4);
                        }
                        // Never fall through to MouseInput, Touch or normal
                        // ACTION_SCROLL: no duplicate pan/pinch/selection.
                        return input_status;
                    }
                    return input_status;
                }
'''
DIAGNOSTICS = r'''
// VectorCraft experimental native touchpad counters (no pointer positions,
// documents, touch coordinates, typed text or device identifiers collected).
static VC_PAD_AXIS_PAN: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_PAD_AXIS_ZOOM: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_PAD_FALLBACK_PAN: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_PAD_FALLBACK_ZOOM: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_PAD_NO_DATA: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
// Source/classification counters, intentionally no coordinates or file data.
static VC_PAD_CLASSIFIED_PINCH: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_PAD_CLASSIFIED_SCROLL: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_PAD_HISTORICAL_ZOOM: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_PAD_UNCLASSIFIED_NO_AXIS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
pub(crate) fn vc_pad_note(route: usize) {
    use std::sync::atomic::Ordering::Relaxed;
    let counter = match route {
        0 => &VC_PAD_AXIS_PAN,
        1 => &VC_PAD_AXIS_ZOOM,
        2 => &VC_PAD_FALLBACK_PAN,
        3 => &VC_PAD_FALLBACK_ZOOM,
        4 => &VC_PAD_NO_DATA,
        5 => &VC_PAD_CLASSIFIED_PINCH,
        6 => &VC_PAD_CLASSIFIED_SCROLL,
        7 => &VC_PAD_HISTORICAL_ZOOM,
        8 => &VC_PAD_UNCLASSIFIED_NO_AXIS,
        _ => &VC_PAD_NO_DATA,
    };
    counter.fetch_add(1, Relaxed);
}
// Session-scoped diagnostic counters: clear only on a user-initiated capture.
pub fn vc_pad_reset_diagnostics() {
    use std::sync::atomic::Ordering::Relaxed;
    for counter in [&VC_PAD_AXIS_PAN, &VC_PAD_AXIS_ZOOM,
                    &VC_PAD_FALLBACK_PAN, &VC_PAD_FALLBACK_ZOOM,
                    &VC_PAD_NO_DATA, &VC_PAD_CLASSIFIED_PINCH,
                    &VC_PAD_CLASSIFIED_SCROLL, &VC_PAD_HISTORICAL_ZOOM,
                    &VC_PAD_UNCLASSIFIED_NO_AXIS] {
        counter.store(0, Relaxed);
    }
}
pub fn vc_pad_diagnostics() -> [u64; 9] {
    use std::sync::atomic::Ordering::Relaxed;
    [VC_PAD_AXIS_PAN.load(Relaxed), VC_PAD_AXIS_ZOOM.load(Relaxed),
     VC_PAD_FALLBACK_PAN.load(Relaxed), VC_PAD_FALLBACK_ZOOM.load(Relaxed),
     VC_PAD_NO_DATA.load(Relaxed), VC_PAD_CLASSIFIED_PINCH.load(Relaxed),
     VC_PAD_CLASSIFIED_SCROLL.load(Relaxed), VC_PAD_HISTORICAL_ZOOM.load(Relaxed),
     VC_PAD_UNCLASSIFIED_NO_AXIS.load(Relaxed)]
}
'''

def patch_staged(root: Path):
    # Extend the *existing* diagnostic report instead of adding a new UI,
    # export action, user-data recorder or a permanent settings row.
    rust = root / 'adapters/vectorcraft/src/lib.rs'
    content = rust.read_text()
    old = '                match self.bridge.copy_diagnostic_report(&report) {'
    new = '''                let pad=winit::platform::android::vc_pad_diagnostics();
                let report=format!("{report}\\nvc_native_trackpad_axis_pan={}\\nvc_native_trackpad_axis_pinch={}\\nvc_native_trackpad_fallback_pan={}\\nvc_native_trackpad_fallback_pinch={}\\nvc_native_trackpad_no_data={}\\nvc_native_trackpad_classified_pinch={}\\nvc_native_trackpad_classified_scroll={}\\nvc_native_trackpad_historical_zoom_packets={}\\nvc_native_trackpad_unclassified_no_axis={}\\n",pad[0],pad[1],pad[2],pad[3],pad[4],pad[5],pad[6],pad[7],pad[8]);
                match self.bridge.copy_diagnostic_report(&report) {'''
    content = once(content, old, new)
    content = once(content,
        'VectorCraft Android.15 Diagnostic Session',
        'VectorCraft v0.23.0-android.4 Diagnostic Session')
    content = once(content,
        '            if vc_diag_start {',
        '            if vc_diag_start {\n'
        '                winit::platform::android::vc_pad_reset_diagnostics();')
    rust.write_text(content)
    print("PASS: existing private diagnostic Copy Report includes aggregate native trackpad routes")

def install_build_hook(root: Path, patch_source: Path, math_source: Path):
    tools = root / 'tools'
    tool = tools / 'vectorcraft_android1_trackpad.py'
    math = tools / 'vectorcraft_pad_math.rs'
    if tool.exists() or math.exists():
        raise ValueError("Trackpad hook already installed")
    shutil.copyfile(patch_source, tool)
    shutil.copyfile(math_source, math)
    sh = root / 'lib/build-common.sh'
    s = sh.read_text()
    anchor = 'python3 "$ROOT/tools/vectorcraft_android25.py" "$SRC/vendor/winit" --restore-reference'
    s = once(s, anchor, anchor + '\n    python3 "$ROOT/tools/vectorcraft_android1_trackpad.py" "$SRC/vendor/winit" --winit')
    sh.write_text(s)
    print("PASS: own trackpad hook runs after pinned Android.25 final vendor restore")

if __name__ == '__main__':
    me=Path(__file__).resolve()
    root=Path(sys.argv[1])
    if '--winit' in sys.argv[2:]:
        math=me.with_name('vectorcraft_pad_math.rs')
        patch_winit(root,math)
    elif '--install-hook' in sys.argv[2:]:
        math=me.with_name('native_pad_math.rs')
        install_build_hook(root,me,math)
    else:
        patch_staged(root)
