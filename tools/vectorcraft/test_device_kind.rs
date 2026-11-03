//! Host-only regression tests for Android mouse / touchpad / touchscreen classification.
//! Run: rustc --edition=2021 --test tools/vectorcraft/test_device_kind.rs -o /tmp/vectorcraft-device-kind && /tmp/vectorcraft-device-kind
#[path = "../../vendor/winit/src/platform_impl/android/device_kind.rs"]
mod device_kind;
