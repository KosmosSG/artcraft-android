//! Shared Android JNI plumbing for the `egui-winit` Android integrations.
//!
//! `ndk_context::android_context()` hands out the *Application*, not the Activity, and the
//! integrations here need `Activity`-only APIs (`getWindow()` for the pointer icon,
//! `startActivity()` for links). The app shell has the real handle at startup, so it publishes it
//! once here; the bridges read it back.

#![cfg(target_os = "android")]

/// The Activity jobject, published once by the app shell (`AndroidApp::activity_as_ptr`).
///
/// The pointer is an unowned JNI global reference owned by `android-activity`, so it must never be
/// deleted by anything that reads it here.
use std::sync::atomic::{AtomicPtr, Ordering};
static ACTIVITY: AtomicPtr<std::ffi::c_void> = AtomicPtr::new(std::ptr::null_mut());

/// Publish the Activity jobject for the bridges. Call once at startup with
/// `app.activity_as_ptr() as usize`. Each new android_main refreshes the Activity after recreation.
pub fn set_activity(activity_as_ptr: *mut std::ffi::c_void) {
    ACTIVITY.store(activity_as_ptr, Ordering::Release);
}

/// The published Activity jobject, or `None` before the shell publishes it.
pub fn activity_raw() -> Option<jni::sys::jobject> {
    let ptr = ACTIVITY.load(Ordering::Acquire);
    (!ptr.is_null()).then_some(ptr.cast())
}
