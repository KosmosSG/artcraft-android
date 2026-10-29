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

    /// Explicit, bounded GET /system_stats request to ComfyUI. Call off the UI
    /// thread. No redirects, authentication, credentials, prompts or image bytes.
    /// This is a reachability probe, NOT authorization to process images.
    pub fn probe_system_stats(&self) -> Result<(), String> {
        let addr = self.socket_addr().ok_or("Invalid endpoint address")?;
        let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(4))
            .map_err(|e| format!("Unable to reach ComfyUI: {e}"))?;
        stream.set_read_timeout(Some(Duration::from_secs(4)))
            .map_err(|e| format!("Read timeout setup failed: {e}"))?;
        stream.set_write_timeout(Some(Duration::from_secs(4)))
            .map_err(|e| format!("Write timeout setup failed: {e}"))?;
        // Host is strictly a numeric IP or localhost, validated before this
        // method is called. Never forward user input into an HTTP path.
        let host = if self.host.contains(':') {
            format!("[{}]", self.host)
        } else {
            self.host.clone()
        };
        let request = format!("GET /system_stats HTTP/1.0\r\nHost: {host}:{}\r\nAccept: application/json\r\nConnection: close\r\n\r\n", self.port);
        stream.write_all(request.as_bytes())
            .map_err(|e| format!("ComfyUI request failed: {e}"))?;

        let mut reply = Vec::with_capacity(4096);
        let mut chunk = [0u8; 4096];
        loop {
            let bytes = stream.read(&mut chunk)
                .map_err(|e| format!("ComfyUI did not respond: {e}"))?;
            if bytes == 0 { break; }
            if reply.len() + bytes > 128 * 1024 {
                return Err("ComfyUI response exceeded the safe limit".into());
            }
            reply.extend_from_slice(&chunk[..bytes]);
        }
        let response = std::str::from_utf8(&reply)
            .map_err(|_| "ComfyUI returned non-UTF8 data")?;
        let (headers, body) = response.split_once("\r\n\r\n")
            .ok_or("ComfyUI returned an invalid HTTP response")?;
        let status = headers.lines().next().unwrap_or("");
        // Require an actual 200 from this endpoint, do not follow redirects
        // (or accidentally contact a different host).
        if !status.starts_with("HTTP/1.") || status.split_whitespace().nth(1) != Some("200") {
            return Err(format!("ComfyUI connection test failed: {}", status.chars().take(90).collect::<String>()));
        }
        // ComfyUI /system_stats responds with JSON containing the system key.
        // A 200 from an arbitrary webserver is not a confirmed ComfyUI host.
        if !body.contains("\"system\"") || !body.contains('{') {
            return Err("Server responded, but did not return ComfyUI system statistics".into());
        }
        Ok(())
    }
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
