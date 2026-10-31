//! Consent-gated Android-to-Linux-Lab U2NetP transport for PR #93 AI Preview.
//! Only tablet-local loopback is permitted. Never persist a session token.
//! Cancellation closes the client connection; the remote CPU subprocess may
//! finish work already started unless the Linux Lab server interrupts it.
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

pub const MAX_INPUT: usize = 24 * 1024 * 1024;
pub const MAX_OUTPUT: usize = 32 * 1024 * 1024;

pub fn remove_background(
    endpoint: SocketAddr, token: &str, png: &[u8], consent: bool,
) -> Result<Vec<u8>, String> {
    let cancellation = AtomicBool::new(false);
    remove_background_with_cancel(endpoint, token, png, consent, &cancellation)
}

fn ensure_active(cancel: &AtomicBool) -> Result<(), String> {
    if cancel.load(Ordering::Acquire) {
        Err("Background removal cancelled".into())
    } else {
        Ok(())
    }
}

/// Preview-only transport. The cancellation flag is shared with the UI so
/// closing the dialog or tapping Cancel drops the TCP connection promptly.
pub fn remove_background_with_cancel(
    endpoint: SocketAddr, token: &str, png: &[u8], consent: bool,
    cancel: &AtomicBool,
) -> Result<Vec<u8>, String> {
    if !consent { return Err("Explicit per-image consent required".into()); }
    if !endpoint.ip().is_loopback() {
        return Err("Only tablet-local loopback U2NetP is allowed".into());
    }
    if token.len() < 32 || token.len() > 128 ||
        !token.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_') {
        return Err("Invalid session token".into());
    }
    if png.is_empty() || png.len() > MAX_INPUT ||
        !png.starts_with(b"\x89PNG\r\n\x1a\n") {
        return Err("Input must be a bounded PNG".into());
    }
    ensure_active(cancel)?;
    let mut stream = TcpStream::connect_timeout(&endpoint, Duration::from_secs(4))
        .map_err(|_| "Local U2NetP server unavailable")?;
    // Subsecond socket waits permit cancellation even when the server is busy.
    // A separate absolute deadline prevents a slow peer from keeping a
    // connection alive indefinitely by sending one byte every second.
    stream.set_read_timeout(Some(Duration::from_millis(500)))
        .map_err(|e| e.to_string())?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))
        .map_err(|e| e.to_string())?;
    let request = format!(
        "POST /v1/remove-background HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nAuthorization: Bearer {}\r\nX-PhotoCraft-Image-Consent: yes\r\nContent-Type: image/png\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        endpoint.port(), token, png.len()
    );
    ensure_active(cancel)?;
    stream.write_all(request.as_bytes())
        .map_err(|_| "Failed to send request headers")?;
    let upload_deadline = Instant::now() + Duration::from_secs(20);
    for chunk in png.chunks(64 * 1024) {
        ensure_active(cancel)?;
        if Instant::now() >= upload_deadline {
            return Err("Local U2NetP image upload timed out".into());
        }
        stream.write_all(chunk).map_err(|_| "Failed to send PNG")?;
    }
    let read_deadline = Instant::now() + Duration::from_secs(190);
    let mut response = Vec::new();
    let mut buf = [0u8; 8192];
    loop {
        ensure_active(cancel)?;
        if Instant::now() >= read_deadline {
            return Err("Local U2NetP response timed out".into());
        }
        let n = match stream.read(&mut buf) {
            Ok(n) => n,
            Err(error) if matches!(error.kind(),
                std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock
                | std::io::ErrorKind::Interrupted) => continue,
            Err(_) => return Err("Local U2NetP connection closed unexpectedly".into()),
        };
        if n == 0 { break; }
        if response.len().saturating_add(n) > MAX_OUTPUT + 16 * 1024 {
            return Err("Local U2NetP response exceeded limit".into());
        }
        response.extend_from_slice(&buf[..n]);
    }
    ensure_active(cancel)?;
    parse_response(&response)
}

pub fn parse_response(response: &[u8]) -> Result<Vec<u8>, String> {
    let split = response.windows(4).position(|w| w == b"\r\n\r\n")
        .ok_or("Incomplete HTTP response")?;
    if split > 16 * 1024 { return Err("HTTP headers too large".into()); }
    let header = std::str::from_utf8(&response[..split]).map_err(|_| "Invalid HTTP headers")?;
    let mut lines = header.split("\r\n");
    // Python BaseHTTPRequestHandler uses HTTP/1.0 by default. Only an exact
    // 200 is accepted; expected HTTP errors get useful non-sensitive feedback.
    match lines.next() {
        Some("HTTP/1.0 200 OK" | "HTTP/1.1 200 OK") => {}
        Some("HTTP/1.0 401 Unauthorized" | "HTTP/1.1 401 Unauthorized") =>
            return Err("U2NetP token rejected. Copy the latest token from Linux Lab.".into()),
        Some("HTTP/1.0 403 Forbidden" | "HTTP/1.1 403 Forbidden") =>
            return Err("U2NetP server refused per-image consent.".into()),
        Some("HTTP/1.0 429 Too Many Requests" | "HTTP/1.1 429 Too Many Requests") =>
            return Err("U2NetP CPU server is busy. Retry after the previous request ends.".into()),
        Some("HTTP/1.0 504 Gateway Timeout" | "HTTP/1.1 504 Gateway Timeout") =>
            return Err("Local U2NetP CPU inference timed out.".into()),
        _ => return Err("Local U2NetP server did not return success".into()),
    }
    let mut length = None;
    let mut png_type = false;
    for line in lines {
        let (name, value) = line.split_once(':').ok_or("Malformed HTTP header")?;
        let value = value.trim();
        if name.eq_ignore_ascii_case("Content-Length") {
            if length.is_some() { return Err("Duplicate Content-Length".into()); }
            length = Some(value.parse::<usize>().map_err(|_| "Invalid Content-Length")?);
        }
        if name.eq_ignore_ascii_case("Content-Type") {
            png_type = value.eq_ignore_ascii_case("image/png");
        }
        if name.eq_ignore_ascii_case("Transfer-Encoding") {
            return Err("Chunked response not supported".into());
        }
    }
    let expected = length.ok_or("Missing Content-Length")?;
    if !png_type || expected == 0 || expected > MAX_OUTPUT {
        return Err("Invalid PNG response metadata".into());
    }
    let body = &response[split + 4..];
    if body.len() != expected || !body.starts_with(b"\x89PNG\r\n\x1a\n") {
        return Err("Truncated or invalid PNG response".into());
    }
    // Header preflight rejects non-alpha output before returning it to the caller.
    // Caller MUST additionally fully decode PNG and check expected dimensions,
    // pixels, and the active document revision before any layer insertion.
    if body.len() < 33 || &body[12..16] != b"IHDR" ||
        u32::from_be_bytes(body[8..12].try_into().unwrap()) != 13 ||
        body[24] != 8 || !matches!(body[25], 4 | 6) {
        return Err("U2NetP output must be 8-bit PNG with alpha".into());
    }
    let width = u32::from_be_bytes(body[16..20].try_into().unwrap());
    let height = u32::from_be_bytes(body[20..24].try_into().unwrap());
    if width == 0 || height == 0 || u64::from(width) * u64::from(height) > 4_000_000 {
        return Err("U2NetP output dimensions exceed preview safety limit".into());
    }
    Ok(body.to_vec())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn sample() -> Vec<u8> {
        let mut png = vec![0u8; 33];
        png[..8].copy_from_slice(b"\x89PNG\r\n\x1a\n");
        png[8..12].copy_from_slice(&13u32.to_be_bytes());
        png[12..16].copy_from_slice(b"IHDR");
        png[16..20].copy_from_slice(&16u32.to_be_bytes());
        png[20..24].copy_from_slice(&16u32.to_be_bytes());
        png[24] = 8;
        png[25] = 6;
        let mut result = format!("HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", png.len()).into_bytes();
        result.extend_from_slice(&png);
        result
    }
    #[test] fn accepts_bounded_png_framing() {
        assert_eq!(parse_response(&sample()).unwrap().len(), 33);
    }
    #[test] fn accepts_python_http10_response() {
        let mut v = sample();
        // Change status line to HTTP/1.0 without corrupting binary PNG bytes.
        v[7] = b'0';
        assert_eq!(parse_response(&v).unwrap().len(), 33);
    }
    #[test] fn rejects_truncation() {
        let mut v=sample();v.pop();assert!(parse_response(&v).is_err());
    }
    #[test] fn rejects_non_png_content_type() {
        let v=sample();let s=String::from_utf8_lossy(&v).replace("image/png","text/html");
        assert!(parse_response(s.as_bytes()).is_err());
    }
    #[test] fn rejects_missing_length() {
        let v=sample();let s=String::from_utf8_lossy(&v).replace("Content-Length: 33\r\n","");
        assert!(parse_response(s.as_bytes()).is_err());
    }
    #[test]
    fn rejects_non_alpha_output() {
        let mut v = sample();
        let start = v.windows(4).position(|w| w == b"\r\n\r\n").unwrap() + 4;
        v[start + 25] = 2;
        assert!(parse_response(&v).is_err());
    }
    #[test] fn rejects_cancelled_before_network() {
        let cancelled = AtomicBool::new(true);
        let png = b"\x89PNG\r\n\x1a\n";
        let token = "abcdefghijklmnopqrstuvwxyz0123456789";
        let err = remove_background_with_cancel(
            "127.0.0.1:18793".parse().unwrap(), token, png, true, &cancelled,
        ).unwrap_err();
        assert!(err.contains("cancelled"));
    }
    #[test] fn cancelling_waiting_http_request_stops_client() {
        use std::net::TcpListener;
        use std::sync::{mpsc, Arc};
        use std::thread;

        let server = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = server.local_addr().unwrap();
        let (accepted_tx, accepted_rx) = mpsc::channel();
        let serving = thread::spawn(move || {
            let (mut peer, _) = server.accept().unwrap();
            peer.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
            let mut request = [0u8; 1024];
            let _ = peer.read(&mut request);
            accepted_tx.send(()).unwrap();
            // Keep the connection alive with no response; the cancelled
            // client must not wait for the full 190-second inference limit.
            thread::sleep(Duration::from_millis(1200));
        });
        let cancel = Arc::new(AtomicBool::new(false));
        let worker_cancel = Arc::clone(&cancel);
        let worker = thread::spawn(move || {
            remove_background_with_cancel(
                endpoint, "abcdefghijklmnopqrstuvwxyz0123456789",
                b"\x89PNG\r\n\x1a\n", true, &worker_cancel,
            )
        });
        accepted_rx.recv_timeout(Duration::from_secs(3)).unwrap();
        cancel.store(true, Ordering::Release);
        let result = worker.join().unwrap();
        assert!(result.unwrap_err().contains("cancelled"));
        serving.join().unwrap();
    }
    #[test] fn server_error_gives_specific_help() {
        for (line, reason) in [
            ("HTTP/1.0 401 Unauthorized", "token"),
            ("HTTP/1.0 403 Forbidden", "consent"),
            ("HTTP/1.0 429 Too Many Requests", "busy"),
            ("HTTP/1.0 504 Gateway Timeout", "timed out"),
        ] {
            let response = format!("{line}\r\nContent-Length: 0\r\n\r\n");
            assert!(parse_response(response.as_bytes()).unwrap_err().contains(reason));
        }
        let redirect = b"HTTP/1.0 302 Found\r\nLocation: http://example.org/\r\n\r\n";
        assert!(parse_response(redirect).is_err());
    }
    #[test] fn consent_and_loopback_required() {
        let png=b"\x89PNG\r\n\x1a\n";
        let token="abcdefghijklmnopqrstuvwxyz0123456789";
        assert!(remove_background("127.0.0.1:18793".parse().unwrap(),token,png,false).is_err());
        assert!(remove_background("192.168.1.10:18793".parse().unwrap(),token,png,true).is_err());
    }
}
