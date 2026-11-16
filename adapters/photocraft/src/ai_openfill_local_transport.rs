//! Consent-gated, tablet-loopback transport to the opt-in Linux Lab OpenFill
//! companion. No raw ComfyUI endpoint access and no startup requests.
//! Never persist bearer tokens, prompts or image data. Worker thread only.
use crate::ai_openfill_operations::{JobDraft, Operation};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

const MAX_BODY: usize = 105 * 1024 * 1024;
const MAX_RESPONSE: usize = 96 * 1024 * 1024;
pub const PORT: u16 = 18794;

fn running(cancel: &AtomicBool) -> Result<(), String> {
    if cancel.load(Ordering::Acquire) {
        Err("OpenFill generation cancelled".into())
    } else {
        Ok(())
    }
}

fn operation_name(operation: Operation) -> &'static str {
    match operation {
        Operation::Fill => "fill",
        Operation::RemoveObject => "remove",
        Operation::GenerativeExpand => "expand",
        Operation::Create => "create",
    }
}

/// Submit one owner-confirmed request to the same tablet's Linux Lab only.
/// The Linux Lab service must independently authenticate, validate and choose
/// approved OpenFill nodes/models; its response is untrusted until fully
/// decoded with PhotoCraft's own image importer.
pub fn generate(
    draft: &JobDraft,
    source_rgba: &[u8],
    mask_alpha: &[u8],
    token: &str,
    consent: bool,
    cancel: &AtomicBool,
) -> Result<Vec<u8>, String> {
    draft.validate_intent(consent).map_err(str::to_owned)?;
    if token.len() < 32 || token.len() > 128 ||
        !token.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_') {
        return Err("Use the temporary 32+ character Linux Lab OpenFill session token".into());
    }
    let (sw, sh) = draft.input.map_or((0u32, 0u32), |size| (size.width, size.height));
    let expected = draft.input.map(|s| s.rgba_len()).transpose()
        .map_err(str::to_owned)?.unwrap_or(0);
    if source_rgba.len() != expected {
        return Err("Source RGBA buffer does not match the active document".into());
    }
    let mask_len = if matches!(draft.operation, Operation::Fill | Operation::RemoveObject) {
        sw as usize * sh as usize
    } else { 0 };
    if mask_alpha.len() != mask_len || (mask_len > 0 && !mask_alpha.iter().any(|&v| v > 0)) {
        return Err("OpenFill requires an exact real selection mask".into());
    }
    let meta = serde_json::json!({
        "operation": operation_name(draft.operation),
        "width": draft.output.width, "height": draft.output.height,
        "source_width": sw, "source_height": sh,
        "offset_x": draft.offset_x, "offset_y": draft.offset_y,
        "prompt": draft.prompt, "model": draft.model_id,
    });
    let bytes = serde_json::to_vec(&meta).map_err(|_| "Could not encode OpenFill metadata")?;
    if bytes.is_empty() || bytes.len() > 8192 {
        return Err("OpenFill request metadata exceeds the safety limit".into());
    }
    let size = 4usize.checked_add(bytes.len())
        .and_then(|x| x.checked_add(source_rgba.len()))
        .and_then(|x| x.checked_add(mask_alpha.len()))
        .ok_or("OpenFill request size overflow")?;
    if size > MAX_BODY {
        return Err("OpenFill image request exceeds the local transfer limit".into());
    }
    running(cancel)?;
    let addr = SocketAddr::from(([127, 0, 0, 1], PORT));
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(4))
        .map_err(|_| "Start the PhotoCraft OpenFill server in Linux Lab (port 18794)")?;
    stream.set_read_timeout(Some(Duration::from_millis(500)))
        .map_err(|_| "Cannot configure OpenFill socket read timeout")?;
    stream.set_write_timeout(Some(Duration::from_secs(3)))
        .map_err(|_| "Cannot configure OpenFill socket write timeout")?;
    let header = format!(
        "POST /v1/openfill HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nAuthorization: Bearer {token}\r\nX-PhotoCraft-Image-Consent: yes\r\nContent-Type: application/octet-stream\r\nContent-Length: {size}\r\nConnection: close\r\n\r\n"
    );
    running(cancel)?;
    stream.write_all(header.as_bytes()).map_err(|_| "Cannot send OpenFill request headers")?;
    stream.write_all(&(bytes.len() as u32).to_be_bytes())
        .map_err(|_| "Cannot send OpenFill metadata length")?;
    stream.write_all(&bytes).map_err(|_| "Cannot send OpenFill request metadata")?;
    let upload_deadline = Instant::now() + Duration::from_secs(50);
    for chunk in source_rgba.chunks(64 * 1024).chain(mask_alpha.chunks(64 * 1024)) {
        running(cancel)?;
        if Instant::now() > upload_deadline {
            return Err("OpenFill local image upload timed out".into());
        }
        stream.write_all(chunk).map_err(|_| "Cannot send OpenFill source or selection data")?;
    }
    let deadline = Instant::now() + Duration::from_secs(930);
    let mut reply = Vec::new();
    let mut buffer = [0u8; 8192];
    loop {
        running(cancel)?;
        if Instant::now() > deadline {
            return Err("Linux Lab OpenFill inference timed out".into());
        }
        match stream.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => {
                if reply.len().saturating_add(n) > MAX_RESPONSE + 16 * 1024 {
                    return Err("OpenFill result exceeds maximum image size".into());
                }
                reply.extend_from_slice(&buffer[..n]);
            }
            Err(error) if matches!(error.kind(), std::io::ErrorKind::Interrupted |
                std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock) => continue,
            Err(_) => return Err("OpenFill local server connection interrupted".into()),
        }
    }
    running(cancel)?;
    // Strict PNG-header check only; the caller must fully decode, validate
    // canvas dimensions and source revision before committing ANY pixel.
    crate::ai_u2netp_transport::parse_response(&reply).map_err(|_| {
        "OpenFill Linux Lab returned no valid RGBA PNG (check installed model/ComfyUI)".into()
    })
}
