//! Non-destructive PhotoCraft OpenFill worker decoding and UI-thread commits.
//! Never mutate Session in a worker. All model output is untrusted until fully
//! decoded, checked against the draft's dimensions, and revision-checked.
use photocraft_doc::{
    ColorMode, Document, Layer, LayerContent, PixelFormat, Rect, SampleType, Size, Surface,
};
use photocraft_engine::Session;
use crate::ai_background_editor;
use crate::ai_background_job::DocumentRevision;
use crate::ai_masked_fill_snapshot::{MaskedFillSnapshot, SourceRevision};
use crate::ai_openfill_operations::{Dimensions, DocVersion, JobDraft, Operation};
use crate::ai_output_validation::{validate_alpha_png, ImageShape};
use crate::ai_u2netp_transport::MAX_OUTPUT;

fn rect(size: Dimensions) -> Result<Rect, String> {
    let width = i32::try_from(size.width).map_err(|_| "AI image width is too large")?;
    let height = i32::try_from(size.height).map_err(|_| "AI image height is too large")?;
    Ok(Rect::new(0, 0, width, height))
}

/// Fully decode an RGBA PNG with PhotoCraft's own importer, then read
/// straight RGBA8 pixels. Header-only checks are never trusted.
fn decode_rgba_png(png: &[u8], size: Dimensions, require_alpha: bool) -> Result<Vec<u8>, String> {
    let expected = size.rgba_len().map_err(str::to_owned)?;
    if png.is_empty() || png.len() > MAX_OUTPUT {
        return Err("OpenFill PNG exceeds the image output limit".into());
    }
    if require_alpha {
        validate_alpha_png(png, ImageShape { width: size.width, height: size.height })
            .map_err(str::to_owned)?;
    }
    let imported = photocraft_io::import("ai-openfill-output.png", png)
        .map_err(|_| "OpenFill PNG could not be fully decoded")?;
    let doc = imported.document;
    if doc.size.width != size.width || doc.size.height != size.height ||
        doc.mode != ColorMode::Rgb || doc.depth != SampleType::U8 || doc.layers.len() != 1 {
        return Err("OpenFill decoded image format or size does not match the request".into());
    }
    let surface = match &doc.layers[0].content {
        LayerContent::Raster(s) => s,
        _ => return Err("OpenFill output was not a raster layer".into()),
    };
    let area = rect(size)?;
    surface.region_health(area).map_err(|_| "OpenFill decoded image tiles are unreadable")?;
    let pixels = expected / 4;
    let mut output = Vec::<[u8; 4]>::new();
    output.try_reserve_exact(pixels).map_err(|_| "No memory for OpenFill output")?;
    output.resize(pixels, [0; 4]);
    surface.read_rgba8_into(area, &mut output);
    surface.region_health(area).map_err(|_| "OpenFill output pixels could not be read")?;
    let mut rgba = Vec::new();
    rgba.try_reserve_exact(expected).map_err(|_| "No memory for OpenFill RGBA")?;
    for pixel in output { rgba.extend_from_slice(&pixel); }
    Ok(rgba)
}

/// Untrusted AI output is required to be 8-bit PNG with an alpha channel.
pub fn decode_output_png(png: &[u8], size: Dimensions) -> Result<Vec<u8>, String> {
    decode_rgba_png(png, size, true)
}

/// Snapshot visible composite into immutable RGBA bytes. This is expensive;
/// run in a worker after explicit opt-in, never on the Android UI thread.
pub fn capture_source_rgba(doc: &Document, version: DocumentRevision)
    -> Result<Vec<u8>, String>
{
    if doc.id.0 != version.document {
        return Err("OpenFill source document identity mismatch".into());
    }
    let png = ai_background_editor::capture_png(doc)?;
    decode_rgba_png(&png, Dimensions {
        width: doc.size.width, height: doc.size.height,
    }, false)
}

/// Produce an isolated new RGB8 raster layer; never paint into an old layer.
pub fn new_layer(label: &str, shape: Dimensions, rgba: &[u8]) -> Result<Layer, String> {
    if shape.rgba_len().map_err(str::to_owned)? != rgba.len() {
        return Err("OpenFill raster layer byte size mismatch".into());
    }
    let mut surface = Surface::new(PixelFormat::RGBA8);
    surface.try_write_interleaved(rect(shape)?, rgba)
        .map_err(|_| "Not enough memory to construct OpenFill raster layer")?;
    Ok(Layer::new(label, LayerContent::Raster(surface)))
}

/// Only selected pixels survive. A feathered mask remains feathered,
/// every unselected pixel is transparent, and source bytes are untouched.
pub fn prepare_masked_layer(
    draft: &JobDraft, snapshot: &MaskedFillSnapshot, output_png: &[u8],
) -> Result<Layer, String> {
    if !matches!(draft.operation, Operation::Fill | Operation::RemoveObject) {
        return Err("Masked layer requires Fill or Remove Object".into());
    }
    let source = draft.source.ok_or("Missing source revision")?;
    let actual = snapshot.source_revision();
    if source.document != actual.document || source.revision != actual.revision ||
        snapshot.dimensions() != (draft.output.width, draft.output.height) {
        return Err("OpenFill source/mask changed while processing".into());
    }
    let generated = decode_output_png(output_png, draft.output)?;
    let pixels = snapshot.masked_result_layer(
        SourceRevision { document: source.document, revision: source.revision }, &generated
    ).map_err(str::to_owned)?;
    new_layer(match draft.operation {
        Operation::Fill => "AI · Fill with Prompt",
        _ => "AI · Remove Object",
    }, draft.output, &pixels)
}

/// Non-destructive expand supporting new space to the right/bottom.
/// A single undo step resizes the canvas AND adds a generated transparent
/// outpaint-only layer. Existing layers, pixels and positions are untouched.
pub fn prepare_expand_layer(draft: &JobDraft, output_png: &[u8]) -> Result<Layer, String> {
    if draft.operation != Operation::GenerativeExpand ||
        draft.offset_x != 0 || draft.offset_y != 0 {
        return Err("This Expand preview supports right/bottom expansion only".into());
    }
    let original = draft.input.ok_or("Expand source dimensions missing")?;
    let mut pixels = decode_output_png(output_png, draft.output)?;
    let stride = draft.output.width as usize * 4;
    let row_bytes = original.width as usize * 4;
    for y in 0..original.height as usize {
        pixels[y * stride..y * stride + row_bytes].fill(0);
    }
    new_layer("AI · Generative Expand", draft.output, &pixels)
}

/// UI-thread-only commit with exact document version and one Undo transaction.
pub fn commit_layer(
    session: &mut Session, draft: &JobDraft, layer: Layer,
) -> Result<(), String> {
    let expected = draft.source.ok_or("Missing origin document")?;
    let live = ai_background_editor::current_revision(session);
    if live != Some(DocumentRevision { document: expected.document, revision: expected.revision }) {
        return Err("Document changed during OpenFill; result discarded".into());
    }
    let name = match draft.operation {
        Operation::Fill => "AI · Fill with Prompt",
        Operation::RemoveObject => "AI · Remove Object",
        Operation::GenerativeExpand => "AI · Generative Expand",
        Operation::Create => return Err("Create result must open a new document".into()),
    };
    if draft.operation == Operation::GenerativeExpand {
        if draft.offset_x != 0 || draft.offset_y != 0 {
            return Err("Expand with top/left offsets is not yet supported".into());
        }
        let shape = draft.output;
        session.edit(name, move |doc, active| {
            doc.size = Size::new(shape.width, shape.height);
            doc.selection = None;
            let id = doc.insert_above(*active, layer);
            *active = Some(id);
            Ok(())
        }).map_err(|e| format!("OpenFill expand could not be recorded in Undo: {e}"))
    } else {
        session.edit(name, move |doc, active| {
            let id = doc.insert_above(*active, layer);
            *active = Some(id);
            Ok(())
        }).map_err(|e| format!("OpenFill layer could not be recorded in Undo: {e}"))
    }
}

/// UI thread: never change an existing document for text-to-image Create.
/// Add a blank new document and insert generation as its first Undo step.
pub fn commit_create(
    session: &mut Session, draft: &JobDraft, layer: Layer,
) -> Result<(), String> {
    if draft.operation != Operation::Create || draft.source.is_some() {
        return Err("Create must target a new document".into());
    }
    draft.output.rgba_len().map_err(str::to_owned)?;
    let shape = draft.output;
    let document = Document::new(
        "AI · Create", Size::new(shape.width, shape.height),
        ColorMode::Rgb, SampleType::U8,
    );
    let _index = session.add_document(document, None);
    session.edit("AI · Create", move |doc, active| {
        let id = doc.insert_above(*active, layer);
        *active = Some(id);
        Ok(())
    }).map_err(|e| format!("OpenFill generated layer could not be added: {e}"))
}

/// Determine the required result shape and reject stale documents in the UI
/// before irreversible canvas edits or insertion.
pub fn validate_live(session: &Session, draft: &JobDraft)
    -> Result<(), String>
{
    let current = if draft.operation == Operation::Create { None }
        else { ai_background_editor::current_revision(session).map(|v|
            DocVersion { document: v.document, revision: v.revision }) };
    draft.validate_result(true, current, draft.output, draft.output.rgba_len()
        .map_err(str::to_owned)?).map_err(str::to_owned)?;
    Ok(())
}
