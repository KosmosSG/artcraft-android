use android_activity::AndroidApp;
use eframe::egui;
use jni::{JavaVM,jni_sig,strings::JNIString,objects::{JObject,JValue}};
pub struct ModalBridge { app: AndroidApp }
impl ModalBridge {
 pub fn new(app: &AndroidApp) -> Self {Self {app:app.clone()}}
    pub fn unsaved_dialog(&self, active: bool, ctx: &egui::Context) {
        if !active { ctx.data_mut(|d| d.remove::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))); }
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let result = vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, JNIString::new("dkUnsavedDialog"), jni_sig!("(Z)I"), &[JValue::Bool(active.into())]);
            if result.is_err() { env.exception_clear(); }
            result?.i()
        });
        if let Ok(action @ 1..=3) = result {
            if active { ctx.data_mut(|d| d.insert_temp(egui::Id::new("deckcraft.unsaved.dcs"), action as u8)); }
        }
        if active { ctx.request_repaint_after(std::time::Duration::from_millis(16)); }
    }
}
