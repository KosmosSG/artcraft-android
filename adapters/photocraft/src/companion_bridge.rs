//! Opt-in, loopback-only PhotoCraft Companion control transport for Android.
//! Based on the published PhotoCraft v0.23.1 control protocol and the
//! kobaltgit/photocraft-companion JSON-lines client format (MIT).
//! No external address, automatic startup, model installation or silent edits.

use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc::Sender, Arc};
use std::time::{Duration, Instant};

use crate::AndroidFileBridge;
use photocraft_ui_egui::ControlRequest;
use serde_json::{json, Value};

const PORT: u16 = 18492;
const MAX_REQUEST: usize = 64 * 1024;
const MAX_RESPONSE: usize = 2 * 1024 * 1024;
const REQUEST_TIMEOUT: Duration = Duration::from_secs(25);

/// In-app toolstrip never accepts arbitrary commands or exposes the pairing token.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum ToolstripAction {
    Inspect,
    Undo,
    Redo,
}

// Pure safety guard shared by the floating buttons. Only an explicit on-device
// approval unlocks the toolstrip's edit commands; B&W also requires confirmation.
fn tool_action_allowed(
    action: ToolstripAction,
    has_document: bool,
    edits_allowed: bool,
) -> bool {
    has_document && (action == ToolstripAction::Inspect || edits_allowed)
}


pub(crate) struct CompanionBridge {
    sender: Sender<ControlRequest>,
    clipboard: AndroidFileBridge,
    copy_status: Option<String>,
    running: Option<Arc<AtomicBool>>,
    token: String,
    status: String,
    pub(crate) show_window: bool,
    writes_enabled: Arc<AtomicBool>,
    macro_confirmed: bool,
    pending_macro: bool,
    macro_status: String,
    toolstrip_visible: bool,
    toolstrip_vertical: bool,
    toolstrip_scale: f32,
    toolstrip_opacity: f32,
    toolstrip_confirmed: bool,
    pending_toolstrip_action: Option<ToolstripAction>,
    toolstrip_status: String,
}

impl CompanionBridge {
    pub(crate) fn new(sender: Sender<ControlRequest>, clipboard: AndroidFileBridge) -> Self {
        Self {
            sender,
            clipboard,
            copy_status: None,
            running: None,
            token: String::new(),
            status: "Off. No local control port is listening.".to_owned(),
            show_window: false,
            writes_enabled: Arc::new(AtomicBool::new(false)),
            macro_confirmed: false,
            pending_macro: false,
            macro_status: "No Companion macro has been run.".to_owned(),
            // Off by default; this egui window floats inside PhotoCraft, not over Android apps.
            toolstrip_visible: false,
            toolstrip_vertical: false,
            toolstrip_scale: 0.85,
            toolstrip_opacity: 0.90,
            toolstrip_confirmed: false,
            pending_toolstrip_action: None,
            toolstrip_status: "Ready for read-only inspection.".to_owned(),
        }
    }

    fn start(&mut self, ctx: &egui::Context) {
        self.copy_status = None;
        if self.running.is_some() {
            return;
        }
        // A cryptographically random, one-session bearer token: never write it
        // to the APK, to logs or to unencrypted persistent preferences.
        let token = match random_token() {
            Ok(token) => token,
            Err(e) => {
                self.status = format!("Companion disabled: secure token unavailable: {e}");
                return;
            }
        };
        let listener = match TcpListener::bind(("127.0.0.1", PORT)) {
            Ok(listener) => listener,
            Err(e) => {
                self.status = format!("Companion disabled: localhost:{PORT} unavailable: {e}");
                return;
            }
        };
        if let Err(e) = listener.set_nonblocking(true) {
            self.status = format!("Companion disabled: cannot secure listener: {e}");
            return;
        }
        let stop = Arc::new(AtomicBool::new(false));
        let worker_stop = Arc::clone(&stop);
        let sender = self.sender.clone();
        let worker_ctx = ctx.clone();
        let worker_token = token.clone();
        let worker_writes = Arc::clone(&self.writes_enabled);
        match std::thread::Builder::new()
            .name("photocraft-companion-loopback".into())
            .spawn(move || {
                while !worker_stop.load(Ordering::Acquire) {
                    match listener.accept() {
                        Ok((stream, peer)) if peer.ip().is_loopback() => {
                            serve_client(stream, &worker_token, &sender, &worker_ctx, &worker_stop, &worker_writes);
                        }
                        Ok(_) => {} // Defense in depth; listener is already loopback-only.
                        Err(e) if e.kind() == io::ErrorKind::WouldBlock => {
                            std::thread::sleep(Duration::from_millis(100));
                        }
                        Err(_) => break,
                    }
                }
            })
        {
            Ok(_) => {
                self.token = token;
                self.running = Some(stop);
                self.status = format!("Local Companion bridge enabled at 127.0.0.1:{PORT}");
            }
            Err(e) => {
                self.status = format!("Companion disabled: could not start thread: {e}");
            }
        }
    }

    fn stop(&mut self) {
        self.copy_status = None;
        self.toolstrip_confirmed = false;
        self.pending_toolstrip_action = None;
        self.writes_enabled.store(false, Ordering::Release);
        self.macro_confirmed = false;
        self.pending_macro = false;
        if let Some(stop) = self.running.take() {
            stop.store(true, Ordering::Release);
        }
        self.token.clear();
        self.status = "Off. No new Companion commands will be accepted.".to_owned();
    }


    /// Draw after the native editor, so the draggable egui window stays above
    /// the canvas. No SYSTEM_ALERT_WINDOW, extra Android Activity or hidden IO.
    pub(crate) fn show_toolstrip(&mut self, ctx: &egui::Context, has_document: bool) {
        if !self.toolstrip_visible { return; }
        let mut open = self.toolstrip_visible;
        let scale = self.toolstrip_scale.clamp(0.75, 1.25);
        let alpha = (255.0 * self.toolstrip_opacity.clamp(0.65, 1.0)) as u8;
        let frame = egui::Frame::window(&ctx.style())
            .fill(egui::Color32::from_rgba_unmultiplied(20, 30, 49, alpha));
        egui::Window::new("Pc · Companion Tools")
            .id(egui::Id::new("pc_companion_phase3_floating_toolstrip"))
            .default_pos(egui::pos2(84.0, 180.0))
            .resizable(false)
            .collapsible(true)
            .open(&mut open)
            .frame(frame)
            .show(ctx, |ui| {
                let bridge_mode = if self.running.is_none() {
                    "Bridge off"
                } else if self.writes_enabled.load(Ordering::Acquire) {
                    "Approved edits enabled"
                } else {
                    "Read-only bridge"
                };
                ui.label(egui::RichText::new(bridge_mode).color(
                    egui::Color32::from_rgb(124, 217, 237)
                ).size(12.0 * scale));
                ui.label(egui::RichText::new(if has_document {
                    "Document open"
                } else {
                    "Open a document to enable actions"
                }).small());
                if self.toolstrip_vertical {
                    ui.vertical(|ui| self.toolstrip_actions(ui, has_document, scale));
                } else {
                    ui.horizontal_wrapped(|ui| self.toolstrip_actions(ui, has_document, scale));
                }
                if has_document && self.writes_enabled.load(Ordering::Acquire) {
                    ui.checkbox(&mut self.toolstrip_confirmed, "Confirm B&W edits on this document");
                } else {
                    self.toolstrip_confirmed = false;
                }
                ui.label(egui::RichText::new(&self.toolstrip_status).small());
                ui.horizontal(|ui| {
                    let switch = if self.toolstrip_vertical { "Horizontal" } else { "Vertical" };
                    if ui.small_button(switch).clicked() {
                        self.toolstrip_vertical = !self.toolstrip_vertical;
                    }
                    if ui.small_button("Companion settings").clicked() {
                        self.show_window = true;
                    }
                });
            });
        self.toolstrip_visible = open;
    }

    fn toolstrip_actions(&mut self, ui: &mut egui::Ui, has_document: bool, scale: f32) {
        let edits_allowed = self.writes_enabled.load(Ordering::Acquire);
        let size = egui::vec2(86.0 * scale, 34.0 * scale);
        if ui.add_enabled(
            tool_action_allowed(ToolstripAction::Inspect, has_document, edits_allowed),
            egui::Button::new("Inspect").min_size(size),
        ).clicked() {
            self.pending_toolstrip_action = Some(ToolstripAction::Inspect);
        }
        if ui.add_enabled(
            has_document && edits_allowed && self.toolstrip_confirmed,
            egui::Button::new("B&W Pop").min_size(size),
        ).clicked() {
            // Route through the exact owner-tested, on-device Phase 2 macro path.
            self.pending_macro = true;
            self.macro_confirmed = false;
            self.toolstrip_confirmed = false;
            self.toolstrip_status = "Applying two undoable B&W operations…".to_owned();
        }
        if ui.add_enabled(
            tool_action_allowed(ToolstripAction::Undo, has_document, edits_allowed),
            egui::Button::new("Undo").min_size(size),
        ).clicked() {
            self.pending_toolstrip_action = Some(ToolstripAction::Undo);
        }
        if ui.add_enabled(
            tool_action_allowed(ToolstripAction::Redo, has_document, edits_allowed),
            egui::Button::new("Redo").min_size(size),
        ).clicked() {
            self.pending_toolstrip_action = Some(ToolstripAction::Redo);
        }
    }

    pub(crate) fn take_toolstrip_action(&mut self) -> Option<ToolstripAction> {
        self.pending_toolstrip_action.take()
    }

    pub(crate) fn toolstrip_action_finished(&mut self, result: Result<String, String>) {
        self.toolstrip_status = result.unwrap_or_else(|error| format!("Action unavailable: {error}"));
    }

    pub(crate) fn show_dialog(&mut self, ctx: &egui::Context) {
        if !self.show_window { return; }
        let mut open = self.show_window;
        egui::Window::new("PhotoCraft Companion · Android Bridge")
            .id(egui::Id::new("pc_android_companion_bridge"))
            .open(&mut open)
            .resizable(true)
            .collapsible(false)
            .show(ctx, |ui| {
                ui.heading("Companion · Linux Lab / Desktop");
                ui.label("Authenticated PhotoCraft control bridge for compatible Companion plugins and macros.");
                ui.label("This does not install the desktop Companion app or neural models.");
                ui.separator();
                ui.label(&self.status);
                if self.running.is_none() {
                    if ui.button("Enable local Companion bridge").clicked() {
                        self.start(ctx);
                    }
                } else {
                    if ui.button("Disable Companion bridge").clicked() {
                        self.stop();
                    }
                    if self.running.is_some() {
                        ui.label("Local endpoint: 127.0.0.1:18492");
                        ui.label("Session token hidden to prevent accidental screenshot exposure.");
                        if ui.button("Copy pairing token privately").clicked() {
                            self.copy_status = Some(match self.clipboard.copy_private_companion_token(&self.token) {
                                Ok(()) => "Pairing token copied to Android clipboard. Paste privately.".to_owned(),
                                Err(error) => format!("Copy failed: {error}"),
                            });
                        }
                        if let Some(message) = &self.copy_status {
                            ui.label(message);
                        }
                        let mut enabled = self.writes_enabled.load(Ordering::Acquire);
                        if ui.checkbox(&mut enabled, "Allow approved undoable edits from paired clients").changed() {
                            self.writes_enabled.store(enabled, Ordering::Release);
                        }
                        ui.label(egui::RichText::new("Read-only by default. Paired clients cannot save, open files, install plugins, send pixels, or run arbitrary commands.").small());
                    }
                }
                ui.separator();
                ui.strong("Floating Companion toolstrip (Phase 3)");
                ui.checkbox(&mut self.toolstrip_visible, "Show floating toolstrip");
                ui.checkbox(&mut self.toolstrip_vertical, "Vertical toolstrip");
                ui.add(egui::Slider::new(&mut self.toolstrip_scale, 0.75..=1.25).text("Toolstrip size"));
                ui.add(egui::Slider::new(&mut self.toolstrip_opacity, 0.65..=1.0).text("Background opacity"));
                ui.label(egui::RichText::new("Drag the toolstrip title to reposition; use its collapse button to minimize. Settings are session-only.").small());
                ui.separator();
                ui.strong("Compatible no-code Companion macro");
                ui.label("B&W Film Pop: duplicate the active layer, then desaturate the copy.");
                ui.label("These are two separate undoable operations (Undo twice to revert both).");
                ui.checkbox(&mut self.macro_confirmed, "I want to run this macro on the active document");
                if ui.add_enabled(self.macro_confirmed, egui::Button::new("Apply B&W Film Pop")).clicked() {
                    self.pending_macro = true;
                    self.macro_confirmed = false;
                }
                ui.label(&self.macro_status);
                ui.separator();
                ui.label(egui::RichText::new("Disabled by default. Listening binds only to tablet localhost. Never connect over a public network.").small());
                ui.label(egui::RichText::new("Companion desktop GPU inference, plugin store, and .pcpl installation are not ported to Android yet.").small());
            });
        self.show_window = open;
    }
}

impl CompanionBridge {
    pub(crate) fn take_macro_request(&mut self) -> bool {
        std::mem::take(&mut self.pending_macro)
    }

    pub(crate) fn macro_finished(&mut self, result: Result<(), String>) {
        self.macro_status = match result {
            Ok(()) => "B&W Film Pop applied to the duplicate; Undo twice to revert both edits.".into(),
            Err(error) => format!("Macro not fully completed: {error}"),
        };
        self.toolstrip_status = self.macro_status.clone();
    }
}

impl Drop for CompanionBridge {
    fn drop(&mut self) { self.stop(); }
}

fn random_token() -> io::Result<String> {
    let mut bytes = [0u8; 32];
    std::fs::File::open("/dev/urandom")?.read_exact(&mut bytes)?;
    let mut result = String::with_capacity(64);
    for byte in bytes {
        use std::fmt::Write as _;
        let _ = write!(result, "{byte:02x}");
    }
    Ok(result)
}

fn constant_time_equal(left: &str, right: &str) -> bool {
    let a = left.as_bytes();
    let b = right.as_bytes();
    let mut difference = a.len() ^ b.len();
    for (i, &x) in a.iter().enumerate() {
        difference |= usize::from(x ^ b.get(i).copied().unwrap_or(0));
    }
    difference == 0
}

/// Read no more than MAX_REQUEST bytes from an untrusted socket, checking
/// the stop flag even if an authenticated peer stops sending data.
fn read_bounded_line(
    reader: &mut BufReader<TcpStream>,
    stop: &AtomicBool,
    deadline: Instant,
) -> io::Result<Option<Vec<u8>>> {
    let mut line = Vec::new();
    loop {
        if stop.load(Ordering::Acquire) { return Ok(None); }
        if Instant::now() >= deadline { return Err(io::Error::new(io::ErrorKind::TimedOut, "Companion read deadline elapsed")); }
        let available = match reader.fill_buf() {
            Ok(available) => available,
            Err(e) if matches!(e.kind(), io::ErrorKind::TimedOut | io::ErrorKind::WouldBlock) => continue,
            Err(e) => return Err(e),
        };
        if available.is_empty() { return Ok(None); }
        let n = available.iter().position(|&b| b == b'\n')
            .map_or(available.len(), |i| i + 1);
        if line.len() + n > MAX_REQUEST {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Companion request too long"));
        }
        let done = available[n - 1] == b'\n';
        line.extend_from_slice(&available[..n]);
        reader.consume(n);
        if done { return Ok(Some(line)); }
    }
}

fn write_response(stream: &mut TcpStream, value: &Value) -> io::Result<()> {
    let mut bytes = serde_json::to_vec(value).map_err(io::Error::other)?;
    if bytes.len() > MAX_RESPONSE {
        bytes = serde_json::to_vec(&json!({
            "id": value.get("id").cloned().unwrap_or(Value::Null),
            "ok": false,
            "error": "Companion result exceeds the Android bridge size limit"
        })).map_err(io::Error::other)?;
    }
    bytes.push(b'\n');
    stream.write_all(&bytes)?;
    stream.flush()
}

/// Paired clients have no unrestricted engine access.
fn authorize_request(method: &str, params: &Value, can_write: bool) -> Result<(), &'static str> {
    const REFUSED: &str = "Command is not approved for the Android Companion bridge";
    let empty = params.as_object().is_some_and(|fields| fields.is_empty());
    if matches!(method, "companion.ping" | "ui.inspect" | "engine.commands") {
        return if empty { Ok(()) } else { Err(REFUSED) };
    }
    if method != "engine.execute" { return Err(REFUSED); }
    let fields = params.as_object().ok_or(REFUSED)?;
    if fields.len() != 2 || !fields.contains_key("command") || !fields.contains_key("params") {
        return Err(REFUSED);
    }
    let command = fields.get("command").and_then(Value::as_str).ok_or(REFUSED)?;
    if !fields.get("params").is_some_and(|args| args.as_object().is_some_and(|m| m.is_empty())) {
        return Err(REFUSED);
    }
    match command {
        "document.inspect" | "session.inspect" => Ok(()),
        "layer.duplicate" | "image.adjustments.desaturate" |
        "layer.newAdjustmentLayer.blackWhite" | "edit.undo" | "edit.redo" if can_write => Ok(()),
        _ => Err(if can_write { REFUSED } else { "Enable approved edits in the Companion dialog first" }),
    }
}

fn serve_client(
    mut stream: TcpStream,
    token: &str,
    sender: &Sender<ControlRequest>,
    ctx: &egui::Context,
    stop: &AtomicBool,
    writes_enabled: &AtomicBool,
) {
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(3)));
    let Ok(read_stream) = stream.try_clone() else { return };
    let mut reader = BufReader::new(read_stream);
    let mut authenticated = false;
    let auth_deadline = Instant::now() + Duration::from_secs(10);
    while !stop.load(Ordering::Acquire) {
        if !authenticated && Instant::now() > auth_deadline { break; }
        let idle_deadline = if authenticated { Instant::now() + Duration::from_secs(60) } else { auth_deadline };
        let line = match read_bounded_line(&mut reader, stop, idle_deadline) {
            Ok(Some(bytes)) => bytes,
            _ => break,
        };
        let request: Value = match serde_json::from_slice(&line) {
            Ok(value) => value,
            Err(_) => {
                let _ = write_response(&mut stream, &json!({"id":null,"ok":false,"error":"invalid JSON"}));
                break;
            }
        };
        let id = request.get("id").cloned().unwrap_or(Value::Null);
        let method = request.get("method").and_then(Value::as_str).unwrap_or("");
        if !authenticated {
            let supplied = request.pointer("/params/token").and_then(Value::as_str).unwrap_or("");
            if method != "auth" || !constant_time_equal(supplied, token) {
                let _ = write_response(&mut stream, &json!({"id":id,"ok":false,"error":"authentication required"}));
                break;
            }
            authenticated = true;
            if write_response(&mut stream, &json!({"id":id,"ok":true,"result":{"authenticated":true}})).is_err() { break; }
            continue;
        }
        if method == "auth" {
            let _ = write_response(&mut stream, &json!({"id":id,"ok":false,"error":"already authenticated"}));
            continue;
        }
        let params = request.get("params").cloned().unwrap_or_else(|| json!({}));
        let can_write = writes_enabled.load(Ordering::Acquire);
        if let Err(error) = authorize_request(method, &params, can_write) {
            if write_response(&mut stream, &json!({"id":id,"ok":false,"error":error})).is_err() { break; }
            continue;
        }
        if method == "companion.ping" {
            let reply = json!({"id":id,"ok":true,"result":{
                "protocol":2, "app":"PhotoCraft Android", "transport":"127.0.0.1",
                "readOnly":!can_write,
                "supportedRead":["ui.inspect","engine.commands","document.inspect","session.inspect"],
                "supportedEdits":["layer.duplicate","image.adjustments.desaturate",
                    "layer.newAdjustmentLayer.blackWhite","edit.undo","edit.redo"]
            }});
            if write_response(&mut stream, &reply).is_err() { break; }
            continue;
        }
        let (mut command, reply) = ControlRequest::new(method.to_owned(), params);
        let deadline = Instant::now() + REQUEST_TIMEOUT;
        command.deadline = Some(deadline);
        let dispatch = command.dispatch.clone();
        if sender.send(command).is_err() { break; }
        ctx.request_repaint();
        let mut response = reply.recv_timeout(REQUEST_TIMEOUT)
            .unwrap_or_else(|_| json!({"ok":false,"error":dispatch.give_up()}));
        if let Some(map) = response.as_object_mut() {
            map.insert("id".to_owned(), id);
        }
        if write_response(&mut stream, &response).is_err() { break; }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn toolstrip_inspection_is_read_only_and_edits_need_permission() {
        assert!(!tool_action_allowed(ToolstripAction::Inspect, false, false));
        assert!(tool_action_allowed(ToolstripAction::Inspect, true, false));
        assert!(!tool_action_allowed(ToolstripAction::Undo, true, false));
        assert!(!tool_action_allowed(ToolstripAction::Redo, true, false));
        assert!(tool_action_allowed(ToolstripAction::Undo, true, true));
        assert!(tool_action_allowed(ToolstripAction::Redo, true, true));
        assert!(!tool_action_allowed(ToolstripAction::Undo, false, true));
    }

    #[test]
    fn constant_time_token_check_rejects_prefix_and_case_changes() {
        let token = "a".repeat(64);
        assert!(constant_time_equal(&token, &token));
        assert!(!constant_time_equal(&token, &token[..63]));
        assert!(!constant_time_equal(&token, &"A".repeat(64)));
    }
    #[test]
    fn read_only_allows_inspection_but_not_mutations() {
        assert!(authorize_request("engine.execute", &json!({"command":"document.inspect","params":{}}), false).is_ok());
        assert!(authorize_request("engine.execute", &json!({"command":"session.inspect","params":{}}), false).is_ok());
        assert!(authorize_request("ui.inspect", &json!({}), false).is_ok());
        assert!(authorize_request("engine.execute", &json!({"command":"layer.duplicate","params":{}}), false).is_err());
    }
    #[test]
    fn write_gate_allows_only_reviewed_zero_argument_commands() {
        for cmd in ["edit.undo","edit.redo","layer.duplicate",
                    "image.adjustments.desaturate","layer.newAdjustmentLayer.blackWhite"] {
            assert!(authorize_request("engine.execute", &json!({"command":cmd,"params":{}}), true).is_ok());
        }
        for method in ["app.open", "app.save", "ui.pointer", "ui.key", "ui.screenshot",
                       "ui.menu.invoke", "ui.set", "jobs.cancel"] {
            assert!(authorize_request(method, &json!({}), true).is_err(), "{method}");
        }
        assert!(authorize_request("engine.execute", &json!({"command":"file.delete","params":{}}), true).is_err());
        assert!(authorize_request("engine.execute", &json!({"command":"edit.undo","params":{},"wait":false}), true).is_err());
        assert!(authorize_request("engine.execute", &json!({"command":"layer.duplicate","params":{"layer":17}}), true).is_err());
    }
    #[test]
    fn tokens_have_256_bits_of_entropy_and_are_unique() {
        let a = random_token().unwrap();
        let b = random_token().unwrap();
        assert_eq!(a.len(), 64);
        assert!(a.bytes().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(a, b);
    }
}
