//! Conservative validation for a future AI background-removal result.
//! Pure Rust, no network calls or document mutation. Not wired into the editor.
//! The caller must separately decode PNG, validate pixels, and insert a new
//! undoable layer; these checks alone never authorize enabling the menu.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ImageShape { pub width: u32, pub height: u32 }
pub const MAX_PIXELS: u64 = 16_777_216; // 4096 x 4096 equivalent
pub const MAX_PNG_BYTES: usize = 64 * 1024 * 1024;

pub fn validate_alpha_png(encoded: &[u8], expected: ImageShape) -> Result<(), &'static str> {
    if expected.width == 0 || expected.height == 0 ||
       u64::from(expected.width) * u64::from(expected.height) > MAX_PIXELS {
        return Err("Input dimensions exceed preview safety bounds");
    }
    if encoded.len() < 33 || encoded.len() > MAX_PNG_BYTES {
        return Err("PNG is empty, truncated or oversized");
    }
    if &encoded[..8] != b"\x89PNG\r\n\x1a\n" || &encoded[12..16] != b"IHDR" {
        return Err("Not a PNG with an IHDR header");
    }
    if u32::from_be_bytes(encoded[8..12].try_into().unwrap()) != 13 {
        return Err("Unexpected PNG IHDR size");
    }
    let width = u32::from_be_bytes(encoded[16..20].try_into().unwrap());
    let height = u32::from_be_bytes(encoded[20..24].try_into().unwrap());
    if width != expected.width || height != expected.height {
        return Err("Output dimensions differ from the input");
    }
    if encoded[24] != 8 || !matches!(encoded[25], 4 | 6) {
        return Err("Output must be 8-bit PNG with alpha");
    }
    // This header-only preflight is deliberately insufficient for insertion:
    // require a real PNG decoder with CRC, chunk and pixel validation.
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn header(w:u32,h:u32,kind:u8)->Vec<u8>{
        let mut v=vec![0u8;33];
        v[..8].copy_from_slice(b"\x89PNG\r\n\x1a\n");
        v[8..12].copy_from_slice(&13u32.to_be_bytes());
        v[12..16].copy_from_slice(b"IHDR");
        v[16..20].copy_from_slice(&w.to_be_bytes());
        v[20..24].copy_from_slice(&h.to_be_bytes());
        v[24]=8;v[25]=kind;v
    }
    #[test] fn valid_alpha_header(){assert!(validate_alpha_png(&header(32,32,6),ImageShape{width:32,height:32}).is_ok());}
    #[test] fn rejects_wrong_size(){assert!(validate_alpha_png(&header(32,31,6),ImageShape{width:32,height:32}).is_err());}
    #[test] fn rejects_rgb_without_alpha(){assert!(validate_alpha_png(&header(32,32,2),ImageShape{width:32,height:32}).is_err());}
    #[test] fn rejects_oversized_input(){assert!(validate_alpha_png(&header(1,1,6),ImageShape{width:5000,height:5000}).is_err());}
    #[test] fn rejects_non_png(){assert!(validate_alpha_png(&[0;33],ImageShape{width:1,height:1}).is_err());}
}
