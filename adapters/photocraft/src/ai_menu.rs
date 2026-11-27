//! Android-only AI Tools menu: read-only ComfyUI diagnostics plus an explicitly
//! consented experimental local U2NetP background removal workflow.
//! No upstream PhotoCraft crates, Android manifest, or signing files are changed.

use crate::ai_tools::{AiAction, ComfyEndpoint};
use crate::ai_background_editor;
use crate::ai_background_job::{Job, JobId};
use crate::ai_u2netp_transport;
use crate::pxc_client::PxcClient;
use photocraft_doc::Layer;
use photocraft_engine::Session;
use std::net::SocketAddr;
use crate::ai_models::{self, ModelInventory};
use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::time::Duration;

/// Persist only the non-sensitive visibility setting inside this app's
/// private files directory. This is separate from production PhotoCraft.
pub(crate) struct AndroidAiMenu {
    show_about: bool,
    show_connection: bool,
    show_background_setup: bool,
    show_txt2img: bool,
    cpu_token: String,
    cpu_consent: bool,
    cpu_status: String,
    cpu_result: Option<Receiver<Result<Layer, String>>>,
    cpu_cancellation: Option<Arc<AtomicBool>>,
    cpu_job: Option<Job>,
    cpu_next_job: u64,
    txt2img_prompt: String,
    txt2img_checkpoint: String,
    txt2img_seed: String,
    txt2img_result: Option<Receiver<Result<Layer, String>>>,
    txt2img_job: Option<Job>,
    txt2img_next_job: u64,
    endpoint_text: String,
    allow_private_lan: bool,
    connection_status: String,
    connection_ok: bool,
    connection_result: Option<Receiver<Result<(), String>>>,
    model_result: Option<Receiver<Result<ModelInventory, String>>>,
    model_status: String,
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
        // Keep visibility local to the Android shell; the protected v0.23.1 UI crate does not expose the newer menu visibility API.
        Self {
            show_about: false,
            show_connection: false,
            show_background_setup: false,
            show_txt2img: false,
            cpu_token: String::new(),
            cpu_consent: false,
            cpu_status: "No image has been processed.".into(),
            cpu_result: None,
            cpu_cancellation: None,
            cpu_job: None,
            cpu_next_job: 0,
            txt2img_prompt: String::new(),
            txt2img_checkpoint: String::new(),
            txt2img_seed: "0".into(),
            txt2img_result: None,
            txt2img_job: None,
            txt2img_next_job: 0,
            endpoint_text: String::new(),
            allow_private_lan: false,
            connection_status: "No connection tested.".into(),
            connection_ok: false,
            connection_result: None,
            model_result: None,
            model_status: "Model inventory has not been checked.".into(),
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

    /// Returns true after a new undoable layer is inserted so the host can
    /// synchronize PhotoCraft canvas caches before rendering the editor.
    pub(crate) fn show(&mut self, ui: &mut egui::Ui, session: &mut Session) -> bool {
        // A hidden AI Tools menu must not apply an invisible in-flight result.
        // Window → Show AI Tools can be toggled at any time.
        let layer_changed = self.poll_cpu_result(session, ui.ctx());
        let txt2img_changed = self.poll_txt2img_result(session, ui.ctx());
        let received = self.connection_result.as_ref().map(|rx| rx.try_recv());
        match received {
            Some(Ok(Ok(()))) => {
                self.connection_ok = true;
                self.connection_status = "Connected to ComfyUI. No image data was sent.".into();
                self.model_status = "Connected. Select Check Installed Models to inspect the catalog (read-only).".into();
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
        // The model check is separately requested by the user; never query
        // model folders automatically just because ComfyUI was reachable.
        let model_received = self.model_result.as_ref().map(|rx| rx.try_recv());
        match model_received {
            Some(Ok(Ok(inventory))) => {
                if self.connection_ok {
                    self.model_status = inventory.human_summary();
                }
                self.model_result = None;
            }
            Some(Ok(Err(error))) => {
                self.model_status = format!("Model inventory failed: {error}");
                self.model_result = None;
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.model_status = "Model inventory check stopped unexpectedly.".into();
                self.model_result = None;
            }
            Some(Err(TryRecvError::Empty)) => {
                ui.ctx().request_repaint_after(Duration::from_millis(200));
            }
            None => {}
        }
        self.persist_visibility(true);
        // egui 0.36 uses Panel::top instead of TopBottomPanel. Mount the
        // Android-only native menu in its own top strip, without editing the
        // upstream Filter menu or painting a floating palette.
        let ctx = ui.ctx().clone();
        egui::Panel::top("artcraft_photocraft_android_ai_menu").show(ui, |ui| {
            egui::MenuBar::new().ui(ui, |ui| {
                    ui.menu_button("AI Tools", |ui| {
                        ui.label(egui::RichText::new(if self.connection_ok {
                            "ComfyUI reachable · Local U2NetP preview is opt-in"
                        } else {
                            "Local U2NetP CPU preview · Optional ComfyUI test"
                        }).weak());
                        ui.separator();

                        // General AI features remain disabled. Background Removal
                        // Preview is a separately gated, explicit local CPU action.
                        for action in AiAction::ALL {
                            ui.add_enabled(false, egui::Button::new(action.label()))
                                .on_hover_text("Coming soon — no AI processing backend is connected.");
                        }
                        ui.separator();
                        if ui.button("Text to Image · PxC / ComfyUI…").clicked() {
                            self.show_txt2img = true;
                            ui.close();
                        }
                        if ui.button("Remove Background · Local CPU Preview…").clicked() {
                            self.show_background_setup = true;
                            ui.close();
                        }
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

        if self.show_txt2img {
            let mut open = self.show_txt2img;
            egui::Window::new("PhotoCraft · Text to Image · PxC / ComfyUI")
                .id(egui::Id::new("photocraft_android_pxc_txt2img"))
                .open(&mut open)
                .resizable(true)
                .collapsible(false)
                .show(&ctx, |ui| {
                    ui.heading("Text to Image");
                    ui.label("Runs inference on your explicitly configured private-LAN ComfyUI server. PhotoCraft stays the Android client.");
                    ui.separator();
                    ui.label("Prompt");
                    ui.add(egui::TextEdit::multiline(&mut self.txt2img_prompt)
                        .desired_rows(4)
                        .hint_text("Describe the image to generate…"));
                    ui.label("Checkpoint filename");
                    ui.add(egui::TextEdit::singleline(&mut self.txt2img_checkpoint)
                        .hint_text("Example: model.safetensors"));
                    ui.label("Seed (optional)");
                    ui.add(egui::TextEdit::singleline(&mut self.txt2img_seed)
                        .hint_text("0"));
                    ui.label("Server: configured in ComfyUI Connection. Private-LAN consent must be enabled and the connection tested.");
                    let pending = self.txt2img_result.is_some();
                    let enabled = self.connection_ok && !pending
                        && !self.txt2img_prompt.trim().is_empty()
                        && !self.txt2img_checkpoint.trim().is_empty()
                        && session.active().is_some();
                    if ui.add_enabled(enabled, egui::Button::new("Generate · Create New Undoable Layer")).clicked() {
                        self.start_txt2img_job(session, &ctx);
                    }
                    if pending && ui.button("Discard pending result").clicked() {
                        self.cancel_txt2img_job();
                    }
                    if !self.connection_ok {
                        ui.label("Connect to ComfyUI first.");
                    }
                    ui.label("The active document must be open and RGB 8-bit. The generated result is fully decoded before insertion.");
                });
            if !open {
                self.cancel_txt2img_job();
            }
            self.show_txt2img = open;
        }

        if self.show_background_setup {
            let mut open = self.show_background_setup;
            egui::Window::new("PhotoCraft · U2NetP Background Removal Preview")
                .id(egui::Id::new("photocraft_android_ai_background_setup"))
                .open(&mut open)
                .resizable(true)
                .collapsible(false)
                .show(&ctx, |ui| {
                    ui.heading("Remove Background · U2NetP CPU");
                    ui.label("Experimental: only a local Linux Lab server at 127.0.0.1:18793 is accepted.");
                    ui.label("The active RGB 8-bit image is sent to that server only after consent.");
                    ui.label("Maximum 4 million pixels / 24 MiB input. Result is a new undoable pixel layer.");
                    ui.label("Do not send private documents without reviewing this processing route.");
                    ui.separator();
                    ui.label("Paste the temporary bearer token displayed by the Linux Lab server.");
                    ui.add(egui::TextEdit::singleline(&mut self.cpu_token)
                        .password(true).hint_text("Temporary session token"));
                    ui.checkbox(&mut self.cpu_consent,
                        "I consent to locally process the currently active image (once)");
                    let pending = self.cpu_result.is_some();
                    if ui.add_enabled(!pending && self.cpu_consent &&
                        !self.cpu_token.is_empty() && session.active().is_some(),
                        egui::Button::new("Remove Background — Create New Layer")).clicked() {
                        self.start_cpu_job(session, &ctx);
                    }
                    if pending && ui.button("Cancel and discard pending result").clicked() {
                        self.cancel_cpu_job();
                    }
                    ui.separator();
                    ui.label(&self.cpu_status);
                    ui.label("Do not expose the CPU service to the LAN or public internet.");
                });
            if !open {
                // Closing the window is a cancellation, never permission to
                // insert a result after the consent dialog disappeared.
                self.cancel_cpu_job();
                self.cpu_consent = false;
                self.cpu_token.clear();
            }
            self.show_background_setup = open;
        }

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
                        self.model_status = "Model inventory cleared: endpoint changed.".into();
                    }
                    if ui.checkbox(&mut self.allow_private_lan,
                        "Allow a connection to a trusted private-LAN host (unencrypted HTTP)").changed() {
                        self.connection_ok = false;
                        self.model_status = "Model inventory cleared: connection consent changed.".into();
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
                    let model_pending = self.model_result.is_some();
                    if ui.add_enabled(self.connection_ok && !pending && !model_pending,
                        egui::Button::new("Check Installed Models (read-only)")).clicked() {
                        match ComfyEndpoint::parse(&self.endpoint_text, self.allow_private_lan) {
                            Ok(endpoint) => {
                                let (tx, rx) = mpsc::channel();
                                self.model_result = Some(rx);
                                self.model_status = "Checking ComfyUI checkpoints and upscale_models folders…".into();
                                std::thread::spawn(move || {
                                    let _ = tx.send(ai_models::inspect_models(&endpoint));
                                });
                                ctx.request_repaint_after(Duration::from_millis(200));
                            }
                            Err(error) => {
                                self.model_status = format!("Invalid model inventory endpoint: {error}");
                            }
                        }
                    }
                    ui.label(&self.model_status);
                    ui.label("No model download or installation occurs. Model counts do not establish CPU compatibility.");
                    ui.label("Keep Linux Lab visible in a floating window during these tests.");
                    ui.separator();
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
                    ui.label("Status: opt-in ComfyUI diagnostics and experimental loopback U2NetP background removal.");
                    ui.label("A separate explicit consent is required for every image sent to local Linux Lab.");
                    ui.label("Background removal creates an undoable layer only after full PNG decoding and stale-document checks.");
                    ui.label("Existing filters, fonts and keyboard shortcuts remain available.");
                });
        }
        layer_changed || txt2img_changed
    }

    fn cancel_txt2img_job(&mut self) {
        if self.txt2img_result.is_none() { return; }
        if let Some(mut job) = self.txt2img_job.take() {
            job.cancel();
        }
        self.txt2img_result = None;
    }

    fn start_txt2img_job(&mut self, session: &Session, ctx: &egui::Context) {
        if self.txt2img_result.is_some() {
            return;
        }
        let (document, origin) = match ai_background_editor::active_snapshot(session) {
            Ok(snapshot) => snapshot,
            Err(error) => {
                self.connection_status = error;
                return;
            }
        };
        let endpoint = match ComfyEndpoint::parse(&self.endpoint_text, self.allow_private_lan) {
            Ok(endpoint) if self.connection_ok => endpoint,
            _ => {
                self.connection_status = "Connect to ComfyUI before generating.".into();
                return;
            }
        };
        let checkpoint = self.txt2img_checkpoint.trim().to_owned();
        let prompt = self.txt2img_prompt.trim().to_owned();
        let seed = match self.txt2img_seed.trim().parse::<u64>() {
            Ok(value) => value,
            Err(_) => {
                self.connection_status = "Seed must be an unsigned integer.".into();
                return;
            }
        };
        self.txt2img_next_job = self.txt2img_next_job.wrapping_add(1);
        let job_id = JobId(self.txt2img_next_job);
        let mut job = Job::new(job_id, origin);
        if let Err(error) = job.consent() {
            self.connection_status = error.into();
            return;
        }
        let (tx, rx) = mpsc::channel();
        self.txt2img_job = Some(job);
        self.txt2img_result = Some(rx);
        self.connection_status = "Generating with PxC / ComfyUI…".into();
        std::thread::spawn(move || {
            let result = (|| {
                let client = PxcClient::new(endpoint);
                let generated = client.generate_text_to_image(
                    &checkpoint,
                    &prompt,
                    seed,
                    document.size.width,
                    document.size.height,
                ).map_err(|error| error.to_string())?;
                ai_background_editor::decode_generated_layer(&generated.image)
            })();
            let _ = tx.send(result);
        });
        ctx.request_repaint_after(Duration::from_millis(200));
    }

    fn poll_txt2img_result(&mut self, session: &mut Session, ctx: &egui::Context) -> bool {
        let received = self.txt2img_result.as_ref().map(|rx| rx.try_recv());
        match received {
            Some(Ok(result)) => {
                self.txt2img_result = None;
                let Some(mut job) = self.txt2img_job.take() else {
                    self.connection_status = "Discarded unexpected PxC result.".into();
                    return false;
                };
                match result {
                    Ok(layer) => {
                        if job.finish(job.id).is_err()
                            || !ai_background_editor::current_revision(session)
                                .is_some_and(|current| job.may_insert(current)) {
                            self.connection_status = "Document changed or generation cancelled; PxC result discarded.".into();
                            return false;
                        }
                        match ai_background_editor::insert_generated_undoable(session, job.origin, layer) {
                            Ok(()) => {
                                self.connection_status = "PxC image generated. New undoable AI layer inserted.".to_string();
                                return true;
                            }
                            Err(error) => self.connection_status = error,
                        }
                    }
                    Err(error) => {
                        job.fail();
                        self.connection_status = format!("PxC generation failed: {error}");
                    }
                }
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.txt2img_result = None;
                self.txt2img_job = None;
                self.connection_status = "PxC generation worker stopped unexpectedly.".into();
            }
            Some(Err(TryRecvError::Empty)) => {
                ctx.request_repaint_after(Duration::from_millis(200));
            }
            None => {}
        }
        false
    }

    fn cancel_cpu_job(&mut self) {
        if self.cpu_result.is_none() { return; }
        if let Some(cancel) = self.cpu_cancellation.take() {
            cancel.store(true, Ordering::Release);
        }
        if let Some(mut job) = self.cpu_job.take() {
            job.cancel();
        }
        self.cpu_result = None;
        self.cpu_status = "Cancelled: AI result discarded. CPU processing already started in Linux Lab may finish before another job can run.".into();
    }

    fn start_cpu_job(&mut self, session: &Session, ctx: &egui::Context) {
        // Consume the one-image checkbox before ANY export or network action.
        let consent = std::mem::take(&mut self.cpu_consent);
        if !consent || self.cpu_result.is_some() {
            self.cpu_status = "Explicit consent required before processing.".into();
            return;
        }
        let (document, origin) = match ai_background_editor::active_snapshot(session) {
            Ok(snapshot) => snapshot,
            Err(error) => { self.cpu_status = error; return; }
        };
        let token = self.cpu_token.clone();
        self.cpu_next_job = self.cpu_next_job.wrapping_add(1);
        let job_id = JobId(self.cpu_next_job);
        let mut job = Job::new(job_id, origin);
        if let Err(error) = job.consent() {
            self.cpu_status = error.into();
            return;
        }
        let endpoint = SocketAddr::from(([127, 0, 0, 1], 18793));
        let (tx, rx) = mpsc::channel();
        let cancellation = Arc::new(AtomicBool::new(false));
        self.cpu_cancellation = Some(Arc::clone(&cancellation));
        self.cpu_job = Some(job);
        self.cpu_result = Some(rx);
        self.cpu_status = "Exporting image and processing in local Linux Lab…".into();
        std::thread::spawn(move || {
            let result = (|| {
                let image_png = ai_background_editor::capture_png(&document)?;
                let output_png = ai_u2netp_transport::remove_background_with_cancel(
                    endpoint, &token, &image_png, true, &cancellation)?;
                ai_background_editor::decode_layer(&output_png, &document)
            })();
            let _ = tx.send(result);
        });
        ctx.request_repaint_after(Duration::from_millis(200));
    }

    fn poll_cpu_result(&mut self, session: &mut Session, ctx: &egui::Context) -> bool {
        let received = self.cpu_result.as_ref().map(|rx| rx.try_recv());
        match received {
            Some(Ok(result)) => {
                self.cpu_result = None;
                self.cpu_cancellation = None;
                let Some(mut job) = self.cpu_job.take() else {
                    self.cpu_status = "Discarded unexpected AI result.".into();
                    return false;
                };
                match result {
                    Ok(layer) => {
                        if job.finish(job.id).is_err() ||
                            !ai_background_editor::current_revision(session)
                                .is_some_and(|current| job.may_insert(current)) {
                            self.cpu_status =
                                "Document changed or job cancelled; AI result discarded.".into();
                            return false;
                        }
                        match ai_background_editor::insert_undoable(session, job.origin, layer) {
                            Ok(()) => {
                                self.cpu_status = "Background removed. New AI layer inserted; Undo/Redo is available.".into();
                                return true;
                            }
                            Err(error) => { self.cpu_status = error; }
                        }
                    }
                    Err(error) => {
                        job.fail();
                        self.cpu_status = format!("Background removal failed: {error}");
                    }
                }
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.cpu_result = None;
                self.cpu_cancellation = None;
                self.cpu_job = None;
                self.cpu_status = "Background removal worker stopped unexpectedly.".into();
            }
            Some(Err(TryRecvError::Empty)) => {
                ctx.request_repaint_after(Duration::from_millis(200));
            }
            None => {}
        }
        false
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
