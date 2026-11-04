//! PDFCraft Android-only, docked controls. Kept separate from the upstream PDF engine.
//! File-import and update actions are handled by Android's Java Activity; no auto installation.
use android_activity::AndroidApp;
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JString, JValue}};
use serde_json::Value;

#[derive(Clone, Copy)]
enum Action { ImportFont, SelectFolder, RefreshFonts, CheckUpdates }

pub struct Mobile {
    app: AndroidApp,
    renderer: String,
    panel_open: bool,
    fonts_open: bool,
    gpu_details_open: bool,
    trackpad_details_open: bool,
    trackpad_scroll_events: u64,
    trackpad_zoom_events: u64,
    trackpad_last_native: String,
    trackpad_java_status: String,
    trackpad_last_poll: Option<std::time::Instant>,
    updates_open: bool,
    toolbar_shown: bool,
    font_status: String,
    update_status: String,
    update_url: Option<String>,
    checking: bool,
    startup_check: bool,
    first_frame: bool,
}

impl Mobile {
    pub fn new(app: AndroidApp) -> Self {
        let mut mobile = Self {
            app, renderer: "Renderer not initialized".into(), panel_open: false, fonts_open: false, gpu_details_open: false,
            trackpad_details_open: false, trackpad_scroll_events: 0, trackpad_zoom_events: 0,
            trackpad_last_native: "No egui scroll/zoom events yet".into(),
            trackpad_java_status: "No Java input diagnostic sample yet".into(),
            trackpad_last_poll: None, updates_open: false, toolbar_shown: false,
            font_status: "PDF text fonts: none imported this session".into(),
            update_status: "No update check has run yet".into(),
            update_url: None, checking: false, startup_check: false, first_frame: true,
        };
        mobile.startup_check = mobile.read_startup_setting().unwrap_or(false);
        mobile.toolbar_shown = mobile.read_toolbar_setting().unwrap_or(false);
        mobile
    }

    fn read_startup_setting(&self) -> Result<bool, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfStartupUpdateEnabled"),
                jni_sig!("()Z"), &[])?.z()
        }).map_err(|err| err.to_string())
    }
    fn save_startup_setting(&self, enabled: bool) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfSetStartupUpdateEnabled"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|err| err.to_string())
    }
    pub fn toolbar_shown(&self) -> bool { self.toolbar_shown }

    fn read_toolbar_setting(&self) -> Result<bool, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfToolbarVisible"),
                jni_sig!("()Z"), &[])?.z()
        }).map_err(|err| err.to_string())
    }

    fn save_toolbar_setting(&self, visible: bool) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfSetToolbarVisible"),
                jni_sig!("(Z)V"), &[JValue::Bool(visible)])?;
            Ok(())
        }).map_err(|err| err.to_string())
    }

    /// One Java preference write per actual change, never a JNI call every frame.
    pub fn sync_toolbar_preference(&mut self, visible: bool) {
        if visible != self.toolbar_shown {
            if let Err(error) = self.save_toolbar_setting(visible) {
                self.font_status = format!("Toolbar preference not saved: {error}");
            }
            self.toolbar_shown = visible;
        }
    }

    fn request(&self, action: Action) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            match action {
                Action::ImportFont => {
                    env.call_method(&*activity, jni_str!("pdfRequestFont"), jni_sig!("()V"), &[])?;
                }
                Action::SelectFolder => {
                    env.call_method(&*activity, jni_str!("pdfRequestFontFolder"), jni_sig!("()V"), &[])?;
                }
                Action::RefreshFonts => {
                    env.call_method(&*activity, jni_str!("pdfRefreshFontFolder"), jni_sig!("()V"), &[])?;
                }
                Action::CheckUpdates => {
                    env.call_method(&*activity, jni_str!("pdfCheckForUpdates"), jni_sig!("()V"), &[])?;
                }
            }
            Ok(())
        }).map_err(|err| err.to_string())
    }
    fn poll_java(&self, updates: bool) -> Result<Option<String>, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let v = if updates {
                env.call_method(&*activity, jni_str!("pdfUpdatePoll"),
                    jni_sig!("()Ljava/lang/String;"), &[])?.l()?
            } else {
                env.call_method(&*activity, jni_str!("pdfFontPoll"),
                    jni_sig!("()Ljava/lang/String;"), &[])?.l()?
            };
            if v.is_null() { return Ok(None); }
            let s = JString::cast_local(env, v)?;
            Ok(Some(s.try_to_string(env)?))
        }).map_err(|err| err.to_string())
    }
    fn release_page(&self, url: &str) -> Result<(), String> {
        if !url.starts_with("https://github.com/KosmosSG/artcraft-android/releases/tag/pdfcraft-v") {
            return Err("Release page is not an approved PDFCraft Android release".into());
        }
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let address = JObject::from(env.new_string(url)?);
            env.call_method(&*activity, jni_str!("pdfOpenReleasePage"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&address)])?;
            Ok(())
        }).map_err(|err| err.to_string())
    }
    pub fn do_update_check(&mut self) {
        if self.checking { return; }
        self.update_url = None;
        self.update_status = "Checking published PDFCraft Android releases…".into();
        self.updates_open = true;
        self.panel_open = true;
        match self.request(Action::CheckUpdates) {
            Ok(()) => self.checking = true,
            Err(error) => self.update_status = format!("Update checker unavailable: {error}"),
        }
    }
    pub fn poll(&mut self, ctx: &egui::Context) {
        if self.trackpad_details_open {
            let due = self.trackpad_last_poll.is_none_or(|last| {
                last.elapsed() >= std::time::Duration::from_millis(500)
            });
            if due {
                self.trackpad_last_poll = Some(std::time::Instant::now());
                self.trackpad_java_status = self.read_trackpad_status()
                    .unwrap_or_else(|error| format!("Java diagnostics: {error}"));
            }
            ctx.request_repaint_after(std::time::Duration::from_millis(500));
        }
        if self.first_frame {
            self.first_frame = false;
            if self.startup_check { self.do_update_check(); }
        }
        for _ in 0..8 {
            match self.poll_java(false) {
                Ok(Some(payload)) => {
                    self.font_status = serde_json::from_str::<Value>(&payload).ok()
                        .and_then(|v| v.get("message").and_then(Value::as_str).map(str::to_owned))
                        .unwrap_or_else(|| "Unrecognized font result".to_owned());
                    ctx.request_repaint();
                }
                Ok(None) => break,
                Err(error) => { self.font_status = format!("Font bridge: {error}"); break; }
            }
        }
        if self.checking {
            match self.poll_java(true) {
                Ok(Some(payload)) => {
                    self.checking = false;
                    if let Ok(response) = serde_json::from_str::<Value>(&payload) {
                        self.update_status = response.get("message").and_then(Value::as_str)
                            .unwrap_or("Invalid GitHub release response").into();
                        self.update_url = response.get("url").and_then(Value::as_str)
                            .filter(|u| u.starts_with(
                                "https://github.com/KosmosSG/artcraft-android/releases/tag/pdfcraft-v"))
                            .map(str::to_owned);
                    } else {
                        self.update_status = "Invalid update response".into();
                    }
                    ctx.request_repaint();
                }
                Ok(None) => ctx.request_repaint_after(std::time::Duration::from_millis(250)),
                Err(error) => {
                    self.checking = false;
                    self.update_status = format!("Update checker: {error}");
                }
            }
        }
    }
    // PDFCRAFT_ANDROID_EGUI_SCROLL_DIAGNOSTICS: inspect egui input before
    // the upstream canvas consumes it. Never alter, consume or delay events.
    pub fn observe_raw_input(&mut self, raw: &egui::RawInput) {
        if !self.trackpad_details_open { return; }
        for event in &raw.events {
            match event {
                egui::Event::MouseWheel { unit, delta, .. } => {
                    self.trackpad_scroll_events += 1;
                    self.trackpad_last_native = format!(
                        "egui wheel #{}: {:?}, x={:.2}, y={:.2}",
                        self.trackpad_scroll_events, unit, delta.x, delta.y);
                }
                egui::Event::Zoom(factor) => {
                    self.trackpad_zoom_events += 1;
                    self.trackpad_last_native = format!(
                        "egui zoom #{}: {:.3}x", self.trackpad_zoom_events, factor);
                }
                _ => {}
            }
        }
    }
    fn read_trackpad_status(&self) -> Result<String, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("pdfTrackpadStatus"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            let text = JString::cast_local(env, value)?;
            Ok(text.try_to_string(env)?.into())
        }).map_err(|err| err.to_string())
    }
    pub fn set_renderer(&mut self, description: String) { self.renderer = description; }
    /// Optional native View > Android tools panel. Hidden means NO egui widget
    /// is drawn above the real application menu, giving the PDF editor its space.
    /// Return true when "Hide panel" was clicked, so the shell can toggle it.
    pub fn toolbar(&mut self, parent: &mut egui::Ui) -> bool {
        let mut hide_requested = false;
        // The root PDFCraft window is transparent on Android. A plain egui group
        // draws NO background: dark native surface shows through behind black text
        // when upstream PDFCraft switches to the light theme. Paint the panel with
        // the same live palette as the built-in File/View chrome on every frame.
        let available_width = parent.available_width();
        egui::Frame::group(parent.style())
            .fill(parent.visuals().panel_fill)
            .show(parent, |ui| {
            // Cover the full width, not just the buttons, so the remaining strip
            // is also light in light mode and dark in dark mode.
            ui.set_min_width((available_width - 14.0).max(0.0));
            ui.horizontal_wrapped(|ui| {
                ui.strong("Fonts:");
                if ui.button("Import Font…")
                    .on_hover_text("Choose an individual .ttf or .otf font").clicked() {
                    self.font_status = "Choose a .ttf or .otf font…".into();
                    if let Err(error) = self.request(Action::ImportFont) { self.font_status = error; }
                }
                if ui.button("Choose Shared Font Folder…")
                    .on_hover_text("Select ArtCraft-Fonts; nested folders are included").clicked() {
                    self.font_status = "Choose your shared Android font folder…".into();
                    if let Err(error) = self.request(Action::SelectFolder) { self.font_status = error; }
                }
                if ui.button("Refresh Font Folder")
                    .on_hover_text("Rescan the previously selected shared folder (4 GiB / 5,000 fonts)").clicked() {
                    self.font_status = "Refreshing previously selected folder…".into();
                    if let Err(error) = self.request(Action::RefreshFonts) { self.font_status = error; }
                }
                ui.separator();
                if ui.button("Check updates").clicked() { self.do_update_check(); }
                if ui.button("GPU info").on_hover_text("Show actual Android wgpu adapter and graphics backend").clicked() {
                    self.gpu_details_open = !self.gpu_details_open;
                }
                ui.separator();
                if ui.button("Hide panel").on_hover_text(
                    "Reopen from View > Android tools panel").clicked() {
                    hide_requested = true;
                }
            });
            // Keep import/scan feedback on screen without hiding the actual actions.
            ui.label(&self.font_status).on_hover_text(
                "PDFCraft accepts embeddable TTF/OTF fonts; existing embedded PDF fonts are unchanged.");
            if self.gpu_details_open {
                ui.separator();
                ui.label(&self.renderer).on_hover_text(
                    "Android GPU adapter information from wgpu at startup. PDF page rasterization is performed by hayro on CPU; the page textures and interface are composited by wgpu. Software/unknown adapters do not prove hardware acceleration.");
            }
            if self.updates_open {
                ui.separator();
                ui.horizontal_wrapped(|ui| {
                    ui.label(&self.update_status);
                    if self.checking { ui.spinner(); }
                    if let Some(url) = self.update_url.clone() {
                        if ui.button("View GitHub release").clicked() {
                            if let Err(error) = self.release_page(&url) { self.update_status = error; }
                        }
                    }
                    if ui.button("Hide update status").clicked() { self.updates_open = false; }
                });
                if ui.checkbox(&mut self.startup_check, "Check for PDFCraft Android updates at startup").changed() {
                    if let Err(error) = self.save_startup_setting(self.startup_check) {
                        self.update_status = format!("Could not save startup preference: {error}");
                    }
                }
                ui.label(egui::RichText::new("Checks only published PDFCraft Android APKs; never installs automatically.").small());
            }
        });
        hide_requested
    }
    pub fn handle_menu(&mut self, action: u8) {
        match action {
            4 => {
                self.panel_open = true;
                self.fonts_open = false;
                self.do_update_check();
                return;
            }
            5 => {
                self.panel_open = true;
                self.fonts_open = false;
                self.updates_open = true;
                return;
            }
            6 => {
                self.panel_open = true;
                self.gpu_details_open = true;
                return;
            }
            7 => {
                self.panel_open = true;
                return;
            }
            8 => {
                self.panel_open = true;
                self.fonts_open = false;
                self.trackpad_details_open = true;
                self.trackpad_last_poll = None;
                return;
            }
            _ => {}
        }
        let request = match action {
            1 => Some(Action::ImportFont),
            2 => Some(Action::SelectFolder),
            3 => Some(Action::RefreshFonts),
            4 => None,
            _ => return,
        };
        self.panel_open = true;
        self.fonts_open = true;
        self.updates_open = action == 4;
        if let Some(request) = request {
            self.font_status = "Waiting for font action…".into();
            if let Err(error) = self.request(request) { self.font_status = error; }
        }
    }
    pub fn dialog(&mut self, ctx: &egui::Context) {
        if !self.panel_open { return; }
        let mut open = self.panel_open;
        egui::Window::new("Android tools").open(&mut open)
            .default_width(520.0).resizable(true).vscroll(true).show(ctx, |ui| {
            ui.horizontal_wrapped(|ui| {
                if ui.button(if self.fonts_open { "Fonts ▴" } else { "Fonts ▾" }).clicked() {
                    self.fonts_open = !self.fonts_open;
                }
                if ui.button("Check updates").clicked() { self.do_update_check(); }
                ui.separator();
                ui.label("PDFCraft Android • document fonts and releases").on_hover_text(&self.renderer);
            });
            if self.gpu_details_open {
                ui.separator();
                ui.label(&self.renderer);
                if ui.button("Hide GPU diagnostics").clicked() { self.gpu_details_open = false; }
            }
            if self.trackpad_details_open {
                ui.separator();
                ui.heading("Trackpad diagnostics");
                ui.label("While this window is open, try two-finger scrolling on the physical trackpad.");
                ui.label(format!("egui scroll events received: {}", self.trackpad_scroll_events));
                ui.label(format!("egui pinch/zoom events received: {}", self.trackpad_zoom_events));
                ui.monospace(&self.trackpad_last_native);
                match serde_json::from_str::<Value>(&self.trackpad_java_status) {
                    Ok(data) => {
                        ui.label(format!(
                            "Java generic motion events: {}",
                            data.get("javaEvents").and_then(Value::as_u64).unwrap_or(0)));
                        ui.label(format!(
                            "Android 14+ gesture-axis events: {}",
                            data.get("gestureAxes").and_then(Value::as_u64).unwrap_or(0)));
                        ui.label(format!(
                            "Legacy wheel-axis events: {}",
                            data.get("legacyAxes").and_then(Value::as_u64).unwrap_or(0)));
                        ui.monospace(data.get("last").and_then(Value::as_str)
                            .unwrap_or("No Java sample"));
                        ui.separator();
                        ui.heading("Adaptive cursor diagnostics");
                        ui.label(format!("Android cursor requests: {}",
                            data.get("cursorRequests").and_then(Value::as_u64).unwrap_or(0)));
                        ui.label(format!("Android cursor applied: {}",
                            data.get("cursorApplied").and_then(Value::as_u64).unwrap_or(0)));
                        let kind = data.get("cursorType").and_then(Value::as_i64).unwrap_or(-1);
                        let label = match kind {
                            1000 => "Default arrow", 1002 => "Pointing hand",
                            1008 => "Text I-beam", 1007 => "Crosshair",
                            1014 | 1021 | 1022 | 1023 => "Resize arrow",
                            -1 => "No cursor request received", _ => "Other native cursor",
                        };
                        ui.label(format!("Last requested cursor: {} ({})", label, kind));
                        ui.label(format!("Target Android view: {}",
                            data.get("cursorTarget").and_then(Value::as_str).unwrap_or("Unknown")));
                        let err = data.get("cursorError").and_then(Value::as_str).unwrap_or("None");
                        if err != "None" { ui.colored_label(egui::Color32::RED, err); }
                        ui.label(egui::RichText::new(
                            "Hover over PDFCraft buttons, then move into editable text. If requests stay at zero, egui's cursor bridge was not called. If requests rise but applied stays zero, the Android view/JNI bridge failed. If both rise but the cursor stays an arrow, the Android system may ignore the selected SurfaceView pointer icon."
                        ).small());
                    }
                    Err(_) => { ui.monospace(&self.trackpad_java_status); }
                }
                ui.label(egui::RichText::new(
                    "Java counters only see events delivered through the Activity. NativeActivity may route others directly to its native input queue. The egui counters show events actually delivered to the editor. Zero Java events alone is inconclusive."
                ).small());
                ui.label(egui::RichText::new(
                    "Try a two-finger gesture over the document, then compare both counters and send a screenshot. Diagnostics are local to this session; no data is uploaded."
                ).small());
                if ui.button("Hide trackpad diagnostics").clicked() {
                    self.trackpad_details_open = false;
                }
            }
            if self.fonts_open {
                ui.separator();
                ui.horizontal_wrapped(|ui| {
                    if ui.button("Import TTF/OTF").clicked() {
                        self.font_status = "Choose a .ttf or .otf font…".into();
                        if let Err(error) = self.request(Action::ImportFont) { self.font_status = error; }
                    }
                    if ui.button("Select shared ArtCraft-Fonts folder").clicked() {
                        self.font_status = "Choose your shared Android font directory…".into();
                        if let Err(error) = self.request(Action::SelectFolder) { self.font_status = error; }
                    }
                    if ui.button("Refresh shared folder").clicked() {
                        self.font_status = "Refreshing previously selected folder…".into();
                        if let Err(error) = self.request(Action::RefreshFonts) { self.font_status = error; }
                    }
                });
                ui.label(&self.font_status);
                ui.label(egui::RichText::new("Only embeddable fonts accepted by PDFCraft are available for PDF text tools; existing embedded fonts are unchanged.").small());
            }
            if self.updates_open {
                ui.separator();
                ui.horizontal_wrapped(|ui| {
                    ui.label(&self.update_status);
                    if self.checking { ui.spinner(); }
                    if let Some(url) = self.update_url.clone() {
                        if ui.button("View GitHub release").clicked() {
                            if let Err(error) = self.release_page(&url) { self.update_status = error; }
                        }
                    }
                    if ui.button("Hide").clicked() { self.updates_open = false; }
                });
                if ui.checkbox(&mut self.startup_check, "Check for PDFCraft Android updates at startup").changed() {
                    if let Err(error) = self.save_startup_setting(self.startup_check) {
                        self.update_status = format!("Could not save startup preference: {error}");
                    }
                }
                ui.label(egui::RichText::new("Checks only published PDFCraft Android APKs; never installs automatically.").small());
            }
        });
        self.panel_open = open;
    }
}
