//! Isolated Android JNI boundary, separate from CADCraft UI forbid(unsafe_code).
//! Resolve Java methods through the Activity instance, not FindClass from Rust.
use jni::{JavaVM, objects::{JObject, JString, JValue}};

fn with_activity<R: Default>(f: impl FnOnce(&mut jni::JNIEnv<'_>, &JObject<'_>)
    -> jni::errors::Result<R>) -> R
{
    let context = ndk_context::android_context();
    // SAF Activity is owned by Android for the entire native application lifetime.
    let vm = match unsafe { JavaVM::from_raw(context.vm() as *mut _) } {
        Ok(vm) => vm,
        Err(_) => return R::default(),
    };
    let mut env = match vm.attach_current_thread() {
        Ok(env) => env,
        Err(_) => return R::default(),
    };
    let activity = std::mem::ManuallyDrop::new(unsafe { JObject::from_raw(context.context() as jni::sys::jobject) });
    // Do not drop the borrowed Activity as if it were a local JNI reference.
    let result = f(&mut env, &activity);
    if env.exception_check().unwrap_or(false) {
        let _ = env.exception_describe();
        let _ = env.exception_clear();
    }
    result.unwrap_or_default()
}

pub fn check_updates() {
    with_activity::<()>(|env, activity| {
        env.call_method(&activity, "cadCheckUpdates", "()V", &[])?;
        Ok(())
    });
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
