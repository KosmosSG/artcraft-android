//! PDFCraft-only Android Adaptive Cursor port: MostafaXS1/artcraft-android v0.2.0.
//! NativeActivity, not the source fork's GameActivity. Hover and pinch are untouched.
#![cfg(target_os = "android")]
use std::sync::OnceLock;
use std::sync::atomic::{AtomicI32, Ordering};
static ACTIVITY: OnceLock<usize> = OnceLock::new();
// PDFCRAFT_ANDROID_CURSOR_FALLBACK_DEDUP: a changed cursor triggers at most one JNI update.
static LAST_ICON: AtomicI32 = AtomicI32::new(-1);
pub fn set_activity(activity: usize) { let _ = ACTIVITY.set(activity); }
pub fn icon_type(icon: egui::CursorIcon) -> Option<i32> {
    use egui::CursorIcon as C;
    Some(match icon {
        C::Default => 1000,
        C::Text | C::VerticalText => 1008,
        C::PointingHand => 1002,
        C::Crosshair => 1007,
        C::ContextMenu => 1001,
        C::Help => 1003,
        C::Cell => 1006,
        C::Alias => 1010,
        C::Copy => 1011,
        C::NoDrop => 1012,
        C::NotAllowed => 1013,
        C::Grab => 1016,
        C::Grabbing => 1017,
        C::ZoomIn => 1018,
        C::ZoomOut => 1019,
        C::AllScroll | C::Move => 1015,
        C::ResizeHorizontal | C::ResizeColumn | C::ResizeEast | C::ResizeWest => 1014,
        C::ResizeVertical | C::ResizeRow | C::ResizeNorth | C::ResizeSouth => 1021,
        C::ResizeNwSe | C::ResizeNorthWest | C::ResizeSouthEast => 1022,
        C::ResizeNeSw | C::ResizeNorthEast | C::ResizeSouthWest => 1023,
        C::Progress | C::Wait | C::None => return None,
    })
}
// Called from deduplicated egui-winit PlatformOutput cursor events only.
#[expect(unsafe_code)]
pub fn apply(icon: impl std::fmt::Debug) {
    // The PDFCraft app and vendored egui-winit use distinct egui crate revisions.
    // Compare stable CursorIcon variant names rather than passing a cross-crate enum.
    let icon_name = format!("{icon:?}");
    let kind = match icon_name.as_str() {
        "Default" => 1000,
        "Text" | "VerticalText" => 1008,
        "PointingHand" => 1002,
        "Crosshair" => 1007,
        "ContextMenu" => 1001,
        "Help" => 1003,
        "Cell" => 1006,
        "Alias" => 1010,
        "Copy" => 1011,
        "NoDrop" => 1012,
        "NotAllowed" => 1013,
        "Grab" => 1016,
        "Grabbing" => 1017,
        "ZoomIn" => 1018,
        "ZoomOut" => 1019,
        "AllScroll" | "Move" => 1015,
        "ResizeHorizontal" | "ResizeColumn" | "ResizeEast" | "ResizeWest" => 1014,
        "ResizeVertical" | "ResizeRow" | "ResizeNorth" | "ResizeSouth" => 1021,
        "ResizeNwSe" | "ResizeNorthWest" | "ResizeSouthEast" => 1022,
        "ResizeNeSw" | "ResizeNorthEast" | "ResizeSouthWest" => 1023,
        _ => return,
    };
    let Some(activity_ptr) = ACTIVITY.get().copied().filter(|p| *p != 0) else { return };
    if LAST_ICON.swap(kind, Ordering::Relaxed) == kind { return; }
    use jni::{jni_sig, jni_str, objects::{JObject, JValue}, JavaVM};
    let vm = unsafe { JavaVM::from_raw(ndk_context::android_context().vm().cast()) };
    let result = vm.attach_current_thread(|env| -> jni::errors::Result<()> {
        let raw = activity_ptr as jni::sys::jobject;
        let activity = unsafe { env.as_cast_raw::<JObject<'_>>(&raw)? };
        env.call_method(&*activity, jni_str!("pdfApplyAdaptiveCursor"),
            jni_sig!("(I)V"), &[JValue::Int(kind)])?;
        Ok(())
    });
    if let Err(error) = result { log::warn!("PDFCraft Adaptive Cursor: {error}"); }
}
