//! Android-only opt-in in-app updater surface. Generated copies get package/version placeholders.
use android_activity::AndroidApp;
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JValue}};

const APP: &str = "__APP__";
const INSTALLED_TAG: &str = "__INSTALLED_TAG__";
const TARGET_PACKAGE: &str = "__TARGET_PACKAGE__";

fn invoke(android: &AndroidApp, method: &str) {
    let vm = unsafe { JavaVM::from_raw(android.vm_as_ptr() as *mut _) };
    let raw = android.activity_as_ptr() as jni::sys::jobject;
    let result = vm.attach_current_thread(|env| -> jni::errors::Result<()> {
        let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
        let app = JObject::from(env.new_string(APP)?);
        let tag = JObject::from(env.new_string(INSTALLED_TAG)?);
        let target = JObject::from(env.new_string(TARGET_PACKAGE)?);
        let args = [
            JValue::Object(&activity),
            JValue::Object(&app),
            JValue::Object(&tag),
            JValue::Object(&target),
        ];
        match method {
            "check" => { env.call_static_method(
                jni_str!("__JAVA_CLASS__"), jni_str!("check"),
                jni_sig!("(Landroid/app/Activity;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V"),
                &args,
            )?; }
            "test" => { env.call_static_method(
                jni_str!("__JAVA_CLASS__"), jni_str!("testDownload"),
                jni_sig!("(Landroid/app/Activity;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V"),
                &args,
            )?; }
            "startup" => { env.call_static_method(
                jni_str!("__JAVA_CLASS__"), jni_str!("startup"),
                jni_sig!("(Landroid/app/Activity;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V"),
                &args,
            )?; }
            "toggle" => { env.call_static_method(
                jni_str!("__JAVA_CLASS__"), jni_str!("toggleStartup"),
                jni_sig!("(Landroid/app/Activity;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V"),
                &args,
            )?; }
            _ => {}
        }
        Ok(())
    });
    if let Err(error) = result {
        log::error!("Android updater JNI {} failed: {}", method, error);
    }
}

/// The approved Wc/Gc icon menu queues a one-shot command in egui's context.
/// No floating button, `egui::Area`, persistent popup or canvas-overlay window is created.
/// This runs after the app's own ribbon UI renders, so menu clicks work the same frame.
pub fn show_ui(ctx: &egui::Context, android: &AndroidApp, _open: &mut bool, initialized: &mut bool) {
    if !*initialized {
        *initialized = true;
        invoke(android, "startup");
    }

    let action = ctx.data_mut(|data| {
        let id = egui::Id::new("artcraft.updater.action");
        let current = data.get_temp::<String>(id).unwrap_or_default();
        data.remove::<String>(id);
        current
    });
    match action.as_str() {
        "check" => invoke(android, "check"),
        "test" => invoke(android, "test"),
        "toggle" => invoke(android, "toggle"),
        "" => {}
        unknown => log::warn!("Unknown in-app updater menu action: {}", unknown),
    }
}
