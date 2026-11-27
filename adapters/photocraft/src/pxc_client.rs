//! Native Android-side client for the useful PxC/ComfyUI transport layer.
//!
//! This intentionally does NOT embed PxC's Python desktop application. It speaks
//! the small ComfyUI HTTP API directly so PhotoCraft can remain an Android client
//! while inference stays on the user's Linux Lab / PC GPU.
//!
//! The module is UI-agnostic: callers provide a validated private-LAN endpoint,
//! a PNG, and an API-format workflow. Results are returned as PNG bytes. Document
//! insertion remains on PhotoCraft's UI thread and must use the existing
//! ai_background_editor revision gate.

use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::{Duration, Instant};

use crate::ai_tools::ComfyEndpoint;

const CONNECT_TIMEOUT: Duration = Duration::from_secs(4);
const IO_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_RESPONSE: usize = 32 * 1024 * 1024;
const MAX_PNG: usize = 24 * 1024 * 1024;
const MAX_POLL: Duration = Duration::from_secs(120);

#[derive(Debug)]
pub enum PxcError {
    Network(String),
    Http(String),
    Json(String),
    Protocol(String),
    Limit(String),
}

impl std::fmt::Display for PxcError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Network(s) | Self::Http(s) | Self::Json(s) |
            Self::Protocol(s) | Self::Limit(s) => f.write_str(s),
        }
    }
}

impl std::error::Error for PxcError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ComfyResult {
    pub prompt_id: String,
    pub image: Vec<u8>,
}

pub struct PxcClient {
    endpoint: ComfyEndpoint,
}

impl PxcClient {
    pub fn new(endpoint: ComfyEndpoint) -> Self {
        Self { endpoint }
    }

    pub fn endpoint(&self) -> &ComfyEndpoint {
        &self.endpoint
    }

    /// Upload one user-approved PNG. The response name is returned exactly as
    /// ComfyUI supplied it; callers must not use it as a filesystem path.
    pub fn upload_png(&self, png: &[u8], filename: &str) -> Result<String, PxcError> {
        if png.is_empty() || png.len() > MAX_PNG {
            return Err(PxcError::Limit("Input PNG exceeds the 24 MiB AI transfer limit".into()));
        }
        if filename.is_empty() || filename.len() > 128 ||
            filename.contains(&['/', '\\', '\r', '\n', '\0'][..]) {
            return Err(PxcError::Protocol("Invalid ComfyUI upload filename".into()));
        }

        let boundary = format!("---------------------------pcxandroid{:016x}", 1u64);
        let mut body = Vec::with_capacity(png.len() + 512);
        append_field(&mut body, &boundary, "overwrite", "true");
        append_field(&mut body, &boundary, "type", "input");
        append_field(&mut body, &boundary, "subfolder", "pcxandroid");
        body.extend_from_slice(format!(
            "--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\nContent-Type: image/png\r\n\r\n"
        ).as_bytes());
        body.extend_from_slice(png);
        body.extend_from_slice(format!("\r\n--{boundary}--\r\n").as_bytes());

        let response = self.request(
            "POST",
            "/upload/image",
            &body,
            &[("Content-Type", format!("multipart/form-data; boundary={boundary}"))],
        )?;
        let value: serde_json::Value = serde_json::from_slice(&response)
            .map_err(|e| PxcError::Json(format!("ComfyUI upload returned invalid JSON: {e}")))?;
        let name = value.get("name").and_then(|v| v.as_str())
            .ok_or_else(|| PxcError::Protocol("ComfyUI upload response has no image name".into()))?;
        let subfolder = value.get("subfolder").and_then(|v| v.as_str()).unwrap_or("");
        if name.len() > 512 || subfolder.len() > 512 {
            return Err(PxcError::Protocol("ComfyUI returned an unsafe image reference".into()));
        }
        Ok(if subfolder.is_empty() { name.to_owned() } else { format!("{subfolder}/{name}") })
    }

    /// Queue a ComfyUI API-format workflow. The workflow must already have
    /// user-approved model/workflow parameters substituted by the caller.
    pub fn queue_workflow(&self, workflow: &serde_json::Value) -> Result<String, PxcError> {
        if !workflow.is_object() || workflow.as_object().map_or(true, |o| o.len() > 500) {
            return Err(PxcError::Protocol("Workflow must be a bounded API-format JSON object".into()));
        }
        let payload = serde_json::json!({
            "prompt": workflow,
            "client_id": "photocraft-android"
        });
        let bytes = serde_json::to_vec(&payload)
            .map_err(|e| PxcError::Json(format!("Could not encode ComfyUI workflow: {e}")))?;
        if bytes.len() > 2 * 1024 * 1024 {
            return Err(PxcError::Limit("Workflow exceeds the 2 MiB safety limit".into()));
        }
        let response = self.request(
            "POST",
            "/prompt",
            &bytes,
            &[("Content-Type", "application/json".into())],
        )?;
        let value: serde_json::Value = serde_json::from_slice(&response)
            .map_err(|e| PxcError::Json(format!("ComfyUI queue response was invalid JSON: {e}")))?;
        value.get("prompt_id").and_then(|v| v.as_str())
            .filter(|id| !id.is_empty() && id.len() <= 128)
            .map(str::to_owned)
            .ok_or_else(|| PxcError::Protocol("ComfyUI did not return a prompt id".into()))
    }

    /// Poll history until the queued job contains a completed image. Only the
    /// first returned image is consumed by this phase; additional variants are
    /// deliberately left for a later batch/variant implementation.
    pub fn wait_for_first_image(&self, prompt_id: &str) -> Result<Vec<u8>, PxcError> {
        if prompt_id.is_empty() || prompt_id.len() > 128 {
            return Err(PxcError::Protocol("Invalid ComfyUI prompt id".into()));
        }
        let started = Instant::now();
        while started.elapsed() < MAX_POLL {
            let path = format!("/history/{}", encode_path_segment(prompt_id));
            let response = self.request("GET", &path, &[], &[])?;
            let value: serde_json::Value = serde_json::from_slice(&response)
                .map_err(|e| PxcError::Json(format!("ComfyUI history returned invalid JSON: {e}")))?;
            if let Some(entry) = value.get(prompt_id) {
                if let Some(error) = find_execution_error(entry) {
                    return Err(PxcError::Protocol(format!("ComfyUI job failed: {error}")));
                }
                if let Some(image_ref) = first_output_image(entry) {
                    let bytes = self.download_image(&image_ref)?;
                    if bytes.len() > MAX_PNG {
                        return Err(PxcError::Limit("Generated PNG exceeds the 24 MiB result limit".into()));
                    }
                    if !bytes.starts_with(b"\\x89PNG\\r\\n\\x1a\\n") {
                        return Err(PxcError::Protocol("ComfyUI returned a non-PNG image".into()));
                    }
                    return Ok(bytes);
                }
            }
            std::thread::sleep(Duration::from_millis(800));
        }
        Err(PxcError::Protocol("ComfyUI generation timed out after 120 seconds".into()))
    }

    pub fn generate_text_to_image(
        &self,
        checkpoint: &str,
        prompt: &str,
        seed: u64,
        width: u32,
        height: u32,
    ) -> Result<ComfyResult, PxcError> {
        validate_text(prompt)?;
        if width == 0 || height == 0 || u64::from(width) * u64::from(height) > 8_000_000 {
            return Err(PxcError::Limit("Text-to-image canvas exceeds 8 million pixels".into()));
        }
        if checkpoint.is_empty() || checkpoint.len() > 512 || checkpoint.contains(&['\r','\n'][..]) {
            return Err(PxcError::Protocol("Invalid checkpoint name".into()));
        }
        let workflow = simple_txt2img_workflow(checkpoint, prompt, seed, width, height);
        let prompt_id = self.queue_workflow(&workflow)?;
        let image = self.wait_for_first_image(&prompt_id)?;
        Ok(ComfyResult { prompt_id, image })
    }

    fn download_image(&self, reference: &ImageRef) -> Result<Vec<u8>, PxcError> {
        let query = format!(
            "filename={}&subfolder={}&type={}",
            percent_encode(&reference.filename),
            percent_encode(&reference.subfolder),
            percent_encode(&reference.kind),
        );
        self.request("GET", &format!("/view?{query}"), &[], &[])
    }

    fn request(
        &self,
        method: &str,
        path: &str,
        body: &[u8],
        extra_headers: &[(&str, String)],
    ) -> Result<Vec<u8>, PxcError> {
        if !path.starts_with('/') || path.contains("..") {
            return Err(PxcError::Protocol("Unsafe ComfyUI request path".into()));
        }
        let addr = self.endpoint.socket_addr()
            .ok_or_else(|| PxcError::Protocol("Invalid ComfyUI endpoint".into()))?;
        let mut stream = TcpStream::connect_timeout(&addr, CONNECT_TIMEOUT)
            .map_err(|e| PxcError::Network(format!("Unable to reach ComfyUI: {e}")))?;
        stream.set_read_timeout(Some(IO_TIMEOUT)).map_err(|e| PxcError::Network(e.to_string()))?;
        stream.set_write_timeout(Some(IO_TIMEOUT)).map_err(|e| PxcError::Network(e.to_string()))?;

        let host = if self.endpoint.host.contains(':') {
            format!("[{}]", self.endpoint.host)
        } else { self.endpoint.host.clone() };
        let mut headers = format!(
            "{method} {path} HTTP/1.1\r\nHost: {host}:{}\r\nConnection: close\r\nAccept: application/json, image/png\r\nContent-Length: {}\r\n",
            self.endpoint.port, body.len()
        );
        for (name, value) in extra_headers {
            headers.push_str(name);
            headers.push_str(": ");
            headers.push_str(value);
            headers.push_str("\r\n");
        }
        headers.push_str("\r\n");
        stream.write_all(headers.as_bytes()).map_err(|e| PxcError::Network(e.to_string()))?;
        if !body.is_empty() {
            stream.write_all(body).map_err(|e| PxcError::Network(e.to_string()))?;
        }

        let mut response = Vec::with_capacity(16 * 1024);
        let mut buffer = [0u8; 8192];
        loop {
            match stream.read(&mut buffer) {
                Ok(0) => break,
                Ok(n) => {
                    if response.len() + n > MAX_RESPONSE {
                        return Err(PxcError::Limit("ComfyUI response exceeds the 32 MiB safety limit".into()));
                    }
                    response.extend_from_slice(&buffer[..n]);
                }
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(e) => return Err(PxcError::Network(format!("ComfyUI response read failed: {e}"))),
            }
        }
        split_http_response(&response)
    }
}

#[derive(Debug)]
struct ImageRef { filename: String, subfolder: String, kind: String }

fn first_output_image(history: &serde_json::Value) -> Option<ImageRef> {
    let outputs = history.get("outputs")?.as_object()?;
    for output in outputs.values() {
        let images = output.get("images")?.as_array()?;
        for image in images {
            let filename = image.get("filename")?.as_str()?.to_owned();
            let subfolder = image.get("subfolder").and_then(|v| v.as_str()).unwrap_or("").to_owned();
            let kind = image.get("type").and_then(|v| v.as_str()).unwrap_or("output").to_owned();
            return Some(ImageRef { filename, subfolder, kind });
        }
    }
    None
}

fn find_execution_error(history: &serde_json::Value) -> Option<String> {
    history.get("status")?.get("status_str").and_then(|v| v.as_str())
        .filter(|s| *s == "error" || *s == "failed")
        .map(str::to_owned)
}

fn simple_txt2img_workflow(checkpoint: &str, prompt: &str, seed: u64, width: u32, height: u32) -> serde_json::Value {
    serde_json::json!({
        "4": {"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":checkpoint}},
        "6": {"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["4",1]}},
        "7": {"class_type":"CLIPTextEncode","inputs":{"text":"","clip":["4",1]}},
        "5": {"class_type":"EmptyLatentImage","inputs":{"width":width,"height":height,"batch_size":1}},
        "3": {"class_type":"KSampler","inputs":{"seed":seed,"steps":20,"cfg":7.0,"sampler_name":"euler","scheduler":"normal","denoise":1.0,"model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":["5",0]}},
        "8": {"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["4",2]}},
        "9": {"class_type":"SaveImage","inputs":{"filename_prefix":"PhotoCraft_PxC","images":["8",0]}}
    })
}

fn validate_text(text: &str) -> Result<(), PxcError> {
    let trimmed = text.trim();
    if trimmed.is_empty() { return Err(PxcError::Protocol("Enter a prompt first".into())); }
    if trimmed.len() > 4096 { return Err(PxcError::Limit("Prompt exceeds the 4 KiB safety limit".into())); }
    Ok(())
}

fn append_field(body: &mut Vec<u8>, boundary: &str, name: &str, value: &str) {
    body.extend_from_slice(format!(
        "--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
    ).as_bytes());
}

fn encode_path_segment(value: &str) -> String {
    percent_encode(value)
}

fn percent_encode(value: &str) -> String {
    let mut out = String::new();
    for byte in value.bytes() {
        if byte.is_ascii_alphanumeric() || matches!(byte, b'-'|b'_'|b'.'|b'~') {
            out.push(byte as char);
        } else {
            out.push_str(&format!("%{byte:02X}"));
        }
    }
    out
}

fn split_http_response(raw: &[u8]) -> Result<Vec<u8>, PxcError> {
    let split = raw.windows(4).position(|w| w == b"\\r\\n\\r\\n")
        .ok_or_else(|| PxcError::Http("ComfyUI returned incomplete HTTP headers".into()))?;
    let header = std::str::from_utf8(&raw[..split])
        .map_err(|_| PxcError::Http("ComfyUI returned invalid HTTP headers".into()))?;
    let status = header.lines().next().unwrap_or("");
    let code = status.split_whitespace().nth(1).unwrap_or("");
    if code != "200" {
        return Err(PxcError::Http(format!("ComfyUI HTTP {code}")));
    }
    let mut content_length = None;
    for line in header.lines().skip(1) {
        if let Some((name, value)) = line.split_once(':') {
            if name.eq_ignore_ascii_case("Content-Length") {
                content_length = value.trim().parse::<usize>().ok();
            }
        }
    }
    let body = &raw[split + 4..];
    if let Some(n) = content_length {
        if n > MAX_RESPONSE { return Err(PxcError::Limit("ComfyUI response is too large".into())); }
        if body.len() < n { return Err(PxcError::Http("ComfyUI response body was truncated".into())); }
        Ok(body[..n].to_vec())
    } else {
        Ok(body.to_vec())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn workflow_has_expected_nodes() {
        let w = simple_txt2img_workflow("model.safetensors", "a cat", 7, 512, 512);
        assert_eq!(w["4"]["class_type"], "CheckpointLoaderSimple");
        assert_eq!(w["9"]["class_type"], "SaveImage");
        assert_eq!(w["5"]["inputs"]["width"], 512);
    }

    #[test]
    fn prompt_is_bounded() {
        assert!(validate_text("").is_err());
        assert!(validate_text(&"x".repeat(4097)).is_err());
        assert!(validate_text("a safe prompt").is_ok());
    }

    #[test]
    fn path_encoding_is_safe() {
        assert_eq!(percent_encode("a/b c.png"), "a%2Fb%20c.png");
    }
}
