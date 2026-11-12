
// Separate, opt-in native input owner for the HONOR Magic-Pencil 4s.
// Android Java validates the exact device name, and supplies matching IDs.
// Unrecognized IDs (including a physical keyboard) NEVER reach this queue.
#[cfg(feature = "native-activity")]
struct PdfStylusNativeKeys {
    enabled: bool,
    allowed_ids: Vec<i32>,
    events: Vec<u8>,
    last_single: Option<std::time::Instant>,
    last_double: Option<std::time::Instant>,
}
#[cfg(feature = "native-activity")]
static PDF_STYLUS_NATIVE_KEYS: std::sync::Mutex<PdfStylusNativeKeys> =
    std::sync::Mutex::new(PdfStylusNativeKeys {
        enabled: false,
        allowed_ids: Vec::new(),
        events: Vec::new(),
        last_single: None,
        last_double: None,
    });

#[cfg(feature = "native-activity")]
pub fn pdf_stylus_configure(enabled: bool, ids: &[i32]) {
    if let Ok(mut state) = PDF_STYLUS_NATIVE_KEYS.lock() {
        let ids: Vec<i32> = ids.iter().copied().take(16).filter(|id| *id > 0).collect();
        if state.enabled != enabled || state.allowed_ids != ids {
            state.events.clear();
            state.last_single = None;
            state.last_double = None;
        }
        state.enabled = enabled;
        state.allowed_ids = ids;
    }
}

#[cfg(feature = "native-activity")]
pub fn pdf_stylus_native_capture(device: i32, code: i32, action: i32, repeat: i32) -> bool {
    let Ok(mut state) = PDF_STYLUS_NATIVE_KEYS.lock() else { return false };
    if !state.enabled || !state.allowed_ids.contains(&device) || (code != 19 && code != 20) {
        return false;
    }
    // Consume BOTH DOWN and UP, but only the first UP (release) triggers.
    // Otherwise Android's usual DPAD navigation can change open menus.
    if action == 1 && repeat == 0 {
        let now = std::time::Instant::now();
        let last = if code == 19 { state.last_double } else { state.last_single };
        if last.is_none_or(|t| now.duration_since(t) >= std::time::Duration::from_millis(650))
            && state.events.len() < 16 {
            state.events.push(code as u8);
            if code == 19 { state.last_double = Some(now); }
            else { state.last_single = Some(now); }
            log::info!("PdfStylusWheel: validated native pen button code={code} device={device}");
        }
    }
    true
}

#[cfg(feature = "native-activity")]
pub fn pdf_stylus_native_take() -> Vec<u8> {
    if let Ok(mut state) = PDF_STYLUS_NATIVE_KEYS.lock() {
        std::mem::take(&mut state.events)
    } else {
        Vec::new()
    }
}

// Observe pen hover before NativeActivity forwards input to winit. Native input
// can bypass Java View listeners, so neither route may be the sole source.
#[cfg(feature = "native-activity")]
static PDF_PEN_HOVER: std::sync::Mutex<Option<(f32, f32)>> = std::sync::Mutex::new(None);
#[cfg(feature = "native-activity")]
pub fn pdf_stylus_observe_motion(tool: i32, action: i32, x: f32, y: f32) {
    if let Ok(mut hover) = PDF_PEN_HOVER.lock() {
        *hover = if (tool == 2 || tool == 4) && (action == 7 || action == 9)
            && x.is_finite() && y.is_finite() { Some((x, y)) } else { None };
    }
}
#[cfg(feature = "native-activity")]
pub fn pdf_stylus_native_hover() -> Option<(f32, f32)> {
    PDF_PEN_HOVER.lock().ok().and_then(|value| *value)
}
#[cfg(feature = "native-activity")]
pub fn pdf_stylus_clear_hover() {
    if let Ok(mut hover) = PDF_PEN_HOVER.lock() { *hover = None; }
}
#[cfg(all(test, feature = "native-activity"))]
mod hover_tests {
    #[test]
    fn pen_hover_never_survives_contact_exit_or_mouse() {
        for tool in [2, 4] {
            super::pdf_stylus_observe_motion(tool, 9, 12.0, 24.0);
            assert_eq!(super::pdf_stylus_native_hover(), Some((12.0, 24.0)));
            for end in [0, 1, 2, 3, 10] {
                super::pdf_stylus_observe_motion(tool, 7, 30.0, 40.0);
                super::pdf_stylus_observe_motion(tool, end, 30.0, 40.0);
                assert_eq!(super::pdf_stylus_native_hover(), None);
            }
        }
        super::pdf_stylus_observe_motion(3, 7, 1.0, 2.0);
        assert_eq!(super::pdf_stylus_native_hover(), None);
        super::pdf_stylus_observe_motion(2, 7, f32::NAN, 2.0);
        assert_eq!(super::pdf_stylus_native_hover(), None);
        super::pdf_stylus_observe_motion(2, 7, 1.0, 2.0);
        super::pdf_stylus_clear_hover();
        assert_eq!(super::pdf_stylus_native_hover(), None);
    }
}
