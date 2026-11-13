//! Isolated Android JNI boundary, separate from CADCraft UI forbid(unsafe_code).
//! Resolve Java methods through the Activity instance, not FindClass from Rust.
use jni::{JavaVM, objects::{JObject, JString}};

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
        std::mem::forget(activity);
        if value.is_null() { return Ok(Vec::new()); }
        let ids: String = env.get_string(&JString::from(value))?.into();
        Ok(ids.split(',').filter_map(|v| v.parse::<i32>().ok()).collect())
    })
}
