//! OpenFill remote GPU connector foundation for PhotoCraft Android.
//! This module makes no image upload and cannot execute an AI graph.
//! Remote GPU jobs require an independent, consented integration.
//!
//! OpenFill GPU server v0.2.6: ofgpu://TOKEN@TAILSCALE_IP:PORT.
//! The pairing token stays in memory only. Never log it or persist it.
//! A 100.64.0.0/10 address is only an address check, NOT proof that a
//! Tailscale VPN is actually running. The UI must obtain informed consent.

use std::io::{Read, Write};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::time::Duration;

const MAX_HTTP_RESPONSE: u64 = 128 * 1024;
const DEFAULT_PORT: u16 = 8390;

#[derive(Clone)]
pub(crate) struct OpenFillPairing {
    address: SocketAddr,
    token: String,
}

impl OpenFillPairing {
    /// Accept only a full OpenFill pairing line with a numeric Tailscale IPv4.
    /// No DNS, raw ComfyUI URL, LAN HTTP, URI path, fragment or query.
    pub(crate) fn parse(input: &str) -> Result<Self, &'static str> {
        let value = input.trim();
        if value.len() > 256 || value.bytes().any(|b| b.is_ascii_control()) {
            return Err("Invalid pairing-code characters or length");
        }
        let rest = value
            .strip_prefix("ofgpu://")
            .ok_or("Paste the complete ofgpu:// pairing code")?;
        let (token, host_port) = rest
            .split_once('@')
            .ok_or("Pairing code must include token and GPU address")?;
        if token.len() < 16 || token.len() > 128 ||
            !token.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-') {
            return Err("Invalid or incomplete OpenFill pairing token");
        }
        if host_port.contains(&['/', '?', '#', '@', '[', ']'][..]) {
            return Err("GPU address must be numeric Tailscale IPv4 only");
        }
        let (host, port) = match host_port.split_once(':') {
            Some((host, p)) => {
                let port = p.parse::<u16>().map_err(|_| "Invalid GPU port")?;
                (host, port)
            }
            None => (host_port, DEFAULT_PORT),
        };
        if port == 0 {
            return Err("GPU port must be non-zero");
        }
        let ip: Ipv4Addr = host.parse().map_err(|_| "GPU host must be a numeric IPv4 address")?;
        let octets = ip.octets();
        if octets[0] != 100 || !(64..=127).contains(&octets[1]) {
            return Err("Only Tailscale-range addresses (100.64.0.0/10) are accepted in this preview");
        }
        Ok(Self {
            address: SocketAddr::new(IpAddr::V4(ip), port),
            token: token.to_owned(),
        })
    }

    /// Explicit authenticated, read-only handshake with the OpenFill GPU server.
    /// No image, mask, selection, document name or prompt leaves the tablet.
    pub(crate) fn probe_system_stats(&self) -> Result<(), String> {
        let mut stream = TcpStream::connect_timeout(&self.address, Duration::from_secs(5))
            .map_err(|_| "Remote GPU is not reachable; check Tailscale and the server".to_owned())?;
        stream.set_read_timeout(Some(Duration::from_secs(8)))
            .map_err(|_| "Could not set read timeout".to_owned())?;
        stream.set_write_timeout(Some(Duration::from_secs(5)))
            .map_err(|_| "Could not set write timeout".to_owned())?;
        // A token never appears in an error message or in application logs.
        let request = format!(
            "GET /system_stats HTTP/1.0\r\nHost: {}\r\nAuthorization: Bearer {}\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n",
            self.address, self.token
        );
        stream.write_all(request.as_bytes())
            .map_err(|_| "Could not send OpenFill connection test".to_owned())?;
        let mut reply = Vec::new();
        stream.take(MAX_HTTP_RESPONSE + 1).read_to_end(&mut reply)
            .map_err(|_| "OpenFill server did not finish its response".to_owned())?;
        if reply.len() as u64 > MAX_HTTP_RESPONSE {
            return Err("OpenFill status exceeded the 128 KiB safety limit".into());
        }
        check_stats_response(&reply)
    }
}

/// Fail closed for redirects, authorization failures, malformed replies and
/// unexpected services. This does not authenticate the *network route*.
fn check_stats_response(reply: &[u8]) -> Result<(), String> {
    let split = reply.windows(4).position(|w| w == b"\r\n\r\n")
        .ok_or("OpenFill server returned an invalid HTTP response")?;
    let (head, body) = reply.split_at(split);
    let head = std::str::from_utf8(head)
        .map_err(|_| "OpenFill returned invalid HTTP headers")?;
    let first = head.lines().next().unwrap_or("");
    if !first.starts_with("HTTP/1.0 200 ") && !first.starts_with("HTTP/1.1 200 ") {
        return Err("OpenFill remote GPU rejected the request or is unavailable".into());
    }
    let lower_headers = head.to_ascii_lowercase();
    if lower_headers.contains("transfer-encoding:") {
        return Err("Unexpected HTTP transfer encoding from OpenFill GPU server".into());
    }
    let body = std::str::from_utf8(&body[4..])
        .map_err(|_| "OpenFill returned non-text status data")?;
    if !body.trim_start().starts_with('{')
        || !body.contains("\"devices\"")
        || !body.contains("\"system\"") {
        return Err("Remote endpoint did not return ComfyUI system information".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    const TOKEN: &str = "abcdEFGHijklMNOPqrstUVWX01234567";
    fn code(address: &str) -> String { format!("ofgpu://{TOKEN}@{address}") }

    #[test]
    fn accepts_tailscale_pairing_code_only() {
        let pair = OpenFillPairing::parse(&code("100.101.102.103:8390")).unwrap();
        assert_eq!(pair.address, "100.101.102.103:8390".parse().unwrap());
        let pair = OpenFillPairing::parse(&code("100.64.0.1")).unwrap();
        assert_eq!(pair.address.port(), DEFAULT_PORT);
        assert!(OpenFillPairing::parse(&code("100.127.255.254:9999")).is_ok());
    }
    #[test]
    fn refuses_untrusted_endpoints_and_url_tricks() {
        for host in [
            "192.168.0.2:8390", "127.0.0.1:8390", "8.8.8.8:8390",
            "100.128.0.1:8390", "100.63.255.255:8390",
            "gpu.example.com:8390", "100.101.102.103:0",
            "100.101.102.103:65536", "100.101.102.103:8390/a",
            "100.101.102.103:8390?x=y", "100.101.102.103:8390#x",
            "100.101.102.103@evil:8390", "[fd7a:115c:a1e0::1]:8390",
        ] {
            assert!(OpenFillPairing::parse(&code(host)).is_err(), "{host}");
        }
    }
    #[test]
    fn refuses_credentials_and_control_characters() {
        for bad in [
            "https://100.101.102.103:8390", "ofgpu://x@100.101.102.103:8390",
            "ofgpu://@100.101.102.103:8390",
            "ofgpu://abcdefghi\r\nHost:evil@100.101.102.103:8390",
            "ofgpu://abcdefghi/evil@100.101.102.103:8390",
        ] {
            assert!(OpenFillPairing::parse(bad).is_err());
        }
    }
    #[test]
    fn validates_remote_status_without_accepting_redirects_or_401() {
        assert!(check_stats_response(
            b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n{\"system\":{},\"devices\":[]}"
        ).is_ok());
        assert!(check_stats_response(b"HTTP/1.0 401 Unauthorized\r\n\r\n{\"system\":{},\"devices\":[]}").is_err());
        assert!(check_stats_response(b"HTTP/1.0 302 Found\r\nLocation: http://evil\r\n\r\n{\"system\":{},\"devices\":[]}").is_err());
        assert!(check_stats_response(b"HTTP/1.0 200 OK\r\n\r\n{}").is_err());
    }
}
