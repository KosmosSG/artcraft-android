//! Opt-in, loopback-only PhotoCraft Companion control transport for Android.
//! Based on the published PhotoCraft v0.23.1 control protocol and the
//! kobaltgit/photocraft-companion JSON-lines client format (MIT).
//! No external address, automatic startup, model installation or silent edits.

use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc::Sender, Arc};
use std::time::{Duration, Instant};

use photocraft_ui_egui::ControlRequest;
use serde_json::{json, Value};

const PORT: u16 = 18492;
const MAX_REQUEST: usize = 64 * 1024;
const MAX_RESPONSE: usize = 2 * 1024 * 1024;
const REQUEST_TIMEOUT: Duration = Duration::from_secs(25);

pub(crate) struct CompanionBridge {
    sender: Sender<ControlRequest>,
    running: Option<Arc<AtomicBool>>,
    token: String,
    status: String,
    pub(crate) show_window: bool,
}

impl CompanionBridge {
    pub(crate) fn new(sender: Sender<ControlRequest>) -> Self {
        Self {
            sender,
            running: None,
            token: String::new(),
            status: "Off. No local control port is listening.".to_owned(),
            show_window: false,
        }
    }

    fn start(&mut self, ctx: &egui::Context) {
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
        match std::thread::Builder::new()
            .name("photocraft-companion-loopback".into())
            .spawn(move || {
                while !worker_stop.load(Ordering::Acquire) {
                    match listener.accept() {
                        Ok((stream, peer)) if peer.ip().is_loopback() => {
                            serve_client(stream, &worker_token, &sender, &worker_ctx, &worker_stop);
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
        if let Some(stop) = self.running.take() {
            stop.store(true, Ordering::Release);
        }
        self.token.clear();
        self.status = "Off. No new Companion commands will be accepted.".to_owned();
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
                        ui.label("One-session control token (keep private):");
                        let mut visible_token = self.token.clone();
                        ui.add(egui::TextEdit::singleline(&mut visible_token)
                            .desired_width(420.0).interactive(false));
                        if ui.button("Copy pairing token").clicked() {
                            ctx.copy_text(self.token.clone());
                        }
                        ui.small("Only connect trusted local software. A paired Companion can modify the open document.");
                    }
                }
                ui.separator();
                ui.small("Disabled by default. Listening binds only to tablet localhost. Never connect over a public network.");
                ui.small("Companion desktop GPU inference, plugin store, and .pcpl installation are not ported to Android yet.");
            });
        self.show_window = open;
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
) -> io::Result<Option<Vec<u8>>> {
    let mut line = Vec::new();
    loop {
        if stop.load(Ordering::Acquire) { return Ok(None); }
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
    let mut bytes = serde_json::to_vec(value)?;
    if bytes.len() > MAX_RESPONSE {
        bytes = serde_json::to_vec(&json!({
            "id": value.get("id").cloned().unwrap_or(Value::Null),
            "ok": false,
            "error": "Companion result exceeds the Android bridge size limit"
        }))?;
    }
    bytes.push(b'\n');
    stream.write_all(&bytes)?;
    stream.flush()
}

fn serve_client(
    mut stream: TcpStream,
    token: &str,
    sender: &Sender<ControlRequest>,
    ctx: &egui::Context,
    stop: &AtomicBool,
) {
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(3)));
    let Ok(read_stream) = stream.try_clone() else { return };
    let mut reader = BufReader::new(read_stream);
    let mut authenticated = false;
    let auth_deadline = Instant::now() + Duration::from_secs(10);
    while !stop.load(Ordering::Acquire) {
        if !authenticated && Instant::now() > auth_deadline { break; }
        let line = match read_bounded_line(&mut reader, stop) {
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
    fn constant_time_token_check_rejects_prefix_and_case_changes() {
        let token = "a".repeat(64);
        assert!(constant_time_equal(&token, &token));
        assert!(!constant_time_equal(&token, &token[..63]));
        assert!(!constant_time_equal(&token, &"A".repeat(64)));
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
