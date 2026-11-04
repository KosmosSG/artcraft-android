//! Compile and exercise the exact candidate bridge without Android/JNI.
#![allow(dead_code)]
struct AndroidFileBridge;
impl AndroidFileBridge {
    fn poll_hardware_key(&self) -> Result<Option<String>, String> { Ok(None) }
}
mod hardware_keys;
