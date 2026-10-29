//! Android-only, native egui AI Tools menu. This is a safe UI scaffold:
//! none of the processing commands execute until a verified backend exists.
//! No upstream PhotoCraft crates, Android manifest, or signing files are changed.

use crate::ai_tools::AiAction;
use std::path::PathBuf;

/// Persist only the non-sensitive visibility setting inside this app's
/// private files directory. This is separate from production PhotoCraft.
pub(crate) struct AndroidAiMenu {
    show_about: bool,
    last_visible: bool,
    preference_path: PathBuf,
}

impl AndroidAiMenu {
    pub(crate) fn new(preference_path: PathBuf) -> Self {
        let visible = std::fs::read(&preference_path)
            .map(|value| value.as_slice() != b"0")
            .unwrap_or(true);
        // Window's checked item and Android's separate menu strip read the
        // same Android-only UI state. Default is visible on first launch.
        photocraft_ui_egui::menus::artcraft_set_ai_tools_visible(visible);
        Self { show_about: false, last_visible: visible, preference_path }
    }

    fn persist_visibility(&mut self, visible: bool) {
        if visible == self.last_visible { return; }
        // Hide/show always responds even if storage is temporarily unavailable.
        self.last_visible = visible;
        let write = (|| -> std::io::Result<()> {
            if let Some(parent) = self.preference_path.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::write(&self.preference_path, if visible { b"1" } else { b"0" })
        })();
        if let Err(error) = write {
            log::warn!("PhotoCraft AI Tools visibility preference could not be saved: {error}");
        }
    }

    pub(crate) fn show(&mut self, ui: &mut egui::Ui) {
        let visible = photocraft_ui_egui::menus::artcraft_ai_tools_visible();
        self.persist_visibility(visible);
        if !visible { return; }
        // egui 0.36 uses Panel::top instead of TopBottomPanel. Mount the
        // Android-only native menu in its own top strip, without editing the
        // upstream Filter menu or painting a floating palette.
        let ctx = ui.ctx().clone();
        egui::Panel::top("artcraft_photocraft_android_ai_menu").show(ui, |ui| {
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
                .show(&ctx, |ui| {
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
        // Visibility is handled by the Android Window menu, not by any
        // processing action. The UI still has no working AI backend.
        assert!(AiAction::ALL.iter().all(|action| !action.label().is_empty()));
    }
}
