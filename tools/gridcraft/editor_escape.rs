
// Android's hidden IME EditText may consume hardware Esc before egui receives it.
// Route the captured press to the existing cancel actions, with modal priority intact.
impl SheetApp {
    pub fn android_editor_escape_active(&self) -> bool {
        (self.editor.is_some() || self.text_box_editor.is_some())
            && self.dialog.is_none() && self.message.is_none() && self.backstage.is_none()
    }

    pub fn android_handle_editor_escape(&mut self, ctx: &egui::Context, native_press: bool) -> bool {
        if !self.android_editor_escape_active() { return false; }
        let event_press = ctx.input_mut(|i| {
            let mut pressed = false;
            i.events.retain(|event| {
                if let egui::Event::Key { key: egui::Key::Escape, pressed: down, repeat, modifiers, .. } = event {
                    if !modifiers.any() {
                        pressed |= *down && !*repeat;
                        return false;
                    }
                }
                true
            });
            pressed
        });
        if !native_press && !event_press { return false; }
        self.cancel_edit();
        self.cancel_text_box_edit();
        ctx.memory_mut(|m| {
            for name in ["gridcraft.cell_editor", "gridcraft.formula_bar", "gridcraft.text_box_editor"] {
                m.surrender_focus(egui::Id::new(name));
            }
        });
        ctx.request_repaint();
        true
    }
}

#[cfg(test)]
mod android_escape_regression {
    use super::*;
    fn app() -> SheetApp {
        let mut session = Session::new();
        session.new_workbook();
        let mut app = SheetApp::new(session, Services::default());
        app.run("cell.set", json!({"cell":"A1", "input":"Original"})).unwrap();
        app
    }
    #[test]
    fn native_escape_exits_cell_and_formula_edit_without_committing_draft() {
        for formula_bar in [false, true] {
            let mut app = app();
            let before = app.session.active().unwrap().revision;
            app.begin_edit(Some("Uncommitted draft".into()), formula_bar);
            let ctx = egui::Context::default();
            let id = egui::Id::new(if formula_bar { "gridcraft.formula_bar" } else { "gridcraft.cell_editor" });
            ctx.memory_mut(|m| m.request_focus(id));
            assert!(app.android_handle_editor_escape(&ctx, true));
            assert!(app.editor.is_none());
            assert_eq!(app.session.active().unwrap().revision, before);
            assert_ne!(ctx.memory(|m| m.focused()), Some(id));
            app.begin_edit(Some("Next edit".into()), false);
            assert!(app.editor.is_some());
        }
    }
    #[test]
    fn error_dialog_keeps_editor_draft_and_owns_escape() {
        let mut app = app();
        app.begin_edit(Some("Draft".into()), false);
        app.message = Some(("Validation".into(), "Check input".into()));
        assert!(!app.android_handle_editor_escape(&egui::Context::default(), true));
        assert_eq!(app.editor.as_ref().unwrap().text, "Draft");
    }
    #[test]
    fn modified_repeat_and_release_events_do_not_exit_editing() {
        for (modifiers, pressed, repeat) in [(egui::Modifiers::CTRL, true, false), (egui::Modifiers::NONE, true, true), (egui::Modifiers::NONE, false, false)] {
            let mut app = app();
            app.begin_edit(Some("Draft".into()), false);
            let ctx = egui::Context::default();
            ctx.input_mut(|i| i.events.push(egui::Event::Key { key: egui::Key::Escape, physical_key: None, pressed, repeat, modifiers }));
            assert!(!app.android_handle_editor_escape(&ctx, false));
            assert!(app.editor.is_some());
        }
    }
    #[test]
    fn egui_escape_exits_editing_even_if_ime_focus_was_lost() {
        let mut app = app();
        app.begin_edit(Some("Draft".into()), false);
        let ctx = egui::Context::default();
        ctx.input_mut(|i| i.events.push(egui::Event::Key { key: egui::Key::Escape, physical_key: None, pressed: true, repeat: false, modifiers: egui::Modifiers::NONE }));
        assert!(app.android_handle_editor_escape(&ctx, false));
        assert!(app.editor.is_none());
    }
    #[test]
    fn no_editor_does_not_consume_escape() {
        let mut app = app();
        assert!(!app.android_handle_editor_escape(&egui::Context::default(), true));
    }
}
