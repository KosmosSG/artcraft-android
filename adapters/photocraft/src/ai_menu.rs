//! Android-only, native egui AI Tools menu. This is a safe UI scaffold:
//! none of the processing commands execute until a verified backend exists.
//! No upstream PhotoCraft crates, Android manifest, or signing files are changed.

use crate::ai_tools::AiAction;

#[derive(Default)]
pub(crate) struct AndroidAiMenu {
    show_about: bool,
}

impl AndroidAiMenu {
    pub(crate) fn show(&mut self, ctx: &egui::Context) {
        // A separate top bar is necessary until upstream PhotoCraft exposes
        // a supported menu extension hook. Do not imitate/replace Filter.
        egui::TopBottomPanel::top("artcraft_photocraft_android_ai_menu")
            .resizable(false)
            .show(ctx, |ui| {
                egui::MenuBar::new().ui(ui, |ui| {
                    ui.menu_button("AI Tools", |ui| {
                        ui.label(egui::RichText::new("Android preview · Not connected").weak());
                        ui.separator();

                        // Disabled deliberately: enabling an item here would
                        // imply the model can process a document, which it can't.
                        for action in AiAction::ALL {
                            ui.add_enabled(false, egui::Button::new(action.label()))
                                .on_hover_text("Coming soon — no AI processing backend is connected.");
                        }
                        ui.separator();
                        ui.add_enabled(false, egui::Button::new("Plugin Manager…"));
                        ui.add_enabled(false, egui::Button::new("ComfyUI Connection…"));
                        if ui.button("About AI Tools…").clicked() {
                            self.show_about = true;
                            ui.close();
                        }
                    });
                });
            });

        if self.show_about {
            egui::Window::new("PhotoCraft Android · AI Tools")
                .id(egui::Id::new("photocraft_android_ai_about"))
                .open(&mut self.show_about)
                .resizable(false)
                .collapsible(false)
                .show(ctx, |ui| {
                    ui.heading("AI Tools — Preview");
                    ui.label("The native AI Tools menu has been added to the Android shell.");
                    ui.separator();
                    ui.label("Planned tools:");
                    for action in AiAction::ALL {
                        ui.label(format!("• {}", action.label()));
                    }
                    ui.separator();
                    ui.label("Status: No AI backend connected.");
                    ui.label("ComfyUI networking, model inference, and layer insertion are not yet implemented.");
                    ui.label("Nothing is uploaded, generated, or changed in your document by this menu.");
                    ui.label("The existing Filter menu, fonts, shortcuts, and document workflow are unchanged.");
                });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn five_tools_are_registered_but_never_executed_by_menu() {
        assert_eq!(AiAction::ALL.len(), 5);
        assert!(!AiAction::ALL.iter().any(|a| a.label().is_empty()));
        let menu = AndroidAiMenu::default();
        assert!(!menu.show_about);
    }
}
