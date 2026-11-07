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

/// Small top-left overlay, preserving the upstream menus and canvas layout.
pub fn show_ui(ctx: &egui::Context, android: &AndroidApp, open: &mut bool, initialized: &mut bool) {
    if !*initialized {
        *initialized = true;
        invoke(android, "startup");
    }
    egui::Area::new(egui::Id::new("artcraft-update-entry"))
        .fixed_pos(egui::pos2(8.0, 56.0))
        .order(egui::Order::Foreground)
        .show(ctx, |ui| {
            if ui.small_button("↻ Updates").clicked() {
                *open = !*open;
            }
        });
    if *open {
        egui::Window::new("App updates")
            .open(open)
            .default_pos(egui::pos2(12.0, 88.0))
            .resizable(false)
            .show(ctx, |ui| {
                ui.label(format!("Installed release: {}", INSTALLED_TAG));
                if ui.button("Check for updates").clicked() {
                    invoke(android, "check");
                }
                if ui.button("Toggle automatic check at startup").clicked() {
                    invoke(android, "toggle");
                }
                ui.small("Only published ARM64 GitHub Releases are eligible.");
                ui.small("Downloads and Android installation always need confirmation.");
            });
    }
}
