//! Opt-in PhotoCraft AI preview: immutable document snapshot -> PNG -> verified
//! raster layer -> one undoable Session history transaction.
//!
//! No editor mutation occurs on the worker thread. Re-validate both document
//! identity and revision on the UI thread before committing the result.
use std::sync::Arc;
use photocraft_doc::{ColorMode, Document, Layer, LayerContent, SampleType};
use photocraft_engine::Session;
use crate::ai_background_job::DocumentRevision;
use crate::ai_output_validation::{validate_alpha_png, ImageShape};
use crate::ai_u2netp_transport::{MAX_INPUT, MAX_OUTPUT};

pub const MAX_PIXELS: u64 = 4_000_000;

pub fn active_snapshot(session: &Session) -> Result<(Arc<Document>, DocumentRevision), String> {
    let state = session.active().ok_or("Open a PhotoCraft document first")?;
    check_document(&state.doc)?;
    Ok((Arc::clone(&state.doc), DocumentRevision {
        document: state.doc.id.0,
        revision: state.revision,
    }))
}

pub fn current_revision(session: &Session) -> Option<DocumentRevision> {
    session.active().map(|state| DocumentRevision {
        document: state.doc.id.0,
        revision: state.revision,
    })
}

fn check_document(doc: &Document) -> Result<(), String> {
    if doc.size.width == 0 || doc.size.height == 0 ||
        u64::from(doc.size.width) * u64::from(doc.size.height) > MAX_PIXELS {
        return Err("This preview supports images of up to 4 million pixels".into());
    }
    // Preserve other colour spaces and deep-colour images until a deliberate
    // conversion implementation is tested; never insert mismatched raster data.
    if doc.mode != ColorMode::Rgb || doc.depth != SampleType::U8 {
        return Err("This preview currently supports RGB 8-bit documents only".into());
    }
    Ok(())
}

/// Runs on a worker thread on an immutable cloned document.
pub fn capture_png(doc: &Document) -> Result<Vec<u8>, String> {
    check_document(doc)?;
    let options = photocraft_io::ExportOptions {
        xmp: photocraft_io::XmpEmbed::None,
        ..Default::default()
    };
    let result = photocraft_io::export(doc, "ai-preview-input.png", &options)
        .map_err(|_| "Could not render active document to PNG")?;
    if result.bytes.is_empty() || result.bytes.len() > MAX_INPUT ||
        !result.bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        return Err("Rendered PNG exceeds the local processing limit".into());
    }
    Ok(result.bytes)
}

/// Full PNG decoder and trusted-layer constructor. Header-only validation is
/// never sufficient: PhotoCraft's normal PNG importer must decode the pixels.
pub fn decode_layer(output: &[u8], source: &Document) -> Result<Layer, String> {
    check_document(source)?;
    if output.len() > MAX_OUTPUT {
        return Err("U2NetP output exceeds the local processing limit".into());
    }
    validate_alpha_png(output, ImageShape {
        width: source.size.width,
        height: source.size.height,
    }).map_err(str::to_owned)?;
    let imported = photocraft_io::import("ai-preview-result.png", output)
        .map_err(|_| "U2NetP result failed full PNG decoding")?;
    let result = imported.document;
    if result.size != source.size || result.mode != ColorMode::Rgb ||
        result.depth != SampleType::U8 || result.layers.len() != 1 {
        return Err("U2NetP result does not match the source document".into());
    }
    let layer = result.layers.into_iter().next()
        .ok_or("U2NetP produced an empty document")?;
    let surface = match layer.content {
        LayerContent::Raster(surface) => surface,
        _ => return Err("U2NetP output is not a pixel layer".into()),
    };
    // Construct a clean, unlocked new layer; do not inherit imported layer
    // locks, background traits, names, metadata or save identity.
    Ok(Layer::new("AI · Background Removed", LayerContent::Raster(surface)))
}

/// Called on the UI thread only, after the worker completes. Session::edit
/// records one undoable history step and restores via standard Undo/Redo.
pub fn insert_undoable(
    session: &mut Session,
    expected: DocumentRevision,
    layer: Layer,
) -> Result<(), String> {
    if current_revision(session) != Some(expected) {
        return Err("Document changed while processing; AI result was discarded".into());
    }
    session.edit("AI · Remove Background", |doc, active| {
        let id = doc.insert_above(*active, layer);
        *active = Some(id);
        Ok(())
    }).map_err(|error| format!("Could not insert AI layer: {error}"))
}
