#[cfg(test)]
mod android_stability_input_tests {
    use super::*;
    use egui::{Event,Key,Modifiers,RawInput};
    fn key(key:Key,modifiers:Modifiers)->Event {Event::Key {key,physical_key:Some(key),pressed:true,repeat:false,modifiers}}
    #[test]
    fn snapshots_survive_missing_modifier_transitions() {
        let mut state=AndroidModifiers::default();
        for _ in 0..100 {
            for mods in [Modifiers{ctrl:true,command:true,..Modifiers::NONE},Modifiers::NONE] {
                let mut raw=RawInput{events:vec![Event::ModifiersChanged(mods),key(Key::Q,mods)],..Default::default()};
                apply_android_modifiers(&mut state,&mut raw);
                assert!(matches!(raw.events.last(),Some(Event::Key{modifiers,..}) if *modifiers==mods));
            }
        }
    }
    #[test]
    fn all_tool_letters_use_one_dispatcher() {
        for k in [Key::V,Key::T,Key::P,Key::A,Key::B,Key::R] {
            let mut raw=RawInput{events:vec![key(k,Modifiers::NONE)],..Default::default()};
            assert_eq!(canvas_hardware_command(&raw,false,false,false,false,false),None);
            assert_eq!(restore_tool_key_text(&mut raw,true),1);assert_eq!(restore_tool_key_text(&mut raw,true),0);
        }
    }
    #[test]
    fn typing_and_composition_unchanged() {
        let mut raw=RawInput{events:vec![key(Key::T,Modifiers::NONE),Event::Ime(egui::ImeEvent::Commit("test".into()))],..Default::default()};
        assert_eq!(restore_tool_key_text(&mut raw,false),0);assert_eq!(raw.events.len(),2);
        assert_eq!(canvas_hardware_command(&raw,true,false,true,false,false),None);
    }
    #[test]
    fn precision_scroll_preserves_phase_delta_and_mouse_wheel() {
        for (unit,source,expected) in [
            (egui::MouseWheelUnit::Point,egui::MouseWheelSource::Unknown,egui::MouseWheelSource::Trackpad),
            (egui::MouseWheelUnit::Line,egui::MouseWheelSource::Unknown,egui::MouseWheelSource::Unknown),
            (egui::MouseWheelUnit::Point,egui::MouseWheelSource::Momentum,egui::MouseWheelSource::Momentum)] {
            let mut raw=RawInput{events:vec![Event::MouseWheel{unit,source,delta:egui::vec2(9.0,-320.0),phase:egui::TouchPhase::End,modifiers:Modifiers::NONE}],..Default::default()};
            classify_android_precision_scroll(&mut raw);
            assert!(matches!(raw.events[0],Event::MouseWheel{delta,phase:egui::TouchPhase::End,source,..} if delta==egui::vec2(9.0,-320.0)&&source==expected));
        }
    }
}
