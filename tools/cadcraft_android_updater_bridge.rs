//! Android-only JNI boundary for CADCraft's user-invoked updater.
//! This is intentionally separate from cadcraft-ui-egui (forbid unsafe).
pub fn check_updates() {
    let context = ndk_context::android_context();
    // SAFETY: ndk-context provides the process-owned live Android VM and
    // activity pointers; this function does not take ownership of either.
    let vm = unsafe { jni::JavaVM::from_raw(context.vm() as *mut _) };
    let result = vm.attach_current_thread(|env| -> jni::errors::Result<()> {
        let activity_raw = context.context() as jni::sys::jobject;
        // SAFETY: the Android activity global reference remains owned by the
        // application for this synchronous Java call.
        let activity = unsafe { env.as_cast_raw::<jni::objects::JObject>(&activity_raw)? };
        env.call_static_method(
            jni::jni_str!("com/artcraft/updater/UpdateCheck"),
            jni::jni_str!("checkNow"),
            jni::jni_sig!("(Landroid/app/Activity;)V"),
            &[jni::objects::JValue::Object(&activity)],
        )?;
        Ok(())
    });
    if let Err(error) = result {
        eprintln!("CADCraft updater JNI call failed: {error}");
    }
}
