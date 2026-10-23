//! Android hardware modifier reconstruction. Original project implementation.
//! Track both sides independently: releasing Left Ctrl must not release Right Ctrl.

#[derive(Default)]
pub struct AndroidModifiers {
    held: [bool; 6],
}

impl AndroidModifiers {
    fn modifiers(&self) -> egui::Modifiers {
        egui::Modifiers {
            shift: self.held[0] || self.held[1],
            ctrl: self.held[2] || self.held[3],
            alt: self.held[4] || self.held[5],
            mac_cmd: false,
            command: self.held[2] || self.held[3],
        }
    }
}

pub fn apply_android_modifiers(state: &mut AndroidModifiers, raw: &mut egui::RawInput) {
    let mut kept = Vec::with_capacity(raw.events.len());
    for mut event in raw.events.drain(..) {
        match &mut event {
            egui::Event::Key { key, physical_key, pressed, modifiers, .. } => {
                let tracked = physical_key.unwrap_or(*key);
                let before = state.modifiers();
                let side = match tracked {
                    egui::Key::ShiftLeft => Some(0),
                    egui::Key::ShiftRight => Some(1),
                    egui::Key::ControlLeft => Some(2),
                    egui::Key::ControlRight => Some(3),
                    egui::Key::AltLeft => Some(4),
                    egui::Key::AltRight => Some(5),
                    _ => None,
                };
                if let Some(side) = side { state.held[side] = *pressed; }
                let current = state.modifiers();
                if current != before { kept.push(egui::Event::ModifiersChanged(current)); }
                *modifiers = current;
                kept.push(event);
            }
            egui::Event::PointerButton { modifiers, .. }
            | egui::Event::MouseWheel { modifiers, .. } => {
                *modifiers = state.modifiers();
                kept.push(event);
            }
            egui::Event::Text(_) if state.modifiers().command => {}
            egui::Event::WindowFocused(false) => {
                *state = AndroidModifiers::default();
                kept.push(egui::Event::ModifiersChanged(state.modifiers()));
                kept.push(event);
            }
            _ => kept.push(event),
        }
    }
    raw.events = kept;
}

#[cfg(test)]
mod tests {
    use super::*;
    use egui::{Event, Key, Modifiers, RawInput};

    fn key(key: Key, pressed: bool) -> Event {
        Event::Key { key, physical_key: Some(key), pressed, repeat: false, modifiers: Modifiers::NONE }
    }
    fn apply(state: &mut AndroidModifiers, events: Vec<Event>) -> Vec<Event> {
        let mut raw = RawInput { events, ..Default::default() };
        apply_android_modifiers(state, &mut raw);
        raw.events
    }
    #[test]
    fn releasing_one_side_preserves_the_other() {
        for (left, right, field) in [
            (Key::ControlLeft, Key::ControlRight, 0),
            (Key::ShiftLeft, Key::ShiftRight, 1),
            (Key::AltLeft, Key::AltRight, 2),
        ] {
            for (first, second) in [(left, right), (right, left)] {
                let mut state = AndroidModifiers::default();
                apply(&mut state, vec![key(first, true), key(second, true), key(first, false)]);
                let mods = state.modifiers();
                assert!([mods.ctrl, mods.shift, mods.alt][field]);
                apply(&mut state, vec![key(second, false)]);
                assert_eq!(state.modifiers(), Modifiers::NONE);
            }
        }
    }
    #[test]
    fn command_and_chord_text_across_frames() {
        let mut state = AndroidModifiers::default();
        apply(&mut state, vec![key(Key::ControlRight, true)]);
        let events = apply(&mut state, vec![key(Key::Z, true), Event::Text("z".into())]);
        assert!(matches!(events.as_slice(), [Event::Key { modifiers, .. }] if modifiers.ctrl && modifiers.command && !modifiers.mac_cmd));
        apply(&mut state, vec![key(Key::ControlRight, false)]);
        assert!(matches!(apply(&mut state, vec![Event::Text("z".into())]).as_slice(), [Event::Text(_)]));
    }
    #[test]
    fn repeats_are_idempotent_and_focus_loss_clears_all_sides() {
        let mut state = AndroidModifiers::default();
        apply(&mut state, vec![key(Key::ControlLeft, true), key(Key::ControlLeft, true), key(Key::ShiftRight, true)]);
        assert!(state.modifiers().ctrl && state.modifiers().shift);
        let events = apply(&mut state, vec![Event::WindowFocused(false), key(Key::B, true), Event::Text("b".into())]);
        assert_eq!(state.modifiers(), Modifiers::NONE);
        assert!(matches!(events.last(), Some(Event::Text(_))));
    }
    #[test]
    fn physical_key_and_event_order_are_preserved() {
        let mut state = AndroidModifiers::default();
        let ctrl = Event::Key { key: Key::A, physical_key: Some(Key::ControlLeft), pressed: true, repeat: false, modifiers: Modifiers::NONE };
        let events = apply(&mut state, vec![ctrl, key(Key::S, true), key(Key::ControlLeft, false)]);
        assert!(matches!(&events[0], Event::ModifiersChanged(mods) if mods.command));
        assert!(matches!(&events[2], Event::Key { key: Key::S, modifiers, .. } if modifiers.command));
        assert!(matches!(&events[3], Event::ModifiersChanged(mods) if !mods.command));
    }
    #[test]
    fn ime_composition_is_never_rewritten() {
        let mut state = AndroidModifiers::default();
        apply(&mut state, vec![key(Key::ControlLeft, true)]);
        let events = apply(&mut state, vec![Event::Ime(egui::ImeEvent::Commit("你好".into()))]);
        assert!(matches!(events.as_slice(), [Event::Ime(egui::ImeEvent::Commit(text))] if text == "你好"));
    }
}
