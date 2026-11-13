//! Android-only JNI boundary. Kept outside CADCraft UI's forbid(unsafe_code).
//! Never call application FindClass from a native render thread: that thread
//! cannot resolve custom Java classes through Android's boot classloader.
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JString}};

fn with_activity<R: Default>(f: impl FnOnce(&mut jni::JNIEnv<'_>, &JObject<'_>)
    -> jni::errors::Result<R>) -> R
{
    let context = ndk_context::android_context();
    let vm = unsafe { JavaVM::from_raw(context.vm() as *mut _) };
    vm.attach_current_thread(|env| -> jni::errors::Result<R> {
        let raw = context.context() as jni::sys::jobject;
        // The Activity is a process-owned global reference.
        let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
        let result = f(env, &activity);
        if result.is_err() && env.exception_check().unwrap_or(false) {
            let _ = env.exception_describe();
            let _ = env.exception_clear();
        }
        result
    }).unwrap_or_default()
}

/// Java dispatch on the Activity itself, which owns the application classloader.
pub fn check_updates() {
    with_activity::<()>(|env, activity| {
        env.call_method(activity, jni_str!("cadCheckUpdates"), jni_sig!("()V"), &[])?;
        Ok(())
    });
}

/// Java validates an actual device name, never a keyboard source heuristic.
pub fn stylus_device_ids() -> Vec<i32> {
    with_activity(|env, activity| {
        let value = env.call_method(activity, jni_str!("cadStylusDeviceIds"),
            jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
        if value.is_null() { return Ok(Vec::new()); }
        let str_value = JString::cast_local(env, value)?;
        let ids: String = str_value.try_to_string(env)?;
        Ok(ids.split(',').filter_map(|v| v.parse::<i32>().ok()).collect())
    })
}
