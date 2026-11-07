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
            "download" => { env.call_static_method(
                jni_str!("__JAVA_CLASS__"), jni_str!("downloadAvailable"),
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

/// Lightweight read-only JNI state poll. Never downloads or checks network on the frame thread.
fn poll_menu_state(ctx: &egui::Context, android: &AndroidApp) {
    let vm = unsafe { JavaVM::from_raw(android.vm_as_ptr() as *mut _) };
    let raw = android.activity_as_ptr() as jni::sys::jobject;
    let result = vm.attach_current_thread(|env| -> jni::errors::Result<String> {
        let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
        let app = JObject::from(env.new_string(APP)?);
        let tag = JObject::from(env.new_string(INSTALLED_TAG)?);
        let target = JObject::from(env.new_string(TARGET_PACKAGE)?);
        let value = env.call_static_method(
            jni_str!("__JAVA_CLASS__"), jni_str!("menuState"),
            jni_sig!("(Landroid/app/Activity;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"),
            &[JValue::Object(&activity), JValue::Object(&app),
              JValue::Object(&tag), JValue::Object(&target)],
        )?.l()?;
        let state = jni::objects::JString::cast_local(env, value)?;
        state.try_to_string(env)
    });
    match result {
        Ok(json) => match serde_json::from_str::<serde_json::Value>(&json) {
            Ok(value) => ctx.data_mut(|data| {
                data.insert_temp(egui::Id::new("artcraft.updater.startup"),
                    value.get("startup").and_then(|v| v.as_bool()).unwrap_or(false));
                data.insert_temp(egui::Id::new("artcraft.updater.available"),
                    value.get("available").and_then(|v| v.as_bool()).unwrap_or(false));
                data.insert_temp(egui::Id::new("artcraft.updater.diagnostics"),
                    value.get("diagnostics").and_then(|v| v.as_bool()).unwrap_or(false));
                data.insert_temp(egui::Id::new("artcraft.updater.status"),
                    value.get("status").and_then(|v| v.as_str())
                         .unwrap_or("Check GitHub Releases for updates.").to_owned());
            }),
            Err(error) => log::warn!("Updater menu-state JSON invalid: {}", error),
        },
        Err(error) => log::warn!("Updater menu-state JNI failed: {}", error),
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
        "download" => invoke(android, "download"),
        "test" => invoke(android, "test"),
        "toggle" => invoke(android, "toggle"),
        "" => {}
        unknown => log::warn!("Unknown in-app updater menu action: {}", unknown),
    }

    // Limit JNI state reads to once a second, including when the app is idle.
    let poll_id = egui::Id::new("artcraft.updater.last_menu_poll");
    let should_poll = ctx.data(|data|
        data.get_temp::<std::time::Instant>(poll_id)
            .is_none_or(|when| when.elapsed() >= std::time::Duration::from_secs(1))
    );
    if should_poll {
        poll_menu_state(ctx, android);
        ctx.data_mut(|data| data.insert_temp(poll_id, std::time::Instant::now()));
    }
    ctx.request_repaint_after(std::time::Duration::from_secs(1));
}
