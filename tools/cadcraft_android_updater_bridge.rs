//! Isolated Android JNI boundary, separate from CADCraft UI forbid(unsafe_code).
//! Resolve Java methods through the Activity instance, not FindClass from Rust.
use jni::{JavaVM, objects::{JObject, JString, JValue}};

// The old JNI bridge returned empty Vec/string on all failures, obscuring
// the real MagicOS problem. Keep a short diagnostic visible in the TEST UI.
static JNI_LAST_FAILURE: std::sync::Mutex<Option<String>> =
    std::sync::Mutex::new(None);
fn jni_failure(reason: String) {
    if let Ok(mut slot) = JNI_LAST_FAILURE.lock() {
        if slot.as_ref() != Some(&reason) { *slot = Some(reason); }
    }
}
pub fn stylus_bridge_failure() -> Option<String> {
    JNI_LAST_FAILURE.lock().ok().and_then(|slot| slot.clone())
}

fn with_activity<R: Default>(f: impl FnOnce(&mut jni::JNIEnv<'_>, &JObject<'_>)
    -> jni::errors::Result<R>) -> R
{
    let context = ndk_context::android_context();
    // SAF Activity is owned by Android for the entire native application lifetime.
    let vm = match unsafe { JavaVM::from_raw(context.vm() as *mut _) } {
        Ok(vm) => vm,
        Err(err) => {
            jni_failure(format!("JavaVM unavailable: {err}"));
            return R::default();
        }
    };
    let mut env = match vm.attach_current_thread() {
        Ok(env) => env,
        Err(err) => {
            jni_failure(format!("Thread attach failed: {err}"));
            return R::default();
        }
    };
    let activity = std::mem::ManuallyDrop::new(unsafe { JObject::from_raw(context.context() as jni::sys::jobject) });
    // Do not drop the borrowed Activity as if it were a local JNI reference.
    let result = f(&mut env, &activity);
    if env.exception_check().unwrap_or(false) {
        if let Ok(cause) = env.exception_occurred() {
            let _ = env.exception_clear();
            let detail = env.call_method(&cause, "toString", "()Ljava/lang/String;", &[])
                .and_then(|v| v.l())
                .and_then(|v| env.get_string(&JString::from(v)).map(String::from))
                .unwrap_or_else(|_| "unavailable".into());
            jni_failure(format!("Activity Java exception: {detail}"));
        } else {
            let _ = env.exception_clear();
            jni_failure("Activity Java exception (details unavailable)".into());
        }
    }
    match result {
        Ok(value) => value,
        Err(err) => {
            jni_failure(format!("Activity method unavailable: {err}"));
            R::default()
        }
    }
}

pub fn check_updates() {
    with_activity::<()>(|env, activity| {
        env.call_method(&activity, "cadCheckUpdates", "()V", &[])?;
        Ok(())
    });
}

pub fn show_pen_diagnostics() {
    with_activity::<()>(|env, activity| {
        env.call_method(activity, "cadStylusShowInputStatus", "()V", &[])?;
        Ok(())
    });
}

/// Read-only diagnostics for the in-app egui test window. If Android/JNI
/// cannot resolve the Activity method, return empty (the UI explains this).
pub fn stylus_status() -> String {
    with_activity(|env, activity| {
        let value = env.call_method(activity, "cadStylusSnapshot",
            "()Ljava/lang/String;", &[])?.l()?;
        if value.is_null() { return Ok(String::new()); }
        let status: String = env.get_string(&JString::from(value))?.into();
        Ok(status)
    })
}

pub fn stylus_device_ids() -> Vec<i32> {
    with_activity(|env, activity| {
        let value = env.call_method(&activity, "cadStylusDeviceIds",
            "()Ljava/lang/String;", &[])?.l()?;
        if value.is_null() { return Ok(Vec::new()); }
        let ids: String = env.get_string(&JString::from(value))?.into();
        Ok(ids.split(',').filter_map(|v| v.parse::<i32>().ok()).collect())
    })
}

pub fn stylus_set_enabled(enabled: bool) {
    with_activity::<()>(|env, activity| {
        env.call_method(activity, "cadStylusSetEnabled", "(Z)V",
            &[JValue::Bool(enabled as u8)])?;
        Ok(())
    });
}

/// PhotoCraft-style Java input fallback: the same Magic-Pencil side-button
/// can reach Activity or hidden IME instead of the NativeActivity input queue.
/// Java validates its exact hardware name, so keyboard arrows are never read.
pub fn stylus_poll() -> Vec<i32> {
    with_activity(|env, activity| {
        let mut events = Vec::new();
        for _ in 0..12 {
            let code = env.call_method(activity, "cadStylusPoll", "()I", &[])?.i()?;
            if code == 0 { break; }
            if code == 19 || code == 20 { events.push(code); }
        }
        Ok(events)
    })
}


/// Direct Java-to-native event handoff for the *verified* Magic-Pencil
/// KEYCODE_DPAD_DOWN/UP release. The Activity checks the InputDevice name
/// BEFORE invoking this method; generic keyboard arrows never reach it.
/// This is intentionally independent of JVM polling from the render thread.
static PEN_DIRECT: std::sync::atomic::AtomicI32 =
    std::sync::atomic::AtomicI32::new(0);

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_artcraft_cadcraft_test_CadCraftActivity_cadWheelButtonNative(
    _env: jni::JNIEnv<'_>,
    _activity: JObject<'_>,
    code: jni::sys::jint,
) {
    if code == 19 || code == 20 {
        PEN_DIRECT.store(code, std::sync::atomic::Ordering::Release);
    }
}

pub fn stylus_take_direct() -> Vec<i32> {
    match PEN_DIRECT.swap(0, std::sync::atomic::Ordering::AcqRel) {
        19 => vec![19],
        20 => vec![20],
        _ => Vec::new(),
    }
}

/// Dedicated visual stylus hover channel. Coordinates are Android window pixels.
/// Never forwards the stylus events as touches or fake mouse clicks.
static PEN_HOVER: std::sync::Mutex<Option<(f32, f32)>> =
    std::sync::Mutex::new(None);

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_artcraft_cadcraft_test_CadCraftActivity_cadStylusHoverNative(
    _env: jni::JNIEnv<'_>,
    _activity: JObject<'_>,
    x: jni::sys::jfloat,
    y: jni::sys::jfloat,
    action: jni::sys::jint,
    device_id: jni::sys::jint,
) {
    // Java has already verified TOOL_TYPE_STYLUS; pass its transient device
    // ID to the native input gate without ever trusting ordinary key presses.
    android_activity::cad_stylus_observe_hover_device(device_id, action);
    if let Ok(mut hover) = PEN_HOVER.lock() {
        match action {
            7 | 9 if x.is_finite() && y.is_finite() => *hover = Some((x, y)),
            0 | 1 | 3 | 10 => *hover = None,
            _ => {}
        }
    }
}

pub fn stylus_hover_pos() -> Option<(f32, f32)> {
    PEN_HOVER.lock().ok().and_then(|hover| *hover)
}


// Device metadata probe uses ONLY system android.view.InputDevice methods,
// avoiding the failing CADCraftActivity JNI route. Never stores numeric IDs.
pub fn stylus_input_device_info(device_id: i32) -> Option<(bool, String)> {
    if device_id <= 0 { return None; }
    let ctx = ndk_context::android_context();
    let vm = match unsafe { JavaVM::from_raw(ctx.vm() as *mut _) } {
        Ok(vm) => vm,
        Err(err) => { jni_failure(format!("InputDevice VM: {err}")); return None; }
    };
    let mut env = match vm.attach_current_thread() {
        Ok(env) => env,
        Err(err) => { jni_failure(format!("InputDevice attach: {err}")); return None; }
    };
    let result = (|| -> jni::errors::Result<(bool, String)> {
        let device = env.call_static_method("android/view/InputDevice", "getDevice",
            "(I)Landroid/view/InputDevice;", &[JValue::Int(device_id)])?.l()?;
        if device.is_null() { return Ok((false, "Device not registered with Android".into())); }
        let name_obj = env.call_method(&device, "getName", "()Ljava/lang/String;", &[])?.l()?;
        let name: String = if name_obj.is_null() { String::new() }
            else { env.get_string(&JString::from(name_obj))?.into() };
        let sources = env.call_method(&device, "getSources", "()I", &[])?.i()?;
        let vendor = env.call_method(&device, "getVendorId", "()I", &[])?.i()?;
        let product = env.call_method(&device, "getProductId", "()I", &[])?.i()?;
        let name_lower = name.to_ascii_lowercase();
        // Strict source/name checks: no generic keyboard names or DPAD buttons
        // are trusted, even when they share device numbers with a pen.
        let magic_pencil = name_lower.contains("magic-pencil")
            || name_lower.contains("magic pencil");
        let named_stylus = name_lower.contains("stylus")
            || name_lower.contains("pencil") || name_lower.contains("honor pen")
            || name_lower.contains("huawei pen");
        let stylus_capable = (sources & 0x0000c000) != 0;
        let verified = magic_pencil || (named_stylus && stylus_capable);
        Ok((verified, format!(
            "ID {device_id}: name={name:?}, sources={sources:#x}, vendor={vendor}, product={product}, pen_verified={verified}"
        )))
    })();
    if env.exception_check().unwrap_or(false) {
        let _ = env.exception_clear();
    }
    match result {
        Ok(value) => Some(value),
        Err(err) => {
            jni_failure(format!("Android InputDevice metadata probe: {err}"));
            None
        }
    }
}
