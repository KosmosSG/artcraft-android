//! Optional docked Android command pad. Original implementation; no synthetic key events.
use std::path::PathBuf;

pub const COMMANDS: [(&str, &str); 8] = [
    ("Undo", "edit.undo"),
    ("Redo", "edit.redo"),
    ("Save", "file.save"),
    ("Fit", "view.fitOnScreen"),
    ("100%", "view.actualPixels"),
    ("Move", "tools.select.move"),
    ("Brush", "tools.select.brush"),
    ("Eraser", "tools.select.eraser"),
];

#[derive(Debug, PartialEq)]
pub enum Action {
    Command(&'static str),
    Hide,
}

pub struct ShortcutPad {
    enabled: bool,
    setting: PathBuf,
    #[cfg(test)]
    buttons: Vec<(&'static str, egui::Rect)>,
    #[cfg(test)]
    bounds: Option<egui::Rect>,
}

impl ShortcutPad {
    pub fn new(setting: PathBuf) -> Self {
        let enabled = std::fs::read(&setting).is_ok_and(|data| data == b"enabled\n");
        Self {
            enabled,
            setting,
            #[cfg(test)]
            buttons: Vec::new(),
            #[cfg(test)]
            bounds: None,
        }
    }

    pub fn enabled(&self) -> bool { self.enabled }

    pub fn set_enabled(&mut self, enabled: bool) -> std::io::Result<()> {
        if let Some(parent) = self.setting.parent() { std::fs::create_dir_all(parent)?; }
        let pending = self.setting.with_extension("tmp");
        std::fs::write(&pending, if enabled { b"enabled\n".as_slice() } else { b"disabled\n".as_slice() })?;
        std::fs::rename(pending, &self.setting)?;
        self.enabled = enabled;
        Ok(())
    }

    /// Draw before the editor's CentralPanel, reserving space rather than covering its canvas.
    /// `allowed` must use the official modal and command-availability gates.
    pub fn show(&mut self, ui: &mut egui::Ui, editing_text: bool, chrome_hidden: bool,
                mut allowed: impl FnMut(&str) -> bool) -> Option<Action> {
        #[cfg(test)]
        { self.buttons.clear(); self.bounds = None; }
        if !self.enabled || chrome_hidden { return None; }
        let editing_text = editing_text || ui.ctx().text_edit_focused();
        let mut action = None;
        let panel = egui::Panel::bottom("artcraft.touch_shortcut_pad")
            .resizable(false).default_size(56.0).show(ui, |ui| {
                egui::ScrollArea::horizontal().id_salt("artcraft.touch_shortcut_pad.scroll")
                    .show(ui, |ui| {
                        ui.horizontal(|ui| {
                            ui.spacing_mut().item_spacing.x = 6.0;
                            for &(label, command) in &COMMANDS {
                                let enabled = !editing_text && allowed(command);
                                let tip = if editing_text { "Finish editing text to use the Shortcut Pad" } else { label };
                                let response = ui.add_enabled(enabled,
                                    egui::Button::new(label).min_size(egui::vec2(56.0, 44.0)))
                                    .on_hover_text(tip);
                                #[cfg(test)]
                                self.buttons.push((command, response.rect));
                                if response.clicked() { action = Some(Action::Command(command)); }
                            }
                            if ui.add(egui::Button::new("Hide pad")
                                .min_size(egui::vec2(72.0, 44.0))).clicked() {
                                action = Some(Action::Hide);
                            }
                        });
                    });
            });
        #[cfg(test)]
        { self.bounds = Some(panel.response.rect); }
        #[cfg(not(test))]
        let _ = panel;
        action
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use egui::{Event, Modifiers, PointerButton, Pos2, RawInput, Rect, vec2};
    use std::sync::atomic::{AtomicUsize, Ordering};
    static NEXT: AtomicUsize = AtomicUsize::new(0);

    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let dir = std::env::temp_dir().join(format!("photocraft-pad-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
            std::fs::create_dir_all(&dir).unwrap();
            Self(dir)
        }
        fn pad(&self) -> ShortcutPad { ShortcutPad::new(self.0.join("shortcut-pad-enabled")) }
    }
    impl Drop for Fixture { fn drop(&mut self) { let _ = std::fs::remove_dir_all(&self.0); } }

    fn frame(pad: &mut ShortcutPad, ctx: &egui::Context, width: f32, events: Vec<Event>,
             editing: bool, hidden: bool, allowed: bool) -> (Option<Action>, Rect) {
        let mut action = None;
        let mut canvas = Rect::NOTHING;
        let mut out = ctx.run_ui(RawInput {
            screen_rect: Some(Rect::from_min_size(Pos2::ZERO, vec2(width, 600.0))), events,
            ..Default::default()
        }, |ui| {
            // egui may discard a layout pass: only the final pass's action is observed.
            action = pad.show(ui, editing, hidden, |_| allowed);
            canvas = egui::CentralPanel::default().show(ui, |ui| ui.max_rect()).inner;
        });
        out.textures_delta.clear();
        (action, canvas)
    }
    fn click(at: Pos2, down: bool) -> Vec<Event> {
        vec![Event::PointerMoved(at), Event::PointerButton {
            pos: at, button: PointerButton::Primary, pressed: down, modifiers: Modifiers::NONE
        }]
    }
    #[test]
    fn opt_in_is_persisted_and_invalid_settings_do_not_enable_it() {
        let f = Fixture::new(); let mut pad = f.pad();
        assert!(!pad.enabled());
        pad.set_enabled(true).unwrap(); assert!(f.pad().enabled());
        pad.set_enabled(false).unwrap(); assert!(!f.pad().enabled());
        std::fs::write(&pad.setting, b"partial").unwrap(); assert!(!f.pad().enabled());
    }
    #[test]
    fn failed_setting_write_keeps_previous_state() {
        let f = Fixture::new(); let mut pad = ShortcutPad::new(f.0.join("blocked/setting"));
        std::fs::write(f.0.join("blocked"), b"file, not a directory").unwrap();
        assert!(pad.set_enabled(true).is_err()); assert!(!pad.enabled());
    }
    #[test]
    fn disabled_and_fullscreen_pad_leave_the_canvas_available() {
        let f = Fixture::new(); let mut pad = f.pad(); let ctx = egui::Context::default();
        let (_, normal) = frame(&mut pad, &ctx, 800.0, vec![], false, false, true);
        assert!(pad.bounds.is_none());
        pad.set_enabled(true).unwrap();
        let (_, full) = frame(&mut pad, &ctx, 800.0, vec![], false, true, true);
        assert_eq!(normal, full); assert!(pad.bounds.is_none());
    }
    #[test]
    fn touch_buttons_reserve_space_and_stay_large_on_narrow_screens() {
        let f = Fixture::new(); let mut pad = f.pad(); pad.set_enabled(true).unwrap();
        let ctx = egui::Context::default();
        let (_, canvas) = frame(&mut pad, &ctx, 320.0, vec![], false, false, true);
        assert!(canvas.bottom() <= pad.bounds.unwrap().top());
        assert_eq!(pad.buttons.len(), 8);
        assert!(pad.buttons.iter().all(|(_, r)| r.height() >= 44.0 && r.width() >= 56.0));
    }
    #[test]
    fn a_tap_dispatches_one_command_and_does_not_synthesize_keys() {
        let f = Fixture::new(); let mut pad = f.pad(); pad.set_enabled(true).unwrap();
        let ctx = egui::Context::default();
        frame(&mut pad, &ctx, 1000.0, vec![], false, false, true);
        let at = pad.buttons[0].1.center();
        assert_eq!(frame(&mut pad, &ctx, 1000.0, click(at, true), false, false, true).0, None);
        assert_eq!(frame(&mut pad, &ctx, 1000.0, click(at, false), false, false, true).0, Some(Action::Command("edit.undo")));
        assert_eq!(frame(&mut pad, &ctx, 1000.0, vec![], false, false, true).0, None);
    }
    #[test]
    fn text_editing_and_disabled_commands_cannot_dispatch() {
        for (editing, allowed) in [(true, true), (false, false)] {
            let f = Fixture::new(); let mut pad = f.pad(); pad.set_enabled(true).unwrap();
            let ctx = egui::Context::default();
            frame(&mut pad, &ctx, 1000.0, vec![], editing, false, allowed);
            let at = pad.buttons[0].1.center();
            frame(&mut pad, &ctx, 1000.0, click(at, true), editing, false, allowed);
            assert_eq!(frame(&mut pad, &ctx, 1000.0, click(at, false), editing, false, allowed).0, None);
        }
    }
}
