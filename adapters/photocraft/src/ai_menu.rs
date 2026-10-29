//! Android-only AI Tools menu. The only live Phase-2 action is an explicitly
//! requested ComfyUI reachability test; model and document actions are disabled.
//! No upstream PhotoCraft crates, Android manifest, or signing files are changed.

use crate::ai_tools::{AiAction, ComfyEndpoint};
use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::time::Duration;

/// Persist only the non-sensitive visibility setting inside this app's
/// private files directory. This is separate from production PhotoCraft.
pub(crate) struct AndroidAiMenu {
    show_about: bool,
    show_connection: bool,
    endpoint_text: String,
    allow_private_lan: bool,
    connection_status: String,
    connection_ok: bool,
    connection_result: Option<Receiver<Result<(), String>>>,
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
        Self {
            show_about: false,
            show_connection: false,
            endpoint_text: String::new(),
            allow_private_lan: false,
            connection_status: "No connection tested.".into(),
            connection_ok: false,
            connection_result: None,
            last_visible: visible,
            preference_path,
        }
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
        let received = self.connection_result.as_ref().map(|rx| rx.try_recv());
        match received {
            Some(Ok(Ok(()))) => {
                self.connection_ok = true;
                self.connection_status = "Connected to ComfyUI. No image data was sent.".into();
                self.connection_result = None;
            }
            Some(Ok(Err(error))) => {
                self.connection_ok = false;
                self.connection_status = format!("Connection test failed: {error}");
                self.connection_result = None;
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.connection_ok = false;
                self.connection_status = "Connection test ended unexpectedly.".into();
                self.connection_result = None;
            }
            Some(Err(TryRecvError::Empty)) => {
                ui.ctx().request_repaint_after(Duration::from_millis(200));
            }
            None => {}
        }
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
                        ui.label(egui::RichText::new(if self.connection_ok {
                            "ComfyUI reachable · AI processing disabled"
                        } else {
                            "AI processing disabled · Optional backend test"
                        }).weak());
                        ui.separator();

                        // Disabled deliberately: enabling an item here would
                        // imply the model can process a document, which it can't.
                        for action in AiAction::ALL {
                            ui.add_enabled(false, egui::Button::new(action.label()))
                                .on_hover_text("Coming soon — no AI processing backend is connected.");
                        }
                        ui.separator();
                        ui.add_enabled(false, egui::Button::new("Plugin Manager…"));
                        if ui.button("ComfyUI Connection…").clicked() {
                            self.show_connection = true;
                            ui.close();
                        }
                        if ui.button("About AI Tools…").clicked() {
                            self.show_about = true;
                            ui.close();
                        }
                    });
            });
        });

        if self.show_connection {
            // open() borrows a local variable rather than self, so inputs in
            // this UI can be edited without conflicting mutable borrows.
            let mut open = self.show_connection;
            egui::Window::new("PhotoCraft · ComfyUI Connection")
                .id(egui::Id::new("photocraft_android_comfyui_connection"))
                .open(&mut open)
                .resizable(true)
                .collapsible(false)
                .show(&ctx, |ui| {
                    ui.label("Optional local ComfyUI server — connection diagnostics only.");
                    ui.label("Enter the computer's private Wi-Fi IP address, e.g. http://192.168.1.20:8188");
                    ui.label("127.0.0.1 means this tablet, not your Mac or PC.");
                    if ui.add(egui::TextEdit::singleline(&mut self.endpoint_text)
                        .hint_text("http://192.168.1.20:8188")).changed() {
                        self.connection_ok = false;
                        self.connection_status = "Endpoint changed. Test again.".into();
                    }
                    if ui.checkbox(&mut self.allow_private_lan,
                        "Allow a connection to a trusted private-LAN host (unencrypted HTTP)").changed() {
                        self.connection_ok = false;
                    }
                    ui.label("No image, document, selection, prompt, model or password is transmitted.");
                    ui.label("Do not expose ComfyUI directly to the internet.");
                    let pending = self.connection_result.is_some();
                    if ui.add_enabled(!pending, egui::Button::new("Test Connection")).clicked() {
                        self.connection_ok = false;
                        match ComfyEndpoint::parse(&self.endpoint_text, self.allow_private_lan) {
                            Ok(endpoint) => {
                                let (tx, rx) = mpsc::channel();
                                self.connection_result = Some(rx);
                                self.connection_status = "Testing ComfyUI /system_stats…".into();
                                std::thread::spawn(move || {
                                    let _ = tx.send(endpoint.probe_system_stats());
                                });
                                ctx.request_repaint_after(Duration::from_millis(200));
                            }
                            Err(error) => {
                                self.connection_status = format!("Invalid endpoint: {error}");
                            }
                        }
                    }
                    ui.separator();
                    ui.label(&self.connection_status);
                    ui.label("Background Removal and Generative Fill remain disabled until non-destructive layer integration is verified.");
                });
            self.show_connection = open;
        }

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
                    ui.label("Status: ComfyUI connection testing is available (opt-in).");
                    ui.label("Model inference, image uploads and non-destructive layer insertion are not implemented.");
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
