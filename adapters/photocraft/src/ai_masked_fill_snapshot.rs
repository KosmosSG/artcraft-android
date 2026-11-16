//! Offline, fail-closed raster+selection handoff for future PhotoCraft masked Fill.
//! This is NOT connected to editor selection capture, networking, ComfyUI, or a menu.
//! It cannot generate an image or insert a layer. No background work or I/O.
//! Only RGB 8-bit RGBA source pixels and 8-bit feathered canvas masks are accepted.

pub const MAX_PIXELS: u64 = 20_000_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SourceRevision {
    pub document: u64,
    pub revision: u64,
}

/// Owns a point-in-time copy. Never borrow a mutable PhotoCraft layer across jobs.
/// Explicit consent is required before even preparing potentially private pixels.
pub struct MaskedFillSnapshot {
    origin: SourceRevision,
    width: u32,
    height: u32,
    source_rgba: Vec<u8>,
    mask_alpha: Vec<u8>,
    selected_pixels: usize,
}

impl MaskedFillSnapshot {
    pub fn prepare(
        origin: SourceRevision,
        width: u32,
        height: u32,
        source_rgba: &[u8],
        mask_alpha: &[u8],
        consent: bool,
    ) -> Result<Self, &'static str> {
        if !consent {
            return Err("Explicit consent is required before capturing image pixels");
        }
        let pixels = u64::from(width) * u64::from(height);
        if pixels == 0 || pixels > MAX_PIXELS {
            return Err("Canvas dimensions exceed the masked Fill preview limit");
        }
        let count = usize::try_from(pixels).map_err(|_| "Canvas size is unsupported")?;
        if source_rgba.len() != count * 4 || mask_alpha.len() != count {
            return Err("Image and selection mask dimensions must match exactly");
        }
        let selected_pixels = mask_alpha.iter().filter(|&&v| v > 0).count();
        if selected_pixels == 0 {
            return Err("A nonempty selection mask is required");
        }
        Ok(Self {
            origin, width, height, source_rgba: source_rgba.to_vec(),
            mask_alpha: mask_alpha.to_vec(), selected_pixels,
        })
    }

    pub fn source_revision(&self) -> SourceRevision { self.origin }
    pub fn dimensions(&self) -> (u32, u32) { (self.width, self.height) }
    pub fn selected_pixels(&self) -> usize { self.selected_pixels }
    pub fn immutable_source_rgba(&self) -> &[u8] { &self.source_rgba }
    pub fn immutable_mask_alpha(&self) -> &[u8] { &self.mask_alpha }

    /// Translate a *fully decoded*, untrusted generated RGBA raster into
    /// a new transparent-over-source layer. Never alter the captured source.
    /// Caller MUST validate document+revision again on the UI thread and
    /// use PhotoCraft's undoable Session::edit to insert the raster layer.
    /// This is a pixel-only preparation function, NOT an editor commit.
    pub fn masked_result_layer(
        &self,
        current: SourceRevision,
        generated_rgba: &[u8],
    ) -> Result<Vec<u8>, &'static str> {
        if current != self.origin {
            return Err("Source document changed; discard the AI result");
        }
        if generated_rgba.len() != self.source_rgba.len() {
            return Err("Generated image dimensions or pixel buffer are invalid");
        }
        let mut layer = vec![0u8; generated_rgba.len()];
        let mut any_visible = false;
        for (i, &mask) in self.mask_alpha.iter().enumerate() {
            // Unselected pixels remain 0,0,0,0; no generated image data leaks.
            if mask == 0 { continue; }
            let p = i * 4;
            let generated_alpha = generated_rgba[p + 3];
            let alpha = (u16::from(mask) * u16::from(generated_alpha) + 127) / 255;
            if alpha == 0 { continue; }
            any_visible = true;
            layer[p..p + 3].copy_from_slice(&generated_rgba[p..p + 3]);
            layer[p + 3] = alpha as u8;
        }
        if !any_visible {
            return Err("Generated result has no visible pixels in the selection");
        }
        Ok(layer)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const REV: SourceRevision = SourceRevision { document: 7, revision: 4 };
    fn sample() -> (Vec<u8>, Vec<u8>) {
        (vec![10u8, 20, 30, 255, 11, 21, 31, 255, 12, 22, 32, 255],
         vec![0u8, 128, 255])
    }
    #[test]
    fn rejects_missing_consent_wrong_sizes_and_empty_selection() {
        let (src, mask) = sample();
        assert!(MaskedFillSnapshot::prepare(REV, 3, 1, &src, &mask, false).is_err());
        assert!(MaskedFillSnapshot::prepare(REV, 0, 1, &src, &mask, true).is_err());
        assert!(MaskedFillSnapshot::prepare(REV, 5_000, 5_000, &src, &mask, true).is_err());
        assert!(MaskedFillSnapshot::prepare(REV, 3, 1, &src[..8], &mask, true).is_err());
        assert!(MaskedFillSnapshot::prepare(REV, 3, 1, &src, &mask[..2], true).is_err());
        assert!(MaskedFillSnapshot::prepare(REV, 3, 1, &src, &[0, 0, 0], true).is_err());
    }
    #[test]
    fn source_is_immutable_and_layer_stays_within_feathered_mask() {
        let (src, mask) = sample();
        let snapshot = MaskedFillSnapshot::prepare(REV, 3, 1, &src, &mask, true).unwrap();
        assert_eq!(snapshot.selected_pixels(), 2);
        assert_eq!(snapshot.dimensions(), (3, 1));
        let generated = vec![222, 223, 224, 255, 201, 202, 203, 255, 204, 205, 206, 128];
        let layer = snapshot.masked_result_layer(REV, &generated).unwrap();
        assert_eq!(&layer[..4], &[0, 0, 0, 0]);
        assert_eq!(&layer[4..8], &[201, 202, 203, 128]);
        assert_eq!(&layer[8..12], &[204, 205, 206, 128]);
        assert_eq!(snapshot.immutable_source_rgba(), src.as_slice());
        assert_eq!(snapshot.immutable_mask_alpha(), mask.as_slice());
    }
    #[test]
    fn rejects_stale_revision_invalid_output_and_transparent_result() {
        let (src, mask) = sample();
        let snapshot = MaskedFillSnapshot::prepare(REV, 3, 1, &src, &mask, true).unwrap();
        assert!(snapshot.masked_result_layer(
            SourceRevision { document: 7, revision: 5 }, &src).is_err());
        assert!(snapshot.masked_result_layer(
            SourceRevision { document: 8, revision: 4 }, &src).is_err());
        assert!(snapshot.masked_result_layer(REV, &src[..8]).is_err());
        assert!(snapshot.masked_result_layer(REV, &[0; 12]).is_err());
    }
}
