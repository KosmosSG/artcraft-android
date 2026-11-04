//! Fallback for hardware keyboard events that NativeActivity's egui/winit path
//! does not expose as Event::Key on certain Android keyboards.
//! All interception is passive: Java dispatches the original event normally.
//! Only a finite allowlist of command keys is forwarded; typed text and tokens
//! are never inspected, logged, or persisted.
use crate::AndroidFileBridge;

fn mapped_key(code: u32) -> Option<egui::Key> {
    // Android KeyEvent KEYCODE_A..KEYCODE_Z are consecutive (29..=54).
    // Forward only key identity; Android-owned text / IME content stays private.
    Some(match code {
        29 => egui::Key::A, 30 => egui::Key::B,
        31 => egui::Key::C, 32 => egui::Key::D,
        33 => egui::Key::E, 34 => egui::Key::F,
        35 => egui::Key::G, 36 => egui::Key::H,
        37 => egui::Key::I, 38 => egui::Key::J,
        39 => egui::Key::K, 40 => egui::Key::L,
        41 => egui::Key::M, 42 => egui::Key::N,
        43 => egui::Key::O, 44 => egui::Key::P,
        45 => egui::Key::Q, 46 => egui::Key::R,
        47 => egui::Key::S, 48 => egui::Key::T,
        49 => egui::Key::U, 50 => egui::Key::V,
        51 => egui::Key::W, 52 => egui::Key::X,
        53 => egui::Key::Y, 54 => egui::Key::Z,
        66 => egui::Key::Enter,
        111 => egui::Key::Escape,
        59 => egui::Key::ShiftLeft, 60 => egui::Key::ShiftRight,
        57 => egui::Key::AltLeft, 58 => egui::Key::AltRight,
        113 => egui::Key::ControlLeft, 114 => egui::Key::ControlRight,
        _ => return None,
    })
}
/// Reconcile Java's authoritative meta-state with a matching native event.
/// A native match must not discard the modifier flags, and merging must not
/// execute the same transition twice within a frame.
fn merge(raw: &mut egui::RawInput, event: &str, state: &mut egui::Modifiers) {
    let mut bits = event.split(',');
    let (Some(code), Some(flags), Some(down)) = (bits.next(), bits.next(), bits.next()) else { return };
    let (Ok(code), Ok(flags)) = (code.parse::<u32>(), flags.parse::<u32>()) else { return };
    if !matches!(down, "0" | "1") { return; }
    let Some(key) = mapped_key(code) else { return };
    let pressed = down == "1";
    let mods = egui::Modifiers {
        alt: flags & 1 != 0, ctrl: flags & 2 != 0, shift: flags & 4 != 0,
        mac_cmd: false, command: flags & 2 != 0,
    };
    let found = raw.events.iter().position(|e| matches!(e,
        egui::Event::Key { key: existing, pressed: existing_down, .. }
            if *existing == key && *existing_down == pressed));
    if let Some(at) = found {
        if let egui::Event::Key { modifiers, .. } = &mut raw.events[at] {
            *modifiers = mods;
        }
        raw.events.insert(at, egui::Event::ModifiersChanged(mods));
    } else {
        raw.events.push(egui::Event::ModifiersChanged(mods));
        raw.events.push(egui::Event::Key {
            key, physical_key: Some(key), pressed, repeat: false, modifiers: mods,
        });
    }
    *state = mods;
}

pub(crate) fn inject(bridge: &AndroidFileBridge, raw: &mut egui::RawInput, state: &mut egui::Modifiers) -> usize {
    let mut received = 0;
    for _ in 0..128 {
        match bridge.poll_hardware_key() {
            Ok(Some(event)) => { merge(raw, &event, state); received += 1; },
            _ => break,
        }
    }
    if received > 0 { raw.events.push(egui::Event::ModifiersChanged(*state)); }
    received
}

#[cfg(test)]
mod tests {
    use super::*;
    fn keys(raw: &egui::RawInput) -> Vec<(egui::Key, bool, egui::Modifiers)> {
        raw.events.iter().filter_map(|e| match e {
            egui::Event::Key { key, pressed, modifiers, .. } => Some((*key, *pressed, *modifiers)),
            _ => None,
        }).collect()
    }
    #[test]
    fn native_duplicate_preserves_java_ctrl_and_one_transition() {
        let mut raw = egui::RawInput::default();
        let mut state = egui::Modifiers::NONE;
        raw.events.push(egui::Event::Key { key: egui::Key::W, physical_key: None,
            pressed: true, repeat: false, modifiers: state });
        merge(&mut raw, "51,2,1", &mut state);
        assert_eq!(keys(&raw).len(), 1);
        assert!(keys(&raw)[0].2.ctrl && keys(&raw)[0].2.command);
        assert!(state.ctrl);
    }
    #[test]
    fn twenty_cycles_deliver_down_up_and_release_modifiers() {
        let mut state = egui::Modifiers::NONE;
        for _ in 0..20 {
            for code in [41,50,30,48,111,41,50,30,36,54] {
                let mut raw = egui::RawInput::default();
                merge(&mut raw, &format!("{code},0,1"), &mut state);
                merge(&mut raw, &format!("{code},0,0"), &mut state);
                assert_eq!(keys(&raw).len(), 2);
                assert!(keys(&raw)[0].1);
                assert!(!keys(&raw)[1].1);
                assert_eq!(state, egui::Modifiers::NONE);
            }
            let mut raw = egui::RawInput::default();
            merge(&mut raw, "41,4,1", &mut state);
            assert!(keys(&raw)[0].2.shift);
            merge(&mut raw, "41,0,0", &mut state);
            assert_eq!(state, egui::Modifiers::NONE);
        }
    }
    #[test]
    fn text_is_never_promoted_to_a_shortcut() {
        let mut raw = egui::RawInput::default();
        raw.events.push(egui::Event::Text("n".into()));
        let mut state = egui::Modifiers::NONE;
        merge(&mut raw, "bad", &mut state);
        assert!(keys(&raw).is_empty());
        assert!(matches!(&raw.events[0], egui::Event::Text(s) if s == "n"));
    }
    #[test]
    fn actual_egui_receives_ctrl_w_once() {
        let ctx = egui::Context::default();
        let mut raw = egui::RawInput::default();
        let mut state = egui::Modifiers::NONE;
        raw.events.push(egui::Event::Key { key: egui::Key::W, physical_key: None,
            pressed: true, repeat: false, modifiers: state });
        merge(&mut raw, "51,2,1", &mut state);
        let mut output = ctx.run_ui(raw, |ui| {
            assert!(ui.ctx().input(|i| i.modifiers.ctrl));
            assert!(ui.ctx().input_mut(|i| i.consume_key(egui::Modifiers::CTRL, egui::Key::W)));
            assert!(!ui.ctx().input_mut(|i| i.consume_key(egui::Modifiers::CTRL, egui::Key::W)));
        });
        output.textures_delta.clear();
    }
    #[test]
    fn modifier_release_without_another_letter_updates_egui() {
        let ctx = egui::Context::default();
        let mut state = egui::Modifiers::NONE;
        for (record, expected) in [("113,2,1", true), ("113,0,0", false)] {
            let mut raw = egui::RawInput::default();
            merge(&mut raw, record, &mut state);
            let mut output = ctx.run_ui(raw, |ui| {
                assert_eq!(ui.ctx().input(|i| i.modifiers.ctrl), expected);
            });
            output.textures_delta.clear();
        }
    }
}
