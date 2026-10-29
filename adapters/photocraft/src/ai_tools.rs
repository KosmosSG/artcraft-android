//! Foundation for optional AI tools in the PhotoCraft Android adapter.
//! Opt-in private-LAN ComfyUI connectivity check. It does not upload images,
//! run models, or alter a PhotoCraft document. No extra dependencies.
use std::io::{Read, Write};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::time::Duration;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AiAction {
    RemoveBackground,
    RemoveObject,
    GenerativeFill,
    GenerativeExpand,
    Upscale,
}

impl AiAction {
    pub const ALL: [Self; 5] = [
        Self::RemoveBackground, Self::RemoveObject, Self::GenerativeFill,
        Self::GenerativeExpand, Self::Upscale,
    ];
    pub const fn label(self) -> &'static str {
        match self {
            Self::RemoveBackground => "Remove Background",
            Self::RemoveObject => "Remove Object",
            Self::GenerativeFill => "Generative Fill",
            Self::GenerativeExpand => "Generative Expand",
            Self::Upscale => "AI Upscale",
        }
    }
    pub const fn requires_backend(self) -> bool {
        !matches!(self, Self::RemoveBackground | Self::Upscale)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ComfyEndpoint {
    pub host: String,
    pub port: u16,
}

impl ComfyEndpoint {
    /// Only HTTP host:port addresses are accepted in phase 1.
    /// An external LAN endpoint must be explicitly enabled by the user.
    /// The caller must separately enforce authentication and transport policy.
    pub fn parse(input: &str, allow_remote: bool) -> Result<Self, &'static str> {
        let stripped = input.trim().strip_prefix("http://")
            .ok_or("Only http:// endpoints are supported in this prototype")?;
        if stripped.contains(&['/', '?', '#', '@'][..]) {
            return Err("Endpoint must contain only a host and port");
        }
        let (host, port_text) = if stripped.starts_with('[') {
            let closing = stripped.find(']').ok_or("Invalid IPv6 host")?;
            let host = &stripped[1..closing];
            let port = stripped[closing + 1..].strip_prefix(':')
                .ok_or("Missing port")?;
            (host, port)
        } else {
            stripped.rsplit_once(':').ok_or("Missing port")?
        };
        let port: u16 = port_text.parse().map_err(|_| "Invalid port")?;
        if port == 0 { return Err("Port must be non-zero"); }
        if host.is_empty() || host.chars().any(|c| c.is_whitespace()) {
            return Err("Invalid hostname");
        }
        let local = host.eq_ignore_ascii_case("localhost")
            || host.parse::<IpAddr>().map(|ip| ip.is_loopback()).unwrap_or(false);
        if !local && !allow_remote { return Err("LAN connections require explicit opt-in"); }
        // For phase 1 accept IP literals and localhost only, avoiding DNS rebinding
        // and implicit network reachability from a user-supplied hostname.
        if !host.eq_ignore_ascii_case("localhost") && host.parse::<IpAddr>().is_err() {
            return Err("Use localhost or a numeric IP address");
        }
        if !local {
            // RFC1918 IPv4 and unique-local IPv6 only. No public endpoints,
            // carrier NAT, link-local, multicast or domain names in phase 2.
            let ip: IpAddr = host.parse().map_err(|_| "Invalid IP address")?;
            let private = match ip {
                IpAddr::V4(v4) => v4.is_private(),
                IpAddr::V6(v6) => v6.is_unique_local(),
            };
            if !private { return Err("Only private LAN IP addresses are allowed"); }
        }
        Ok(Self { host: host.to_string(), port })
    }
    pub fn socket_addr(&self) -> Option<SocketAddr> {
        let ip = if self.host.eq_ignore_ascii_case("localhost") {
            IpAddr::V4(Ipv4Addr::LOCALHOST)
        } else { self.host.parse().ok()? };
        Some(SocketAddr::new(ip, self.port))
    }
    pub fn is_loopback(&self) -> bool {
        self.socket_addr().map(|a| a.ip().is_loopback()).unwrap_or(false)
    }

    /// An explicit, bounded GET /system_stats to a previously validated
    /// endpoint. Runs only on the background thread; does not upload data.
    pub fn probe_system_stats(&self) -> Result<(), String> {
        let addr = self.socket_addr().ok_or("Invalid endpoint address")?;
        let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(4))
            .map_err(|e| format!("Unable to reach ComfyUI: {e}"))?;
        stream.set_read_timeout(Some(Duration::from_secs(4)))
            .map_err(|e| format!("Read timeout setup failed: {e}"))?;
        stream.set_write_timeout(Some(Duration::from_secs(4)))
            .map_err(|e| format!("Write timeout setup failed: {e}"))?;

        // ComfyUI is an aiohttp HTTP/1.1 server. Explicit identity encoding,
        // no redirects, and a fixed path avoid negotiating unknown content.
        let host = if self.host.contains(':') {
            format!("[{}]", self.host)
        } else {
            self.host.clone()
        };
        let request = format!(
            "GET /system_stats HTTP/1.1\r\nHost: {host}:{}\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n",
            self.port
        );
        stream.write_all(request.as_bytes())
            .map_err(|e| format!("ComfyUI request failed: {e}"))?;

        let mut reply = Vec::with_capacity(4096);
        let mut chunk = [0u8; 4096];
        loop {
            match stream.read(&mut chunk) {
                Ok(0) => {
                    return parse_stats_response(&reply, true)?
                        .ok_or_else(|| "ComfyUI closed an incomplete response".into());
                }
                Ok(n) => {
                    if reply.len() + n > 128 * 1024 {
                        return Err("ComfyUI response exceeded the 128 KiB safety limit".into());
                    }
                    reply.extend_from_slice(&chunk[..n]);
                    // IMPORTANT: ComfyUI may keep a TCP connection open even
                    // after sending the complete JSON. Honor HTTP framing
                    // instead of waiting indefinitely for socket EOF/EAGAIN.
                    if let Some(()) = parse_stats_response(&reply, false)? {
                        return Ok(());
                    }
                }
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(e) if matches!(
                    e.kind(),
                    std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock
                ) => {
                    return Err("Timed out waiting for the complete ComfyUI /system_stats response; verify the server is still running".into());
                }
                Err(e) => return Err(format!("ComfyUI response read failed: {e}")),
            }
        }
    }
}

/// Parse a complete HTTP response using Content-Length or chunked framing.
/// Without an explicit length, wait for EOF instead of treating a truncated
/// body as a successful connection. A failed /system_stats response never
/// becomes permission to upload or process images.
fn parse_stats_response(reply: &[u8], eof: bool) -> Result<Option<()>, String> {
    let Some(header_end) = reply.windows(4).position(|w| w == b"\r\n\r\n") else {
        return if eof {
            Err("ComfyUI sent an incomplete HTTP header".into())
        } else {
            Ok(None)
        };
    };
    if header_end > 16 * 1024 {
        return Err("ComfyUI response headers are too large".into());
    }
    let header = std::str::from_utf8(&reply[..header_end])
        .map_err(|_| "ComfyUI returned invalid HTTP headers")?;
    let mut lines = header.split("\r\n");
    let status = lines.next().unwrap_or("");
    if !(status.starts_with("HTTP/1.0 ") || status.starts_with("HTTP/1.1 "))
        || status.split_whitespace().nth(1) != Some("200")
    {
        return Err(format!(
            "ComfyUI connection test failed: {}",
            status.chars().take(90).collect::<String>()
        ));
    }

    let mut content_length = None;
    let mut chunked = false;
    let mut is_json = false;
    for line in lines {
        let (name, value) = line.split_once(':')
            .ok_or("Malformed ComfyUI HTTP header")?;
        let value = value.trim();
        if name.eq_ignore_ascii_case("Content-Length") {
            if content_length.is_some() {
                return Err("Duplicate HTTP Content-Length".into());
            }
            let size = value.parse::<usize>().map_err(|_| "Invalid Content-Length")?;
            if size > 128 * 1024 {
                return Err("ComfyUI JSON response exceeds the safety limit".into());
            }
            content_length = Some(size);
        } else if name.eq_ignore_ascii_case("Transfer-Encoding") {
            if !value.eq_ignore_ascii_case("chunked") {
                return Err("Unsupported ComfyUI transfer encoding".into());
            }
            chunked = true;
        } else if name.eq_ignore_ascii_case("Content-Type") {
            is_json = value.to_ascii_lowercase().starts_with("application/json");
        }
    }
    if !is_json {
        return Err("Server did not return JSON as ComfyUI should".into());
    }
    if chunked && content_length.is_some() {
        return Err("Conflicting HTTP response framing".into());
    }

    let body = &reply[header_end + 4..];
    if chunked {
        return match decode_chunked_body(body)? {
            Some(json) => validate_stats_json(&json).map(Some),
            None if eof => Err("ComfyUI truncated its chunked response".into()),
            None => Ok(None),
        };
    }
    if let Some(size) = content_length {
        return if body.len() >= size {
            validate_stats_json(&body[..size]).map(Some)
        } else if eof {
            Err("ComfyUI truncated its JSON response".into())
        } else {
            Ok(None)
        };
    }
    if eof {
        return validate_stats_json(body).map(Some);
    }
    Ok(None)
}

/// Minimal RFC 9112 chunked decoder for the ComfyUI diagnostic response.
fn decode_chunked_body(raw: &[u8]) -> Result<Option<Vec<u8>>, String> {
    let mut offset = 0usize;
    let mut decoded = Vec::new();
    loop {
        let Some(end) = raw[offset..].windows(2).position(|w| w == b"\r\n") else {
            return Ok(None);
        };
        let line = std::str::from_utf8(&raw[offset..offset + end])
            .map_err(|_| "Invalid chunk size line")?;
        let size = usize::from_str_radix(
            line.split(';').next().unwrap_or("").trim(), 16
        ).map_err(|_| "Invalid chunk size")?;
        offset += end + 2;
        if size > 128 * 1024 - decoded.len() {
            return Err("ComfyUI chunked response exceeds safety limit".into());
        }
        if size == 0 {
            if raw.len() < offset + 2 { return Ok(None); }
            if raw[offset..].starts_with(b"\r\n") {
                return Ok(Some(decoded));
            }
            // Optional HTTP trailers. Ignore their values, do not trust
            // them to override the already validated response headers.
            return if raw[offset..].windows(4).any(|w| w == b"\r\n\r\n") {
                Ok(Some(decoded))
            } else {
                Ok(None)
            };
        }
        if raw.len() < offset + size + 2 { return Ok(None); }
        if &raw[offset + size..offset + size + 2] != b"\r\n" {
            return Err("Invalid ComfyUI chunk framing".into());
        }
        decoded.extend_from_slice(&raw[offset..offset + size]);
        offset += size + 2;
    }
}

fn validate_stats_json(body: &[u8]) -> Result<(), String> {
    let json = std::str::from_utf8(body)
        .map_err(|_| "ComfyUI returned invalid JSON encoding")?;
    let json = json.trim();
    // No new crate dependencies in the owner-tested Android adapter. The
    // response is still only a reachability diagnostic, never authorization
    // for image processing or a claim that a model is installed.
    if !json.starts_with('{') || !json.ends_with('}')
        || !json.contains("\"system\"") || !json.contains("\"devices\"")
    {
        return Err("Server did not return recognizable ComfyUI /system_stats JSON".into());
    }
    Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn tools_have_distinct_labels() {
        let labels: Vec<_> = AiAction::ALL.iter().map(|a| a.label()).collect();
        for (i, left) in labels.iter().enumerate() {
            assert!(!left.is_empty());
            assert!(!labels[i + 1..].contains(left));
        }
    }
    #[test]
    fn localhost_is_allowed() {
        assert!(ComfyEndpoint::parse("http://127.0.0.1:8188", false).unwrap().is_loopback());
        assert!(ComfyEndpoint::parse("http://[::1]:8188", false).unwrap().is_loopback());
    }
    #[test]
    fn remote_requires_opt_in() {
        assert!(ComfyEndpoint::parse("http://192.168.1.20:8188", false).is_err());
        assert!(!ComfyEndpoint::parse("http://192.168.1.20:8188", true).unwrap().is_loopback());
    }
    #[test]
    fn reject_public_or_link_local_targets() {
        for value in [
            "http://8.8.8.8:8188", "http://169.254.1.2:8188",
            "http://224.0.0.1:8188", "http://1.1.1.1:8188",
            "http://[fe80::1]:8188",
        ] {
            assert!(ComfyEndpoint::parse(value, true).is_err(), "{value}");
        }
        assert!(ComfyEndpoint::parse("http://10.0.0.1:8188", true).is_ok());
        assert!(ComfyEndpoint::parse("http://172.16.0.1:8188", true).is_ok());
        assert!(ComfyEndpoint::parse("http://[fd12::1]:8188", true).is_ok());
    }
    #[test]
    fn test_comfyui_probe_uses_only_system_stats() {
        use std::net::TcpListener;
        use std::thread;
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = thread::spawn(move || {
            let (mut socket, _) = listener.accept().unwrap();
            socket.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
            let mut request = [0u8; 1024];
            let n = socket.read(&mut request).unwrap();
            let text = std::str::from_utf8(&request[..n]).unwrap();
            assert!(text.starts_with("GET /system_stats HTTP/1.0\r\n"));
            assert!(!text.contains("/prompt"));
            socket.write_all(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"system\":{},\"devices\":[]}").unwrap();
        });
        let endpoint = ComfyEndpoint::parse(&format!("http://127.0.0.1:{port}"), false).unwrap();
        endpoint.probe_system_stats().unwrap();
        server.join().unwrap();
    }
    #[test]
    fn non_comfy_response_is_not_success() {
        use std::net::TcpListener;
        use std::thread;
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = thread::spawn(move || {
            let (mut socket, _) = listener.accept().unwrap();
            let mut request = [0u8; 1024];
            socket.read(&mut request).unwrap();
            socket.write_all(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n<html>Not ComfyUI</html>").unwrap();
        });
        let endpoint = ComfyEndpoint::parse(&format!("http://127.0.0.1:{port}"), false).unwrap();
        assert!(endpoint.probe_system_stats().is_err());
        server.join().unwrap();
    }
    #[test]
    fn reject_invalid_endpoints() {
        for value in ["https://localhost:8188", "http://localhost:0",
            "http://localhost:8188/path", "http://user@localhost:8188",
            "http://example.com:8188", "http://localhost:abc"] {
            assert!(ComfyEndpoint::parse(value, true).is_err(), "{value}");
        }
    }
}
