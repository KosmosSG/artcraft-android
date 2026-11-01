//! Android-only, opt-in read-only PhotoCraft Companion metadata catalog.
//!
//! Unlike the editor's file picker, Companion SAF events never enter the
//! document inbox. This module cannot execute plugin commands, load model
//! weights, or open arbitrary network/listener endpoints.
use super::AndroidFileBridge;
use jni::{
    jni_sig, jni_str,
    objects::{JObject, JString, JValue},
};
use serde_json::Value;
use std::time::Duration;

const MAX_METADATA_JSON_BYTES: usize = 16 * 1024;
const MAX_CATALOG_ENTRIES: usize = 24;

#[derive(Default)]
pub(super) struct CompanionCatalog {
    open: bool,
    entries: Vec<CatalogEntry>,
    initialized: bool,
    pending: Option<u64>,
    next_id: u64,
    status: String,
}

struct CatalogEntry {
    name: String,
    id: String,
    version: String,
    kind: String,
}

impl AndroidFileBridge {
    fn companion_request(&self, id: u64) -> Result<(), String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<()> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                env.call_method(
                    &*activity,
                    jni_str!("pcRequestCompanionPlugin"),
                    jni_sig!("(J)V"),
                    &[JValue::Long(id as i64)],
                )?;
                Ok(())
            })
            .map_err(|error| format!("Android Companion picker unavailable: {error}"))
    }

    fn companion_poll(&self) -> Result<Option<String>, String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let value = env
                    .call_method(
                        &*activity,
                        jni_str!("pcCompanionPollResult"),
                        jni_sig!("()Ljava/lang/String;"),
                        &[],
                    )?
                    .l()?;
                if value.is_null() {
                    return Ok(None);
                }
                let value = JString::cast_local(env, value)?;
                Ok(Some(value.try_to_string(env)?))
            })
            .map_err(|error| format!("Could not read Companion picker status: {error}"))
    }

    fn companion_snapshot(&self) -> Result<String, String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<String> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let value = env
                    .call_method(
                        &*activity,
                        jni_str!("pcCompanionCatalogSnapshot"),
                        jni_sig!("()Ljava/lang/String;"),
                        &[],
                    )?
                    .l()?;
                let value = JString::cast_local(env, value)?;
                value.try_to_string(env)
            })
            .map_err(|error| format!("Could not load Companion catalog metadata: {error}"))
    }
}

fn safe_text(value: &Value, key: &str, max: usize) -> Option<String> {
    let text = value.get(key)?.as_str()?;
    (!text.is_empty() && text.len() <= max && !text.chars().any(char::is_control))
        .then(|| text.to_owned())
}

fn parse_metadata(snapshot: &str) -> Result<Vec<CatalogEntry>, &'static str> {
    if snapshot.len() > MAX_METADATA_JSON_BYTES {
        return Err("Saved Companion catalog metadata is too large");
    }
    let value: Value =
        serde_json::from_str(snapshot).map_err(|_| "Saved Companion catalog metadata is invalid")?;
    let array = value
        .as_array()
        .ok_or("Saved Companion catalog is not a list")?;
    if array.len() > MAX_CATALOG_ENTRIES {
        return Err("Too many saved Companion plugin summaries");
    }
    let mut entries = Vec::with_capacity(array.len());
    let mut seen = std::collections::HashSet::new();
    for item in array {
        if item.get("catalog_status").and_then(Value::as_str) != Some("metadata_only") {
            return Err("Companion catalog contains an executable entry");
        }
        let id = safe_text(item, "id", 128).ok_or("Invalid Companion plugin ID")?;
        if !seen.insert(id.clone()) {
            return Err("Duplicate saved Companion plugin ID");
        }
        let name = safe_text(item, "name", 120).ok_or("Invalid Companion plugin name")?;
        let version = safe_text(item, "version", 48).ok_or("Invalid Companion plugin version")?;
        let kind = safe_text(item, "plugin_type", 48).ok_or("Invalid Companion plugin type")?;
        entries.push(CatalogEntry {
            name,
            id,
            version,
            kind,
        });
    }
    Ok(entries)
}

impl CompanionCatalog {
    fn load_snapshot(&mut self, bridge: &AndroidFileBridge) {
        match bridge.companion_snapshot() {
            Ok(raw) => match parse_metadata(&raw) {
                Ok(entries) => {
                    self.entries = entries;
                    self.status = format!(
                        "{} plugin descriptor(s) available (metadata only)",
                        self.entries.len()
                    );
                }
                Err(error) => {
                    self.entries.clear();
                    self.status = error.into();
                }
            },
            Err(error) => {
                self.entries.clear();
                self.status = error;
            }
        }
    }

    pub(super) fn poll(&mut self, bridge: &AndroidFileBridge, ctx: &egui::Context) {
        if !self.initialized {
            self.initialized = true;
            self.load_snapshot(bridge);
        }
        for _ in 0..8 {
            let raw = match bridge.companion_poll() {
                Ok(Some(raw)) => raw,
                Ok(None) => break,
                Err(error) => {
                    self.pending = None;
                    self.status = error;
                    break;
                }
            };
            if raw.len() > 4096 {
                self.status = "Oversized Companion picker response rejected".into();
                self.pending = None;
                break;
            }
            let Ok(value) = serde_json::from_str::<Value>(&raw) else {
                self.status = "Malformed Companion picker response rejected".into();
                self.pending = None;
                break;
            };
            if value.get("kind").and_then(Value::as_str) != Some("companion")
                || value.get("id").and_then(Value::as_u64) != self.pending
            {
                continue; // Never accept an unrelated or stale request result.
            }
            self.pending = None;
            match value.get("status").and_then(Value::as_str) {
                Some("ok") => {
                    // Reload only Java's validated, persistently stored metadata.
                    self.load_snapshot(bridge);
                    self.status = "Plugin metadata added. Execution remains disabled.".into();
                }
                Some("cancel") => self.status = "Plugin selection cancelled.".into(),
                _ => {
                    self.status = "Plugin rejected; catalog unchanged.".into();
                }
            }
            ctx.request_repaint();
        }
        if self.pending.is_some() {
            ctx.request_repaint_after(Duration::from_millis(250));
        }
    }

    pub(super) fn show(&mut self, ctx: &egui::Context, bridge: &AndroidFileBridge) {
        // Small, explicitly tapped entry point separate from File > Open and shortcuts.
        // Right-bottom placement avoids the established top menu and contextual text strip.
        egui::Area::new(egui::Id::new("photocraft_companion_catalog_button"))
            .order(egui::Order::Foreground)
            .anchor(egui::Align2::RIGHT_BOTTOM, egui::vec2(-18.0, -18.0))
            .show(ctx, |ui| {
                egui::Frame::default().show(ui, |ui| {
                    if ui.button("Plugins · Preview").clicked() {
                        self.open = !self.open;
                    }
                });
            });

        if !self.open {
            return;
        }
        let mut open = self.open;
        egui::Window::new("Companion plugins · Read-only preview")
            .id(egui::Id::new("photocraft_companion_catalog_window"))
            .open(&mut open)
            .default_width(380.0)
            .resizable(true)
            .show(ctx, |ui| {
                ui.label("PhotoCraft Companion package catalog");
                ui.small("Metadata only. No plugins can run or change your document.");
                ui.separator();
                let import = ui.add_enabled(
                    self.pending.is_none(),
                    egui::Button::new("Import .pcpl descriptor (SAF)"),
                );
                if import.clicked() {
                    self.next_id = self.next_id.wrapping_add(1).max(1);
                    match bridge.companion_request(self.next_id) {
                        Ok(()) => {
                            self.pending = Some(self.next_id);
                            self.status = "Choose one .pcpl file in Android Documents.".into();
                        }
                        Err(error) => self.status = error,
                    }
                }
                if self.pending.is_some() {
                    ui.spinner();
                    ui.label("Waiting for Android document picker...");
                }
                if ui.button("Refresh catalog").clicked() {
                    self.load_snapshot(bridge);
                }
                ui.label(&self.status);
                ui.separator();
                if self.entries.is_empty() {
                    ui.label("No validated plugin descriptors in the catalog.");
                }
                egui::ScrollArea::vertical()
                    .max_height(360.0)
                    .show(ui, |ui| {
                        for entry in &self.entries {
                            ui.group(|ui| {
                                ui.label(&entry.name);
                                ui.small(format!(
                                    "{} · {} · {}",
                                    entry.id, entry.kind, entry.version
                                ));
                                ui.small("Not installed · execution disabled");
                            });
                        }
                    });
                ui.separator();
                ui.small("No marketplace, scripts, model downloads or plugin commands.");
            });
        self.open = open;
    }
}
