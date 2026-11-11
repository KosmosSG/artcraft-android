
// Separate, opt-in native input owner for the HONOR Magic-Pencil 4s.
// Android Java validates the exact device name, and supplies matching IDs.
// Unrecognized IDs (including a physical keyboard) NEVER reach this queue.
#[cfg(feature = "native-activity")]
struct VcStylusNativeKeys {
    enabled: bool,
    allowed_ids: Vec<i32>,
    events: Vec<u8>,
    last_single: Option<std::time::Instant>,
    last_double: Option<std::time::Instant>,
}
#[cfg(feature = "native-activity")]
static VC_STYLUS_NATIVE_KEYS: std::sync::Mutex<VcStylusNativeKeys> =
    std::sync::Mutex::new(VcStylusNativeKeys {
        enabled: false,
        allowed_ids: Vec::new(),
        events: Vec::new(),
        last_single: None,
        last_double: None,
    });

#[cfg(feature = "native-activity")]
pub fn vc_stylus_configure(enabled: bool, ids: &[i32]) {
    if let Ok(mut state) = VC_STYLUS_NATIVE_KEYS.lock() {
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
pub fn vc_stylus_native_capture(device: i32, code: i32, action: i32, repeat: i32) -> bool {
    let Ok(mut state) = VC_STYLUS_NATIVE_KEYS.lock() else { return false };
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
            log::info!("VcStylusWheel: validated native pen button code={code} device={device}");
        }
    }
    true
}

#[cfg(feature = "native-activity")]
pub fn vc_stylus_native_take() -> Vec<u8> {
    if let Ok(mut state) = VC_STYLUS_NATIVE_KEYS.lock() {
        std::mem::take(&mut state.events)
    } else {
        Vec::new()
    }
}
