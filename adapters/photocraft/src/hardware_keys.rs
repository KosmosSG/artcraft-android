//! Fallback for hardware keyboard events that NativeActivity's egui/winit path
//! does not expose as Event::Key on certain Android keyboards.
//! All interception is passive: Java dispatches the original event normally.
//! Only a finite allowlist of command keys is forwarded; typed text and tokens
//! are never inspected, logged, or persisted.
use crate::AndroidFileBridge;

fn mapped_key(code: u32) -> Option<egui::Key> {
    Some(match code {
        111 => egui::Key::Escape, // Android KEYCODE_ESCAPE
        50 => egui::Key::V,
        48 => egui::Key::T,
        30 => egui::Key::B,
        53 => egui::Key::Y,
        42 => egui::Key::N,
        31 => egui::Key::C,
        51 => egui::Key::W,
        32 => egui::Key::D,
        47 => egui::Key::S,
        66 => egui::Key::Enter,
        _ => return None,
    })
}
pub(crate) fn inject(bridge: &AndroidFileBridge, raw: &mut egui::RawInput) {
    for _ in 0..24 {
        let event = match bridge.poll_hardware_key() {
            Ok(Some(k)) => k,
            Ok(None) => break,
            Err(_) => break, // a Java activity without the bridge is still usable
        };
        let mut bits = event.split(',');
        let (Some(code), Some(flags), Some(down)) = (bits.next(), bits.next(), bits.next()) else { continue };
        let (Ok(code), Ok(flags)) = (code.parse::<u32>(), flags.parse::<u32>()) else { continue };
        let Some(key) = mapped_key(code) else { continue };
        let pressed = down == "1";
        let mods = egui::Modifiers {
            alt: flags & 1 != 0,
            ctrl: flags & 2 != 0,
            shift: flags & 4 != 0,
            mac_cmd: false,
            command: flags & 2 != 0,
        };
        if !raw.events.iter().any(|e| matches!(e,
            egui::Event::Key { key: existing, pressed: already_pressed, .. }
                if *existing == key && *already_pressed == pressed)) {
            raw.events.push(egui::Event::Key {
                key, physical_key: None, pressed, repeat: false, modifiers: mods,
            });
        }
    }
}


/// Recover tool and discard-dialog hotkeys when a hardware/soft keyboard only
/// produces egui::Text instead of an egui::Key. Never do this while the Type
/// tool or a text field owns input: it would hijack typed characters and tokens.
pub(crate) fn recover_text_keys(
    raw: &mut egui::RawInput, ctx: &egui::Context, inline_text_edit: bool,
) {
    if inline_text_edit || ctx.text_edit_focused() { return; }
    let mut recovered = Vec::new();
    for event in &raw.events {
        let egui::Event::Text(text) = event else { continue };
        let key = match text.as_str().to_ascii_lowercase().as_str() {
            "v" => egui::Key::V, "t" => egui::Key::T,
            "b" => egui::Key::B, "y" => egui::Key::Y,
            "n" => egui::Key::N, "c" => egui::Key::C,
            "d" => egui::Key::D, "s" => egui::Key::S,
            _ => continue,
        };
        if raw.events.iter().any(|e| matches!(e,
            egui::Event::Key { key: present, pressed: true, .. } if *present == key
        )) { continue; }
        recovered.push(key);
    }
    for key in recovered {
        for pressed in [true, false] {
            raw.events.push(egui::Event::Key {
                key, physical_key: None, pressed, repeat: false,
                modifiers: egui::Modifiers::NONE,
            });
        }
    }
}
