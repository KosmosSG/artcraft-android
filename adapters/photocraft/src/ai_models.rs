//! Read-only ComfyUI model inventory, deliberately separate from AI execution.
//! Only two hard-coded GET routes are used. No prompts, image bytes, downloads,
//! model inference, credentials, or document modifications are supported.
use crate::ai_tools::ComfyEndpoint;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::Duration;

const MAX_JSON_BYTES: usize = 128 * 1024;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ModelInventory {
    pub checkpoint_count: usize,
    pub upscale_count: usize,
}

impl ModelInventory {
    pub fn human_summary(&self) -> String {
        format!(
            "Installed files: {} diffusion checkpoint(s), {} upscale model(s). \
             Background-removal nodes/models are not checked. \
             Availability does not mean these models will run on CPU.",
            self.checkpoint_count, self.upscale_count
        )
    }
}

#[derive(Clone, Copy)]
enum ModelFolder { Checkpoints, Upscale }

impl ModelFolder {
    fn path(self) -> &'static str {
        match self {
            Self::Checkpoints => "/models/checkpoints",
            Self::Upscale => "/models/upscale_models",
        }
    }
}

pub(crate) fn inspect_models(endpoint: &ComfyEndpoint) -> Result<ModelInventory, String> {
    // The caller must explicitly opt in and validate the address using
    // ComfyEndpoint::parse before invoking this asynchronous check.
    let checkpoint_count = request_model_count(endpoint, ModelFolder::Checkpoints)?;
    let upscale_count = request_model_count(endpoint, ModelFolder::Upscale)?;
    Ok(ModelInventory { checkpoint_count, upscale_count })
}

fn request_model_count(endpoint: &ComfyEndpoint, folder: ModelFolder) -> Result<usize, String> {
    let addr = endpoint.socket_addr().ok_or("Invalid endpoint address")?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(4))
        .map_err(|e| format!("Cannot connect for model inventory: {e}"))?;
    stream.set_read_timeout(Some(Duration::from_secs(10)))
        .map_err(|e| format!("Cannot set model inventory read timeout: {e}"))?;
    stream.set_write_timeout(Some(Duration::from_secs(4)))
        .map_err(|e| format!("Cannot set model inventory write timeout: {e}"))?;

    let host = if endpoint.host.contains(':') {
        format!("[{}]", endpoint.host)
    } else { endpoint.host.clone() };
    let request = format!(
        "GET {} HTTP/1.1\r\nHost: {host}:{}\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n",
        folder.path(), endpoint.port
    );
    stream.write_all(request.as_bytes())
        .map_err(|e| format!("ComfyUI model inventory request failed: {e}"))?;

    let mut response = Vec::with_capacity(4096);
    let mut buffer = [0u8; 4096];
    loop {
        match stream.read(&mut buffer) {
            Ok(0) => return match decode_http_json(&response, true)? {
                Some(body) => count_json_array_strings(&body),
                None => Err("ComfyUI ended an incomplete inventory response".into())
            },
            Ok(n) => {
                if response.len() + n > MAX_JSON_BYTES + 16 * 1024 {
                    return Err("Model inventory response exceeded safe size limit".into());
                }
                response.extend_from_slice(&buffer[..n]);
                if let Some(body) = decode_http_json(&response, false)? {
                    return count_json_array_strings(&body);
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(e) if matches!(e.kind(), std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut) => {
                return Err("Model inventory timed out. Keep Linux Lab visible as a floating window.".into());
            }
            Err(e) => return Err(format!("ComfyUI model inventory read failed: {e}")),
        }
    }
}

/// Strictly parse 200 application/json with bounded Content-Length or chunked
/// data; do not follow redirects, infer success from TCP connect, or accept
/// truncated replies. If neither framing header exists, require socket EOF.
fn decode_http_json(reply: &[u8], eof: bool) -> Result<Option<Vec<u8>>, String> {
    let Some(split) = reply.windows(4).position(|s| s == b"\r\n\r\n") else {
        return if eof { Err("Incomplete model inventory HTTP headers".into()) } else { Ok(None) };
    };
    if split > 16 * 1024 { return Err("Model inventory HTTP headers too large".into()); }
    let headers = std::str::from_utf8(&reply[..split])
        .map_err(|_| "Invalid model inventory HTTP headers")?;
    let mut lines = headers.split("\r\n");
    let status = lines.next().unwrap_or("");
    if !matches!(status.split_whitespace().nth(1), Some("200"))
        || !(status.starts_with("HTTP/1.1 ") || status.starts_with("HTTP/1.0 "))
    {
        return Err(format!("Model list HTTP error: {}", status.chars().take(80).collect::<String>()));
    }
    let mut content_length = None;
    let mut chunked = false;
    let mut json_type = false;
    for header in lines {
        let (name, value) = header.split_once(':').ok_or("Invalid model inventory header")?;
        let value = value.trim();
        if name.eq_ignore_ascii_case("Content-Type") {
            json_type = value.to_ascii_lowercase().starts_with("application/json");
        } else if name.eq_ignore_ascii_case("Content-Length") {
            if content_length.is_some() { return Err("Duplicate Content-Length".into()); }
            let len = value.parse::<usize>().map_err(|_| "Invalid Content-Length")?;
            if len > MAX_JSON_BYTES { return Err("Too many model entries for this preview".into()); }
            content_length = Some(len);
        } else if name.eq_ignore_ascii_case("Transfer-Encoding") {
            if !value.eq_ignore_ascii_case("chunked") { return Err("Unsupported inventory transfer encoding".into()); }
            chunked = true;
        }
    }
    if !json_type { return Err("ComfyUI model listing was not JSON".into()); }
    if chunked && content_length.is_some() { return Err("Conflicting model inventory framing".into()); }
    let body = &reply[split+4..];
    if chunked {
        // Reuse the bounded standard decoder already reviewed for /system_stats.
        return match crate::ai_tools::decode_chunked_body(body)? {
            Some(bytes) => Ok(Some(bytes)),
            None if eof => Err("Incomplete chunked model inventory".into()),
            None => Ok(None)
        };
    }
    if let Some(n) = content_length {
        return if body.len() >= n { Ok(Some(body[..n].to_vec())) }
            else if eof { Err("Truncated model inventory body".into()) }
            else { Ok(None) };
    }
    if eof {
        if body.len() > MAX_JSON_BYTES { return Err("Inventory too large".into()); }
        return Ok(Some(body.to_vec()));
    }
    Ok(None)
}

/// ComfyUI /models/{folder} returns a JSON string array of installed filenames.
/// Count only complete, correctly escaped JSON strings; don't expose filenames
/// in UI/logs, and don't interpret them as runnable or safe model choices.
fn count_json_array_strings(data: &[u8]) -> Result<usize, String> {
    let text = std::str::from_utf8(data).map_err(|_| "Invalid model-list encoding")?;
    let mut chars = text.chars().peekable();
    fn whitespace(i: &mut std::iter::Peekable<std::str::Chars<'_>>) {
        while i.peek().is_some_and(|c| c.is_ascii_whitespace()) { i.next(); }
    }
    whitespace(&mut chars);
    if chars.next() != Some('[') { return Err("Model list is not a JSON array".into()); }
    whitespace(&mut chars);
    if chars.peek() == Some(&']') {
        chars.next(); whitespace(&mut chars);
        return if chars.next().is_none() { Ok(0) } else { Err("Trailing model-list JSON".into()) };
    }
    let mut count = 0usize;
    loop {
        whitespace(&mut chars);
        if chars.next() != Some('"') { return Err("Model list contains a non-string entry".into()); }
        loop {
            match chars.next() {
                Some('"') => break,
                Some('\\') => match chars.next() {
                    Some('"' | '\\' | '/' | 'b' | 'f' | 'n' | 'r' | 't') => {},
                    Some('u') => for _ in 0..4 {
                        if !chars.next().is_some_and(|c| c.is_ascii_hexdigit()) {
                            return Err("Invalid JSON unicode escape in model name".into());
                        }
                    },
                    _ => return Err("Invalid JSON escape in model name".into()),
                },
                Some(c) if (c as u32) >= 0x20 => {},
                _ => return Err("Invalid JSON string in model list".into()),
            }
        }
        count += 1;
        if count > 4096 { return Err("Model inventory has too many entries".into()); }
        whitespace(&mut chars);
        match chars.next() {
            Some(',') => continue,
            Some(']') => {
                whitespace(&mut chars);
                return if chars.next().is_none() { Ok(count) } else { Err("Trailing model-list JSON".into()) };
            }
            _ => return Err("Malformed JSON model list".into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;
    use std::thread;
    #[test]
    fn counts_only_model_names_without_exposing_them() {
        assert_eq!(count_json_array_strings(br#"[]"#).unwrap(), 0);
        assert_eq!(count_json_array_strings(br#"["first.safetensors", "second\\name.pt", "nonascii-\u4e2d.ckpt"]"#).unwrap(), 3);
        for bad in [r#"{"models":[]}"#, r#"[1]"#, r#"["a",]"#, r#"["unterminated]"#, r#"["a"] trailing"#, r#"["bad\q"]"#] {
            assert!(count_json_array_strings(bad.as_bytes()).is_err(), "{bad}");
        }
        let summary = ModelInventory{ checkpoint_count:0, upscale_count:2 }.human_summary();
        assert!(summary.contains("0 diffusion"));
        assert!(summary.contains("not checked"));
    }
    #[test]
    fn inventory_response_requires_200_json_and_correct_length() {
        let mut response = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 5\r\n\r\n".to_vec();
        response.extend_from_slice(b"[\"a\"]");
        assert_eq!(decode_http_json(&response, false).unwrap(), Some(b"[\"a\"]".to_vec()));
        assert_eq!(decode_http_json(&response[..response.len()-1], false).unwrap(), None);
        assert!(decode_http_json(&response[..response.len()-1], true).is_err());
        assert!(decode_http_json(b"HTTP/1.1 302 Found\r\nLocation: /redirect\r\n\r\n", true).is_err());
        assert!(decode_http_json(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n[]", true).is_err());
    }
    #[test]
    fn fetches_only_two_read_only_model_routes() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = thread::spawn(move || {
            for expected in ["/models/checkpoints", "/models/upscale_models"] {
                let (mut conn, _) = listener.accept().unwrap();
                conn.set_read_timeout(Some(Duration::from_secs(3))).unwrap();
                let mut request = [0u8; 2048];
                let size = conn.read(&mut request).unwrap();
                let req = std::str::from_utf8(&request[..size]).unwrap();
                assert!(req.starts_with(&format!("GET {expected} HTTP/1.1\r\n")));
                assert!(!req.contains("/prompt"));
                let body = if expected == "/models/checkpoints" { b"[]".as_slice() } else { b"[\"upscale.pth\"]".as_slice() };
                let head = format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: keep-alive\r\n\r\n", body.len());
                conn.write_all(head.as_bytes()).unwrap();
                conn.write_all(body).unwrap();
                // Drop the socket only after sending; client must not rely on EOF.
            }
        });
        let url = format!("http://127.0.0.1:{port}");
        let endpoint = ComfyEndpoint::parse(&url, false).unwrap();
        let result = inspect_models(&endpoint).unwrap();
        server.join().unwrap();
        assert_eq!(result, ModelInventory{checkpoint_count:0,upscale_count:1});
    }
}
