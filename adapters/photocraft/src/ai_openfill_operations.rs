//! OpenFill's four distinct AI operations: narrow source/output contract.
//!
//! This adapter does not send requests, select models, or modify the editor.
//! It will only become a backend job envelope after a user-approved,
//! authenticated and encrypted transport plus complete image verification.
//! "Remove Object" is NOT the existing U2NetP Remove Background feature.

pub const MAX_IMAGE_PIXELS: u64 = 20_000_000;
pub const MAX_PROMPT_CHARS: usize = 2000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Operation {
    Fill,
    RemoveObject,
    GenerativeExpand,
    Create,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DocVersion { pub document: u64, pub revision: u64 }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Dimensions { pub width: u32, pub height: u32 }
impl Dimensions {
    fn pixels(self) -> Result<u64, &'static str> {
        let count = u64::from(self.width) * u64::from(self.height);
        if count == 0 || count > MAX_IMAGE_PIXELS {
            return Err("AI canvas dimensions exceed the 20MP limit");
        }
        Ok(count)
    }
    pub fn rgba_len(self) -> Result<usize, &'static str> {
        usize::try_from(self.pixels()? * 4).map_err(|_| "AI pixel buffer is too large")
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OutputKind {
    MaskedNewLayer,
    ExpandAndLayerSingleUndo,
    NewDocument,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ValidatedShape {
    pub output: Dimensions,
    pub kind: OutputKind,
}

#[derive(Clone, Debug)]
pub struct JobDraft {
    pub operation: Operation,
    /// None only for "Create" to a new document.
    pub source: Option<DocVersion>,
    /// Source is None for "Create".
    pub input: Option<Dimensions>,
    pub output: Dimensions,
    /// Existing pixels' top-left offset in the expanded canvas.
    pub offset_x: u32,
    pub offset_y: u32,
    /// Count of nonzero pixels in real PhotoCraft selection coverage.
    pub selected_pixels: usize,
    /// UTF-8 request, NEVER stored in logs or persisted by this adapter.
    pub prompt: String,
    /// Whitelisted charset only; model installation and license validation
    /// are separate mandatory backend checks.
    pub model_id: String,
}

impl JobDraft {
    /// Validate intent and geometry only. This never grants permission to
    /// transmit an image, execute a graph, or mutate a PhotoCraft document.
    pub fn validate_intent(&self, consent: bool) -> Result<ValidatedShape, &'static str> {
        if !consent {
            return Err("Explicit consent required for this AI operation");
        }
        self.output.pixels()?;
        if self.prompt.chars().count() > MAX_PROMPT_CHARS ||
            self.prompt.chars().any(|ch| ch.is_control())
        {
            return Err("AI prompt is too long or contains controls");
        }
        // Do not accept a path, raw ComfyUI class name, or arbitrary node
        // text as a verified installed OpenFill model ID.
        if self.model_id.is_empty() || self.model_id.len() > 80 ||
            !self.model_id.bytes().all(|c| c.is_ascii_alphanumeric() || b"_-.".contains(&c))
        {
            return Err("Invalid OpenFill model identifier");
        }

        match self.operation {
            Operation::Fill | Operation::RemoveObject => {
                let doc = self.source.ok_or("Open a document before AI editing")?;
                if doc.document == 0 { return Err("Invalid source document identity"); }
                let input = self.input.ok_or("Input image required")?;
                let pixels = input.pixels()?;
                if self.output != input || self.offset_x != 0 || self.offset_y != 0 {
                    return Err("Fill and Remove Object may not resize the source canvas");
                }
                if self.selected_pixels == 0 || (self.selected_pixels as u64) > pixels {
                    return Err("A real, nonempty selection mask is required");
                }
                if self.operation == Operation::Fill && self.prompt.trim().is_empty() {
                    return Err("A prompt is required for Fill");
                }
                if self.operation == Operation::RemoveObject && !self.prompt.trim().is_empty() {
                    return Err("Remove Object uses a mask and no generative prompt");
                }
                Ok(ValidatedShape {
                    output: self.output, kind: OutputKind::MaskedNewLayer,
                })
            }
            Operation::GenerativeExpand => {
                let doc = self.source.ok_or("Open a document before Expand")?;
                if doc.document == 0 { return Err("Invalid source document identity"); }
                let input = self.input.ok_or("Input canvas required for Expand")?;
                input.pixels()?;
                if self.output.width < input.width || self.output.height < input.height ||
                    self.output == input || self.selected_pixels != 0
                {
                    return Err("Expand must add canvas space without an input selection");
                }
                if self.offset_x > self.output.width - input.width ||
                    self.offset_y > self.output.height - input.height
                {
                    return Err("Expand may not crop or move source pixels outside the canvas");
                }
                Ok(ValidatedShape {
                    output: self.output, kind: OutputKind::ExpandAndLayerSingleUndo,
                })
            }
            Operation::Create => {
                if self.source.is_some() || self.input.is_some() ||
                    self.selected_pixels != 0 || self.offset_x != 0 || self.offset_y != 0
                {
                    return Err("Create new document may not capture an existing document");
                }
                if self.prompt.trim().is_empty() {
                    return Err("A prompt is required for Create");
                }
                Ok(ValidatedShape {
                    output: self.output, kind: OutputKind::NewDocument,
                })
            }
        }
    }

    /// Validate a full decoded output buffer's envelope and source revision.
    /// The actual PNG decoder, pixels, alpha, colorspace, backend model and
    /// one-transaction UI insertion MUST be validated separately.
    pub fn validate_result(
        &self, consent: bool, active: Option<DocVersion>,
        dimensions: Dimensions, rgba_byte_len: usize,
    ) -> Result<OutputKind, &'static str> {
        let plan = self.validate_intent(consent)?;
        if plan.output != dimensions || dimensions.rgba_len()? != rgba_byte_len {
            return Err("AI result does not match validated canvas dimensions");
        }
        if self.source != active {
            return Err("Source document changed while AI was processing");
        }
        Ok(plan.kind)
    }

    /// Derive an outpaint-only alpha mask: 255 outside the old image, 0
    /// inside its offset rect. Preserve every old pixel untouched.
    pub fn expansion_mask(&self, consent: bool) -> Result<Vec<u8>, &'static str> {
        if self.operation != Operation::GenerativeExpand ||
            self.validate_intent(consent)?.kind != OutputKind::ExpandAndLayerSingleUndo
        {
            return Err("Expansion mask requires a validated Expand draft");
        }
        let size = usize::try_from(self.output.pixels()?).map_err(|_| "Canvas too large")?;
        let mut mask = Vec::new();
        mask.try_reserve_exact(size).map_err(|_| "Cannot allocate expansion mask")?;
        mask.resize(size, 255);
        let input = self.input.ok_or("Missing Expand source")?;
        let stride = usize::try_from(self.output.width).map_err(|_| "Invalid canvas stride")?;
        for y in self.offset_y..self.offset_y + input.height {
            let row = usize::try_from(y).map_err(|_| "Invalid Expand row")? * stride;
            let left = row + self.offset_x as usize;
            let right = left + input.width as usize;
            mask[left..right].fill(0);
        }
        Ok(mask)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const SRC: DocVersion = DocVersion { document: 9, revision: 3 };
    fn draft(operation: Operation) -> JobDraft {
        JobDraft {
            operation,
            source: Some(SRC),
            input: Some(Dimensions { width: 3, height: 2 }),
            output: Dimensions { width: 3, height: 2 },
            offset_x: 0, offset_y: 0, selected_pixels: 2,
            prompt: "repair".into(), model_id: "approved-model".into(),
        }
    }
    #[test]
    fn fill_requires_consent_mask_prompt_and_unmodified_canvas() {
        let d = draft(Operation::Fill);
        assert_eq!(d.validate_intent(true).unwrap().kind, OutputKind::MaskedNewLayer);
        assert!(d.validate_intent(false).is_err());
        let mut bad = d.clone();
        bad.selected_pixels = 0;
        assert!(bad.validate_intent(true).is_err());
        bad.selected_pixels = 7;
        assert!(bad.validate_intent(true).is_err());
        bad.selected_pixels = 2;
        bad.prompt.clear();
        assert!(bad.validate_intent(true).is_err());
        bad.prompt = "repair".into();
        bad.output.width = 4;
        assert!(bad.validate_intent(true).is_err());
    }
    #[test]
    fn remove_object_has_mask_not_prompt_and_is_not_bg_removal() {
        let mut d = draft(Operation::RemoveObject);
        assert!(d.validate_intent(true).is_err());
        d.prompt.clear();
        assert_eq!(d.validate_intent(true).unwrap().kind, OutputKind::MaskedNewLayer);
        d.selected_pixels = 0;
        assert!(d.validate_intent(true).is_err());
    }
    #[test]
    fn expand_preserves_original_rectangle_and_rejects_cropping() {
        let mut d = draft(Operation::GenerativeExpand);
        d.selected_pixels = 0;
        d.output = Dimensions { width: 6, height: 4 };
        d.offset_x = 2; d.offset_y = 1;
        assert_eq!(d.validate_intent(true).unwrap().kind, OutputKind::ExpandAndLayerSingleUndo);
        let mask = d.expansion_mask(true).unwrap();
        assert_eq!(mask.len(), 24);
        for y in 0..4usize {
            for x in 0..6usize {
                let inside = (1..3).contains(&y) && (2..5).contains(&x);
                assert_eq!(mask[y * 6 + x], if inside { 0 } else { 255 });
            }
        }
        d.offset_x = 4;
        assert!(d.validate_intent(true).is_err());
        d.offset_x = 0;
        d.output = d.input.unwrap();
        assert!(d.validate_intent(true).is_err());
    }
    #[test]
    fn create_has_no_source_and_requires_prompt_and_bounded_output() {
        let mut d = draft(Operation::Create);
        assert!(d.validate_intent(true).is_err());
        d.source = None; d.input = None; d.selected_pixels = 0;
        assert_eq!(d.validate_intent(true).unwrap().kind, OutputKind::NewDocument);
        d.prompt.clear();
        assert!(d.validate_intent(true).is_err());
        d.prompt = "forest".into();
        d.output = Dimensions { width: 5000, height: 5000 };
        assert!(d.validate_intent(true).is_err());
    }
    #[test]
    fn result_must_match_live_revision_and_expected_rgba_size() {
        let d = draft(Operation::Fill);
        assert!(d.validate_result(true, Some(SRC), d.output, 24).is_ok());
        assert!(d.validate_result(true, Some(DocVersion { document: 9, revision: 4 }), d.output, 24).is_err());
        assert!(d.validate_result(true, Some(SRC), d.output, 23).is_err());
        assert!(d.validate_result(true, Some(SRC), Dimensions { width: 3, height: 3 }, 36).is_err());
    }
    #[test]
    fn invalid_model_and_prompt_controls_fail_closed() {
        let mut d = draft(Operation::Fill);
        for bad in ["", "../x", "model/name", "bad:model", "x\nmodel"] {
            d.model_id = bad.into();
            assert!(d.validate_intent(true).is_err(), "{bad:?}");
        }
        d.model_id = "safe".into();
        d.prompt = "hello\0world".into();
        assert!(d.validate_intent(true).is_err());
    }
}
