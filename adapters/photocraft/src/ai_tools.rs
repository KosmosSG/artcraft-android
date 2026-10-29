//! Foundation for optional AI tools in the PhotoCraft Android adapter.
//! Deliberately has no model execution, no networking and no dependency changes.
//! Wire into the adapter UI only after native menu and layer APIs are verified.
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr};

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
        if !local && !allow_remote { return Err("Remote connections are disabled"); }
        // For phase 1 accept IP literals and localhost only, avoiding DNS rebinding
        // and implicit network reachability from a user-supplied hostname.
        if !host.eq_ignore_ascii_case("localhost") && host.parse::<IpAddr>().is_err() {
            return Err("Use localhost or a numeric IP address");
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
    fn reject_invalid_endpoints() {
        for value in ["https://localhost:8188", "http://localhost:0",
            "http://localhost:8188/path", "http://user@localhost:8188",
            "http://example.com:8188", "http://localhost:abc"] {
            assert!(ComfyEndpoint::parse(value, true).is_err(), "{value}");
        }
    }
}
