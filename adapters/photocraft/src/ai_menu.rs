//! Android-only AI Tools menu: read-only ComfyUI diagnostics plus an explicitly
//! consented experimental local U2NetP background removal workflow.
//! No upstream PhotoCraft crates, Android manifest, or signing files are changed.

use crate::ai_tools::{AiAction, ComfyEndpoint};
use crate::ai_openfill_editor;
use crate::ai_openfill_local_transport;
use crate::ai_openfill_operations::{
    Dimensions as FillSize, DocVersion as FillDocVersion,
    JobDraft as FillDraft, Operation as FillOperation,
};
use crate::ai_background_editor;
use crate::ai_background_job::{Job, JobId};
use crate::ai_u2netp_transport;
use crate::openfill_remote::OpenFillPairing;
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
    linux_lab_mode: bool,
    show_openfill_setup: bool,
    fill_operation: Option<FillOperation>,
    fill_prompt: String,
    fill_model: String,
    fill_width: String,
    fill_height: String,
    fill_left: String,
    fill_top: String,
    fill_consent: bool,
    fill_status: String,
    fill_preflight: Option<Receiver<Result<(String, Option<FillDocVersion>), String>>>,
    fill_token: String,
    fill_running: Option<Receiver<Result<(FillDraft, Layer), String>>>,
    fill_cancel: Option<Arc<AtomicBool>>,
    openfill_code: String,
    openfill_status: String,
    openfill_consent: bool,
    openfill_result: Option<Receiver<Result<OpenFillPairing, String>>>,
    openfill_session: Option<OpenFillPairing>,
    show_background_setup: bool,
    cpu_token: String,
    cpu_consent: bool,
    cpu_status: String,
    cpu_result: Option<Receiver<Result<Layer, String>>>,
    cpu_cancellation: Option<Arc<AtomicBool>>,
    cpu_job: Option<Job>,
    cpu_next_job: u64,
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
        photocraft_ui_egui::menus::artcraft_set_ai_tools_visible(visible);
        Self {
            show_about: false,
            show_connection: false,
            linux_lab_mode: false,
            show_openfill_setup: false,
            fill_operation: None,
            fill_prompt: String::new(),
            fill_model: String::new(),
            fill_width: "1024".into(),
            fill_height: "1024".into(),
            fill_left: "0".into(),
            fill_top: "0".into(),
            fill_consent: false,
            fill_status: "No generation requested.".into(),
            fill_preflight: None,
            fill_token: String::new(),
            fill_running: None,
            fill_cancel: None,
            openfill_code: String::new(),
            openfill_status: "Remote GPU has not been paired.".into(),
            openfill_consent: false,
            openfill_result: None,
            openfill_session: None,
            show_background_setup: false,
            cpu_token: String::new(),
            cpu_consent: false,
            cpu_status: "No image has been processed.".into(),
            cpu_result: None,
            cpu_cancellation: None,
            cpu_job: None,
            cpu_next_job: 0,
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

    /// Pc launcher menu actions 37–40 open operation-specific inputs.
    /// Actual Generate is NOT enabled until a verified local AI transport exists.
    pub(crate) fn open_openfill_operation(&mut self, code: u8) {
        self.cancel_fill_generation();
        self.fill_operation = match code {
            37 => Some(FillOperation::Fill),
            38 => Some(FillOperation::RemoveObject),
            39 => Some(FillOperation::GenerativeExpand),
            40 => Some(FillOperation::Create),
            _ => return,
        };
        self.fill_prompt.clear();
        self.fill_model.clear();
        self.fill_consent = false;
        self.fill_preflight = None;
        self.fill_status = "Enter the request and choose Validate (offline) or Generate (Linux Lab).".into();
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
        if !photocraft_ui_egui::menus::artcraft_ai_tools_visible() {
            self.cancel_cpu_job();
            self.cpu_consent = false;
        }
        let background_changed = self.poll_cpu_result(session, ui.ctx());
        let fill_changed = self.poll_fill_generation(session, ui.ctx());
        let layer_changed = background_changed || fill_changed;
        self.poll_fill_preflight(session, ui.ctx());
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
        // OpenFill remote GPU handshake is read-only. No pixels or prompts
        // are uploaded, and the pairing token stays in memory for this session.
        let remote_received = self.openfill_result.as_ref().map(|rx| rx.try_recv());
        match remote_received {
            Some(Ok(Ok(pair))) => {
                self.openfill_session = Some(pair);
                self.openfill_status = "OpenFill remote GPU verified for this session. Generative jobs are not wired up yet.".into();
                self.openfill_result = None;
            }
            Some(Ok(Err(error))) => {
                self.openfill_session = None;
                self.openfill_status = format!("Remote GPU check failed: {error}");
                self.openfill_result = None;
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.openfill_session = None;
                self.openfill_status = "Remote GPU check ended unexpectedly.".into();
                self.openfill_result = None;
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
        let visible = photocraft_ui_egui::menus::artcraft_ai_tools_visible();
        self.persist_visibility(visible);
        if !visible { return layer_changed; }
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
                        if ui.button("Remove Background · Local CPU Preview…").clicked() {
                            self.show_background_setup = true;
                            ui.close();
                        }
                        ui.add_enabled(false, egui::Button::new("Plugin Manager…"));
                        if ui.button("ComfyUI Connection…").clicked() {
                            self.linux_lab_mode = false;
                            self.show_connection = true;
                            ui.close();
                        }
                        if ui.button("Linux Lab · Local ComfyUI (Preview)…").clicked() {
                            self.linux_lab_mode = true;
                            // Running Linux Lab on this tablet normally shares
                            // Android's loopback namespace with PhotoCraft.
                            // Configure localhost only; never silently switch
                            // an existing private-LAN endpoint to a local one.
                            self.endpoint_text = "http://127.0.0.1:8188".into();
                            self.allow_private_lan = false;
                            self.connection_ok = false;
                            self.connection_status = "Linux Lab selected. Start ComfyUI there and tap Test Connection.".into();
                            self.model_status = "No local models checked yet.".into();
                            self.model_result = None;
                            self.connection_result = None;
                            self.show_connection = true;
                            ui.close();
                        }
                        if ui.button("OpenFill Remote GPU (Preview)…").clicked() {
                            self.show_openfill_setup = true;
                            ui.close();
                        }
                        if ui.button("About AI Tools…").clicked() {
                            self.show_about = true;
                            ui.close();
                        }
                    });
            });
        });


        if let Some(operation) = self.fill_operation {
            let caption = match operation {
                FillOperation::Fill => "Fill with Prompt",
                FillOperation::RemoveObject => "Remove Object",
                FillOperation::GenerativeExpand => "Generative Expand",
                FillOperation::Create => "Create · Text to Image",
            };
            let mut open = true;
            egui::Window::new(format!("PhotoCraft · OpenFill · {caption}"))
                .id(egui::Id::new("pc_openfill_four_operation_window"))
                .open(&mut open)
                .resizable(true).collapsible(false)
                .show(&ctx, |ui| {
                    ui.heading(caption);
                    ui.label("Generate only through your tablet-local Linux Lab OpenFill service and a licensed installed model.");
                    if operation != FillOperation::Create {
                        if let Some(active) = session.active() {
                            ui.label(format!("Current canvas: {} × {} px",
                                active.doc.size.width, active.doc.size.height));
                        } else {
                            ui.weak("Open an image first.");
                        }
                    }
                    if operation != FillOperation::RemoveObject {
                        ui.label("Prompt");
                        ui.add(egui::TextEdit::multiline(&mut self.fill_prompt)
                            .desired_rows(2).hint_text("Describe the result"));
                    } else {
                        ui.label("Select the object using a marquee or lasso.");
                    }
                    ui.label("OpenFill model identifier (backend/model license not verified)");
                    ui.add(egui::TextEdit::singleline(&mut self.fill_model)
                        .hint_text("Installed model ID"));
                    ui.label("Linux Lab OpenFill token (from local server at 127.0.0.1:18794)");
                    ui.add(egui::TextEdit::singleline(&mut self.fill_token)
                        .password(true).hint_text("Temporary session token"));
                    if matches!(operation, FillOperation::GenerativeExpand | FillOperation::Create) {
                        ui.horizontal(|ui| {
                            ui.label("Output width");
                            ui.text_edit_singleline(&mut self.fill_width);
                            ui.label("Height");
                            ui.text_edit_singleline(&mut self.fill_height);
                        });
                    }
                    if operation == FillOperation::GenerativeExpand {
                        ui.horizontal(|ui| {
                            ui.label("Source left");
                            ui.text_edit_singleline(&mut self.fill_left);
                            ui.label("Top");
                            ui.text_edit_singleline(&mut self.fill_top);
                        });
                        ui.label("Expand must preserve every original image pixel.");
                    }
                    ui.checkbox(&mut self.fill_consent,
                        "I permit this operation to send my image/mask and prompt to my tablet-local Linux Lab (never cloud)");
                    let busy = self.fill_preflight.is_some() || self.fill_running.is_some();
                    if ui.add_enabled(!busy && self.fill_consent,
                        egui::Button::new("Validate Request (Offline)")).clicked() {
                        self.start_fill_preflight(operation, session, &ctx);
                    }
                    if ui.add_enabled(!busy && self.fill_consent && self.fill_token.len() >= 32,
                        egui::Button::new("Generate in Linux Lab…")).clicked() {
                        self.start_fill_generation(operation, session, &ctx);
                    }
                    if self.fill_running.is_some() && ui.button("Cancel Generation").clicked() {
                        self.cancel_fill_generation();
                    }
                    if busy { ui.spinner(); }
                    ui.label(&self.fill_status);
                    ui.weak("Generates only through your token-protected tablet-local Linux Lab OpenFill server. An installed compatible model is required. A model result is never applied after source changes.");
                });
            if !open {
                self.fill_operation = None;
                self.fill_preflight = None;
                self.fill_consent = false;
                self.cancel_fill_generation();
                self.fill_token.clear();
            }
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
                    ui.label("Up to 20 megapixels / 64 MiB input (experimental). Above 4 MP, CPU AI analyzes a smaller copy; a full-resolution alpha result preserves original RGB pixels. New undoable layer.");
                    if let Some(active) = session.active() {
                        let w = active.doc.size.width;
                        let h = active.doc.size.height;
                        ui.label(format!("Current document: {w} x {h} ({:.2} MP)", f64::from(w) * f64::from(h) / 1_000_000.0));
                    }
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

        if self.show_openfill_setup {
            let mut open = self.show_openfill_setup;
            egui::Window::new("PhotoCraft · OpenFill Remote GPU Preview")
                .id(egui::Id::new("photocraft_android_openfill_remote_gpu"))
                .open(&mut open)
                .resizable(true)
                .collapsible(false)
                .show(&ctx, |ui| {
                    ui.heading("OpenFill · Remote GPU");
                    ui.label("Connection test only. Generative Fill, Remove Object, Expand and Create are not yet enabled.");
                    ui.label("Install OpenFill's GPU server on a separate computer with ComfyUI and connect both devices through Tailscale.");
                    ui.label("Paste its complete pairing code (a password). It is kept in memory, never saved.");
                    if ui.add(egui::TextEdit::singleline(&mut self.openfill_code)
                        .password(true)
                        .hint_text("ofgpu://TOKEN@100.x.y.z:8390")).changed() {
                        self.openfill_session = None;
                        self.openfill_status = "Pairing details changed. Test again.".into();
                    }
                    ui.checkbox(&mut self.openfill_consent,
                        "Tailscale is connected; I permit sending this pairing token to that GPU server");
                    ui.label("A 100.x address alone does not prove a VPN is active. Never paste a code for a stranger's server.");
                    let pending = self.openfill_result.is_some();
                    if ui.add_enabled(!pending && self.openfill_consent,
                        egui::Button::new("Check Paired GPU (No Image Upload)")).clicked() {
                        self.openfill_session = None;
                        // The connection code is validated before any network activity.
                        match OpenFillPairing::parse(&self.openfill_code) {
                            Ok(pair) => {
                                self.openfill_code.clear();
                                self.openfill_consent = false;
                                let (tx, rx) = mpsc::channel();
                                self.openfill_result = Some(rx);
                                self.openfill_status = "Checking authenticated /system_stats on your remote GPU…".into();
                                std::thread::spawn(move || {
                                    let outcome = pair.probe_system_stats();
                                    let _ = tx.send(outcome.map(|()| pair));
                                });
                                ctx.request_repaint_after(Duration::from_millis(200));
                            }
                            Err(error) => {
                                self.openfill_status = format!("Invalid pairing: {error}");
                            }
                        }
                    }
                    if pending {
                        ui.label("Remote GPU handshake in progress…");
                    }
                    ui.separator();
                    ui.label(&self.openfill_status);
                    ui.label("No image, mask, selection, prompt or document leaves the tablet in this preview.");
                    ui.label("OpenFill image-generation backend and model licenses need separate implementation and validation.");
                });
            if !open {
                // Closing revokes the connection. Discard late results.
                self.openfill_code.clear();
                self.openfill_consent = false;
                self.openfill_result = None;
                self.openfill_session = None;
            }
            self.show_openfill_setup = open;
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
                    ui.label("Read-only ComfyUI connection diagnostics. AI generation remains disabled.");
                    if self.linux_lab_mode {
                        // Local mode is pinned to the tablet's loopback address.
                        // Do not display a private-LAN consent control or accept
                        // external IPs in the dedicated Linux Lab workflow.
                        self.endpoint_text = "http://127.0.0.1:8188".into();
                        self.allow_private_lan = false;
                        ui.label("Linux Lab on this tablet · 127.0.0.1:8188");
                        ui.label("Local loopback only; no private Wi-Fi IP or LAN permission is needed.");
                    } else {
                        ui.label("Enter a trusted computer's private Wi-Fi IP address, e.g. http://192.168.1.20:8188");
                        ui.label("127.0.0.1 means this tablet, not another computer.");
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
        layer_changed
    }


    fn start_fill_preflight(
        &mut self, operation: FillOperation, session: &Session, ctx: &egui::Context,
    ) {
        if self.fill_preflight.is_some() { return; }
        let consent = std::mem::take(&mut self.fill_consent);
        if !consent {
            self.fill_status = "Explicit local validation consent required.".into();
            return;
        }
        let snapshot = if operation == FillOperation::Create {
            None
        } else {
            match ai_background_editor::active_snapshot(session) {
                Ok(pair) => Some(pair),
                Err(error) => { self.fill_status = error; return; }
            }
        };
        let numeric = |value: &str| value.parse::<u32>();
        let result = if matches!(operation, FillOperation::Create | FillOperation::GenerativeExpand) {
            match (numeric(&self.fill_width), numeric(&self.fill_height),
                   numeric(&self.fill_left), numeric(&self.fill_top)) {
                (Ok(width), Ok(height), Ok(left), Ok(top)) =>
                    Ok((FillSize { width, height }, left, top)),
                _ => Err("Width, height and offsets must be valid unsigned integers"),
            }
        } else {
            match snapshot.as_ref() {
                Some((doc, _)) => Ok((FillSize {
                    width: doc.size.width, height: doc.size.height,
                }, 0, 0)),
                None => Err("Open an image first"),
            }
        };
        let (output, offset_x, offset_y) = match result {
            Ok(value) => value,
            Err(error) => { self.fill_status = error.into(); return; }
        };
        let prompt = self.fill_prompt.clone();
        let model_id = self.fill_model.clone();
        let (tx, rx) = mpsc::channel();
        self.fill_preflight = Some(rx);
        self.fill_status = "Validating real selection coverage without network activity…".into();
        std::thread::spawn(move || {
            let validation = (|| -> Result<(String, Option<FillDocVersion>), String> {
                let source = snapshot.as_ref().map(|(_, rev)| FillDocVersion {
                    document: rev.document, revision: rev.revision,
                });
                let input = snapshot.as_ref().map(|(doc, _)| FillSize {
                    width: doc.size.width, height: doc.size.height,
                });
                let selected_pixels = if matches!(operation,
                    FillOperation::Fill | FillOperation::RemoveObject)
                {
                    let (doc, rev) = snapshot.as_ref()
                        .ok_or("A source image is required")?;
                    ai_background_editor::capture_masked_fill(doc, *rev, true)?
                        .selected_pixels()
                } else { 0 };
                let draft = FillDraft {
                    operation, source, input, output, offset_x, offset_y,
                    selected_pixels, prompt, model_id,
                };
                let checked = draft.validate_intent(true).map_err(str::to_owned)?;
                if operation == FillOperation::GenerativeExpand {
                    let _ = draft.expansion_mask(true).map_err(str::to_owned)?;
                }
                Ok((format!("Offline request validated: {:?} · {} × {} px. Model readiness and inference still unverified.",
                    checked.kind, output.width, output.height), source))
            })();
            let _ = tx.send(validation);
        });
        ctx.request_repaint_after(Duration::from_millis(200));
    }

    fn poll_fill_preflight(&mut self, session: &Session, ctx: &egui::Context) {
        let received = self.fill_preflight.as_ref().map(|rx| rx.try_recv());
        match received {
            Some(Ok(Ok((text, source)))) => {
                self.fill_preflight = None;
                let live = ai_background_editor::current_revision(session).map(|rev|
                    FillDocVersion { document: rev.document, revision: rev.revision });
                self.fill_status = if source.is_some() && source != live {
                    "Document changed during validation. Request discarded.".into()
                } else { text };
            }
            Some(Ok(Err(error))) => {
                self.fill_preflight = None;
                self.fill_status = format!("Request rejected: {error}");
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.fill_preflight = None;
                self.fill_status = "Local validation worker disconnected.".into();
            }
            Some(Err(TryRecvError::Empty)) => ctx.request_repaint_after(Duration::from_millis(200)),
            None => {}
        }
    }


    fn cancel_fill_generation(&mut self) {
        if let Some(cancel) = self.fill_cancel.take() {
            cancel.store(true, Ordering::Release);
            self.fill_status = "Cancelled. AI output will be discarded.".into();
        }
        self.fill_running = None;
    }

    fn start_fill_generation(
        &mut self, operation: FillOperation, session: &Session, ctx: &egui::Context,
    ) {
        if self.fill_running.is_some() || self.fill_preflight.is_some() { return; }
        let consent = std::mem::take(&mut self.fill_consent);
        if !consent {
            self.fill_status = "Explicit consent is required for this generation.".into();
            return;
        }
        let snapshot = if operation == FillOperation::Create {
            None
        } else {
            match ai_background_editor::active_snapshot(session) {
                Ok(value) => Some(value),
                Err(error) => { self.fill_status = error; return; }
            }
        };
        let parse = |s: &str| s.parse::<u32>();
        let shape = if matches!(operation, FillOperation::Create | FillOperation::GenerativeExpand) {
            match (parse(&self.fill_width), parse(&self.fill_height),
                   parse(&self.fill_left), parse(&self.fill_top)) {
                (Ok(width), Ok(height), Ok(left), Ok(top)) =>
                    Ok((FillSize { width, height }, left, top)),
                _ => Err("Output dimensions or offsets are invalid"),
            }
        } else {
            match snapshot.as_ref() {
                Some((doc, _)) => Ok((FillSize {
                    width: doc.size.width, height: doc.size.height,
                }, 0, 0)),
                None => Err("Open an image first"),
            }
        };
        let (output, offset_x, offset_y) = match shape {
            Ok(value) => value,
            Err(error) => { self.fill_status = error.into(); return; }
        };
        // Right/bottom expansion is non-destructive with no changes to any
        // existing layers. Shifting all existing layers for top/left expansion
        // is intentionally refused until its own full geometry tests pass.
        if operation == FillOperation::GenerativeExpand && (offset_x != 0 || offset_y != 0) {
            self.fill_status = "Expand currently supports right/bottom only (left=0, top=0).".into();
            return;
        }
        let prompt = if operation == FillOperation::RemoveObject {
            String::new()
        } else { self.fill_prompt.clone() };
        let model_id = self.fill_model.clone();
        let token = self.fill_token.clone();
        let (tx, rx) = mpsc::channel();
        let cancellation = Arc::new(AtomicBool::new(false));
        self.fill_cancel = Some(Arc::clone(&cancellation));
        self.fill_running = Some(rx);
        self.fill_status = "Capturing image locally; waiting for Linux Lab inference…".into();
        std::thread::spawn(move || {
            let result = (|| -> Result<(FillDraft, Layer), String> {
                let source = snapshot.as_ref().map(|(_, rev)| FillDocVersion {
                    document: rev.document, revision: rev.revision,
                });
                let input = snapshot.as_ref().map(|(doc, _)| FillSize {
                    width: doc.size.width, height: doc.size.height,
                });
                let selected = if matches!(operation,
                    FillOperation::Fill | FillOperation::RemoveObject)
                {
                    let (doc, rev) = snapshot.as_ref().ok_or("No source image selected")?;
                    Some(ai_background_editor::capture_masked_fill(doc, *rev, true)?)
                } else { None };
                let draft = FillDraft {
                    operation, source, input, output, offset_x, offset_y,
                    selected_pixels: selected.as_ref().map(|s| s.selected_pixels()).unwrap_or(0),
                    prompt, model_id,
                };
                draft.validate_intent(true).map_err(str::to_owned)?;
                if cancellation.load(Ordering::Acquire) {
                    return Err("Generation cancelled".into());
                }
                let flat = if operation == FillOperation::GenerativeExpand {
                    let (doc, rev) = snapshot.as_ref().ok_or("Missing Expand image")?;
                    ai_openfill_editor::capture_source_rgba(doc, *rev)?
                } else { Vec::new() };
                let source_rgba = selected.as_ref()
                    .map(|s| s.immutable_source_rgba()).unwrap_or(flat.as_slice());
                let mask_alpha = selected.as_ref()
                    .map(|s| s.immutable_mask_alpha()).unwrap_or(&[]);
                let png = ai_openfill_local_transport::generate(
                    &draft, source_rgba, mask_alpha, &token, true, &cancellation,
                )?;
                if cancellation.load(Ordering::Acquire) {
                    return Err("Generation cancelled".into());
                }
                let layer = match operation {
                    FillOperation::Fill | FillOperation::RemoveObject => {
                        ai_openfill_editor::prepare_masked_layer(
                            &draft, selected.as_ref().ok_or("Selection missing")?, &png
                        )?
                    }
                    FillOperation::GenerativeExpand => {
                        ai_openfill_editor::prepare_expand_layer(&draft, &png)?
                    }
                    FillOperation::Create => {
                        let rgba = ai_openfill_editor::decode_output_png(&png, draft.output)?;
                        ai_openfill_editor::new_layer("AI · Create", draft.output, &rgba)?
                    }
                };
                Ok((draft, layer))
            })();
            let _ = tx.send(result);
        });
        ctx.request_repaint_after(Duration::from_millis(200));
    }

    fn poll_fill_generation(&mut self, session: &mut Session, ctx: &egui::Context) -> bool {
        let received = self.fill_running.as_ref().map(|rx| rx.try_recv());
        match received {
            Some(Ok(Ok((draft, layer)))) => {
                self.fill_running = None;
                self.fill_cancel = None;
                let result = ai_openfill_editor::validate_live(session, &draft);
                if let Err(error) = result {
                    self.fill_status = format!("Generation discarded: {error}");
                    return false;
                }
                let inserted = if draft.operation == FillOperation::Create {
                    ai_openfill_editor::commit_create(session, &draft, layer)
                } else {
                    ai_openfill_editor::commit_layer(session, &draft, layer)
                };
                match inserted {
                    Ok(()) => {
                        self.fill_status = "OpenFill generated an undoable result. Use Undo/Redo to review.".into();
                        return true;
                    }
                    Err(error) => {
                        self.fill_status = format!("Result was not applied: {error}");
                    }
                }
            }
            Some(Ok(Err(error))) => {
                self.fill_running = None;
                self.fill_cancel = None;
                self.fill_status = format!("OpenFill generation failed: {error}");
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.fill_running = None;
                self.fill_cancel = None;
                self.fill_status = "OpenFill worker disconnected; no editor change.".into();
            }
            Some(Err(TryRecvError::Empty)) => ctx.request_repaint_after(Duration::from_millis(200)),
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
