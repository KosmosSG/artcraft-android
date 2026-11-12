//! PDFCraft Android-only, docked controls. Kept separate from the upstream PDF engine.
//! File-import and update actions are handled by Android's Java Activity; no auto installation.
use android_activity::AndroidApp;
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JString, JValue}};
use serde_json::Value;

#[derive(Clone, Copy)]
enum Action { ImportFont, SelectFolder, RefreshFonts, CheckUpdates { manual: bool } }

pub struct Mobile {
    app: AndroidApp,
    wheel: crate::pdfcraft_stylus_wheel::Wheel,
    wheel_scan: std::time::Instant,
    renderer: String,
    panel_open: bool,
    fonts_open: bool,
    gpu_details_open: bool,
    trackpad_details_open: bool,
    performance_enabled: bool,
    perf_last_frame: Option<std::time::Instant>,
    perf_frame_count: u64,
    perf_mean_ms: f64,
    perf_m2_ms: f64,
    perf_last_ms: f64,
    perf_ui_ms: f64,
    perf_slow_frames: u64,
    trackpad_scroll_events: u64,
    trackpad_zoom_events: u64,
    trackpad_last_native: String,
    trackpad_java_status: String,
    trackpad_last_poll: Option<std::time::Instant>,
    updates_open: bool,
    about_open: bool,
    // Retrieved from the Android PackageManager, never hardcoded to a release.
    installed_version: String,
    installed_package: String,
    toolbar_shown: bool,
    font_status: String,
    update_status: String,
    update_url: Option<String>,
    update_asset_url: Option<String>,
    update_digest: String,
    downloading: bool,
    download_ready: bool,
    checking: bool,
    startup_check: bool,
    first_frame: bool,
}

impl Mobile {
    pub fn new(app: AndroidApp) -> Self {
        let mut mobile = Self {
            wheel: crate::pdfcraft_stylus_wheel::Wheel::new(false), wheel_scan: std::time::Instant::now(),
            app, renderer: "Renderer not initialized".into(), panel_open: false, fonts_open: false, gpu_details_open: false,
            trackpad_details_open: false, performance_enabled: false,
            perf_last_frame: None, perf_frame_count: 0, perf_mean_ms: 0.0,
            perf_m2_ms: 0.0, perf_last_ms: 0.0, perf_ui_ms: 0.0, perf_slow_frames: 0,
            trackpad_scroll_events: 0, trackpad_zoom_events: 0,
            trackpad_last_native: "No egui scroll/zoom events yet".into(),
            trackpad_java_status: "No Java input diagnostic sample yet".into(),
            trackpad_last_poll: None, updates_open: false, about_open: false, toolbar_shown: false,
            installed_version: "Unavailable".into(), installed_package: "unavailable".into(),
            font_status: "PDF text fonts: none imported this session".into(),
            update_status: "No update check has run yet".into(),
            update_url: None, update_asset_url: None, update_digest: String::new(),
            downloading: false, download_ready: false, checking: false, startup_check: true, first_frame: true,
        };
        mobile.startup_check = mobile.read_startup_setting().unwrap_or(true);
        mobile.toolbar_shown = mobile.read_toolbar_setting().unwrap_or(false);
        if let Ok((version, package)) = mobile.read_installed_build_info() {
            mobile.installed_version = version;
            mobile.installed_package = package;
        }
        let enabled = mobile.pdf_stylus_enabled().unwrap_or(false);
        mobile.wheel = crate::pdfcraft_stylus_wheel::Wheel::new(enabled);
        if let Ok(layout) = mobile.pdf_stylus_get_layout() { mobile.wheel.set_layout_string(&layout); }
        android_activity::pdf_stylus_configure(enabled, &mobile.pdf_stylus_device_ids().unwrap_or_default());
        mobile
    }

    fn pdf_stylus_get_layout(&self) -> Result<String, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pdfStylusGetLayout"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(String::new()); }
            let value = JString::cast_local(env, result)?;
            value.try_to_string(env)
        }).map_err(|e| e.to_string())
    }
    fn pdf_stylus_set_layout(&self, layout: &str) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.new_string(layout)?;
            let object = JObject::from(value);
            env.call_method(&*activity, jni_str!("pdfStylusSetLayout"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&object)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
    fn pdf_stylus_set_enabled(&self, enabled: bool) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfStylusSetEnabled"), jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
    fn pdf_stylus_enabled(&self) -> Result<bool, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfStylusEnabled"), jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| e.to_string())
    }
    fn pdf_stylus_poll(&self) -> Result<Option<String>, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pdfStylusPoll"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }
    fn pdf_stylus_device_ids(&self) -> Result<Vec<i32>, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<Vec<i32>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("pdfStylusDeviceIds"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if value.is_null() { return Ok(Vec::new()); }
            let value = JString::cast_local(env, value)?;
            let ids: String = value.try_to_string(env)?;
            Ok(ids.split(',').filter_map(|s| s.parse::<i32>().ok()).collect())
        }).map_err(|e| e.to_string())
    }
    // The MagicPad window can have focus before winit's initial egui focus
    // event (which on some devices only arrives after the first pen contact).
    // Query the Android Activity instead of gating pre-contact hover on raw.focused.
    fn pdf_stylus_window_focused(&self) -> Result<bool, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfStylusWindowFocused"),
                jni_sig!("()Z"), &[])?.z()
        }).map_err(|error| error.to_string())
    }
    fn pen_hover(&self, ctx: &egui::Context) -> Option<egui::Pos2> {
        if let Some((x, y)) = android_activity::pdf_stylus_native_hover() {
            return Some(egui::pos2(x, y) / ctx.pixels_per_point());
        }
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let value = vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("pdfStylusHover"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            JString::cast_local(env, value)?.try_to_string(env)
        }).ok()?;
        let (x, y) = value.split_once(',')?;
        let x = x.parse::<f32>().ok()? / ctx.pixels_per_point();
        let y = y.parse::<f32>().ok()? / ctx.pixels_per_point();
        if x.is_finite() && y.is_finite() { Some(egui::pos2(x,y)) } else { None }
    }
    pub fn wheel_input(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput, blocked: bool) {
        if self.wheel_scan.elapsed() > std::time::Duration::from_secs(2) {
            android_activity::pdf_stylus_configure(self.wheel.enabled, &self.pdf_stylus_device_ids().unwrap_or_default());
            self.wheel_scan = std::time::Instant::now();
        }
        // Use Activity window focus: egui/winit may report false until the
        // first stylus tap even when the Android window is already interactive.
        let focused = self.pdf_stylus_window_focused().unwrap_or(raw.focused);
        if !focused { android_activity::pdf_stylus_clear_hover(); }
        // Keep polling while popups and the customizer are open; those UI
        // states used to stop redraws and made hover appear only on contact.
        if self.wheel.enabled && focused {
            ctx.request_repaint_after(std::time::Duration::from_millis(45));
        }
        self.wheel.set_pen_hover(if focused { self.pen_hover(ctx) } else { None });
        let blocked = blocked || self.panel_open || self.fonts_open || self.updates_open || self.about_open;
        for code in android_activity::pdf_stylus_native_take() {
            if !blocked { self.wheel.signal(if code == 19 { "D" } else { "S" }, ctx); }
        }
        for _ in 0..12 {
            match self.pdf_stylus_poll() {
                Ok(Some(signal)) => if !blocked { self.wheel.signal(&signal, ctx); },
                _ => break,
            }
        }
        self.wheel.capture(ctx, raw, blocked);

        // NativeActivity receives stylus HOVER_MOVE even when winit does not
        // produce egui PointerMoved. egui menus must receive the same location
        // as the custom wheel, in *points* rather than Android physical pixels.
        // Append after winit events so a stale mouse move cannot overwrite it.
        // This is passive motion only: never synthesize Touch or PointerButton.
        let pen = if focused { self.pen_hover(ctx) } else { None };
        let hover_id = egui::Id::new("pdfcraft.native.pen-hover-active");
        let was_hovering = ctx.data(|d| d.get_temp::<bool>(hover_id).unwrap_or(false));
        let contacting = ctx.input(|i| i.pointer.any_down()) ||
            raw.events.iter().any(|e| matches!(e,
                egui::Event::PointerButton { pressed: true, .. } |
                egui::Event::Touch { phase: egui::TouchPhase::Start, .. }));
        if let Some(pos) = pen.filter(|p| p.x.is_finite() && p.y.is_finite()
            && ctx.content_rect().contains(*p)) {
            if !contacting {
                raw.events.push(egui::Event::PointerMoved(pos));
                ctx.data_mut(|d| d.insert_temp(hover_id, true));
                ctx.request_repaint();
            } else {
                ctx.data_mut(|d| d.insert_temp(hover_id, false));
            }
        } else {
            // Clear the hover highlight when the pen leaves. Do not interfere
            // with current real mouse/trackpad motion on the same frame.
            if was_hovering && !raw.events.iter().any(|e| matches!(e,
                egui::Event::PointerMoved(_) | egui::Event::PointerButton { .. })) {
                raw.events.push(egui::Event::PointerGone);
            }
            ctx.data_mut(|d| d.insert_temp(hover_id, false));
        }
    }
    pub fn take_wheel_action(&mut self) -> Option<&'static str> { self.wheel.take_action() }
    pub fn wheel_ui(&mut self, ui: &mut egui::Ui) {
        ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("pdfcraft.wheel.enabled"), self.wheel.enabled));
        let request = ui.ctx().data_mut(|d| d.remove_temp::<u8>(egui::Id::new("pdfcraft.wheel.request")));
        if request == Some(1) {
            let enabled = !self.wheel.enabled;
            match self.pdf_stylus_set_enabled(enabled) {
                Ok(()) => {
                    self.wheel.toggle(enabled, ui.ctx());
                    android_activity::pdf_stylus_configure(enabled, &self.pdf_stylus_device_ids().unwrap_or_default());
                },
                Err(error) => log::warn!("Cannot save stylus setting: {error}"),
            }
        }
        if request == Some(2) { self.wheel.open_customizer(ui.ctx()); }
        if !self.wheel.is_visible() && !egui::Popup::is_any_open(ui.ctx()) && !self.panel_open && !self.fonts_open && !self.updates_open && !self.about_open {
            if let Some(position) = self.pen_hover(ui.ctx()) {
                let painter = ui.ctx().layer_painter(egui::LayerId::new(egui::Order::Foreground, egui::Id::new("pdf.pen.hover")));
                painter.circle_stroke(position, 5.0, egui::Stroke::new(1.25, egui::Color32::from_rgb(251,180,176)));
                ui.ctx().request_repaint_after(std::time::Duration::from_millis(16));
            }
        }
        self.wheel.render(ui);
        if let Some(layout) = self.wheel.take_layout_change() {
            if let Err(error) = self.pdf_stylus_set_layout(&layout) { log::warn!("Cannot save wheel layout: {error}"); }
        }
    }

    fn read_installed_build_info(&self) -> Result<(String, String), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let payload = vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("pdfInstalledBuildInfo"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if value.is_null() { return Ok(String::new()); }
            JString::cast_local(env, value)?.try_to_string(env)
        }).map_err(|error| error.to_string())?;
        let info: Value = serde_json::from_str(&payload).map_err(|error| error.to_string())?;
        let version = info.get("version").and_then(Value::as_str)
            .filter(|value| !value.is_empty()).ok_or("Android version unavailable")?;
        let package = info.get("package").and_then(Value::as_str)
            .filter(|value| !value.is_empty()).ok_or("Android package unavailable")?;
        Ok((version.to_owned(), package.to_owned()))
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
                Action::CheckUpdates { manual } => {
                    env.call_method(&*activity, jni_str!("pdfCheckForUpdates"), jni_sig!("(Z)V"),
                        &[JValue::Bool(manual)])?;
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
    fn download_update(&self, asset: &str) -> Result<(), String> {
        if !asset.starts_with("https://github.com/KosmosSG/artcraft-android/releases/download/pdfcraft-v") {
            return Err("Unapproved PDFCraft APK download address".into());
        }
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let address = JObject::from(env.new_string(asset)?);
            let digest = JObject::from(env.new_string(&self.update_digest)?);
            env.call_method(&*activity, jni_str!("pdfDownloadUpdate"),
                jni_sig!("(Ljava/lang/String;Ljava/lang/String;)V"),
                &[JValue::Object(&address), JValue::Object(&digest)])?;
            Ok(())
        }).map_err(|err| err.to_string())
    }
    fn install_download(&self) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfInstallDownloadedUpdate"),
                jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|err| err.to_string())
    }
    pub fn do_update_check(&mut self) {
        self.check_updates(true);
    }
    fn check_updates(&mut self, manual: bool) {
        if self.checking || self.downloading { return; }
        self.update_url = None;
        self.update_asset_url = None;
        self.update_digest.clear();
        self.download_ready = false;
        self.update_status = "Checking published PDFCraft Android releases…".into();
        // PhotoCraft-style feedback: Java owns native Android toasts.
        // The update dialog opens only when a compatible new APK exists.
        self.updates_open = false;
        match self.request(Action::CheckUpdates { manual }) {
            Ok(()) => self.checking = true,
            Err(error) => {
                self.update_status = format!("Update checker unavailable: {error}");
                self.updates_open = true; // show an actionable error if JNI is unavailable
            }
        }
    }
    pub fn poll(&mut self, ctx: &egui::Context) {
        // PDFCRAFT_ANDROID_DECKCRAFT_APP_UPDATES: reflect persisted ON/OFF
        // in the Pc > App Updates submenu without an extra floating window.
        ctx.data_mut(|data| data.insert_temp(
            egui::Id::new("pdfcraft.android.startup.enabled"), self.startup_check));
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
            if self.startup_check { self.check_updates(false); }
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
        if self.checking || self.downloading {
            match self.poll_java(true) {
                Ok(Some(payload)) => {
                    if let Ok(response) = serde_json::from_str::<Value>(&payload) {
                        self.update_status = response.get("message").and_then(Value::as_str)
                            .unwrap_or("Invalid update response").into();
                        if response.get("kind").and_then(Value::as_str) == Some("download") {
                            self.download_ready = response.get("ready").and_then(Value::as_bool)
                                .unwrap_or(false);
                            self.downloading = !self.download_ready
                                && !self.update_status.starts_with("Cannot ")
                                && !self.update_status.starts_with("Download not ")
                                && !self.update_status.starts_with("Android Download Manager")
                                && !self.update_status.starts_with("Refused:");
                        } else {
                            self.checking = false;
                            self.update_url = response.get("url").and_then(Value::as_str)
                                .filter(|u| u.starts_with(
                                    "https://github.com/KosmosSG/artcraft-android/releases/tag/pdfcraft-v"))
                                .map(str::to_owned);
                            self.update_asset_url = response.get("asset_url").and_then(Value::as_str)
                                .filter(|u| u.starts_with(
                                    "https://github.com/KosmosSG/artcraft-android/releases/download/pdfcraft-v"))
                                .map(str::to_owned);
                            self.update_digest = response.get("digest").and_then(Value::as_str)
                                .unwrap_or("").into();
                            // A production update needs download/install controls.
                            // No-update, test-package and check errors remain
                            // bottom-center Android toasts, without a modal.
                            if self.update_asset_url.is_some() {
                                self.updates_open = true;
                            }
                        }
                    } else {
                        self.checking = false;
                        self.downloading = false;
                        self.update_status = "Invalid update response".into();
                    }
                    ctx.request_repaint();
                }
                Ok(None) => ctx.request_repaint_after(std::time::Duration::from_millis(350)),
                Err(error) => {
                    self.checking = false;
                    self.downloading = false;
                    self.update_status = format!("Update checker: {error}");
                }
            }
        }
    }
    // PDFCRAFT_ANDROID_EGUI_SCROLL_DIAGNOSTICS: inspect egui input before
    // the upstream canvas consumes it. Never alter, consume or delay events.
    pub fn observe_raw_input(&mut self, raw: &egui::RawInput) {
        if !self.performance_enabled { return; }
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
    pub fn begin_ui_sample(&mut self) -> Option<std::time::Instant> {
        if !self.performance_enabled { return None; }
        let now = std::time::Instant::now();
        if let Some(last) = self.perf_last_frame.replace(now) {
            let ms = now.duration_since(last).as_secs_f64() * 1000.0;
            // Active UI passes only: idle intervals are not dropped display frames.
            if ms < 250.0 {
                self.perf_last_ms = ms;
                self.perf_frame_count += 1;
                let d = ms - self.perf_mean_ms;
                self.perf_mean_ms += d / self.perf_frame_count as f64;
                self.perf_m2_ms += d * (ms - self.perf_mean_ms);
                if ms > 33.333 { self.perf_slow_frames += 1; }
            }
        }
        Some(now)
    }
    pub fn end_ui_sample(&mut self, start: Option<std::time::Instant>) {
        if let Some(start) = start {
            self.perf_ui_ms = start.elapsed().as_secs_f64() * 1000.0;
            egui_winit::pdfcraft_input::ui_complete();
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
                    if let Some(asset) = self.update_asset_url.clone() {
                        if !self.downloading && !self.download_ready
                            && ui.button("Download APK").clicked() {
                            match self.download_update(&asset) {
                                Ok(()) => {
                                    self.downloading = true;
                                    self.update_status = "Starting Android download…".into();
                                }
                                Err(error) => self.update_status = error,
                            }
                        }
                    }
                    if self.downloading { ui.spinner(); }
                    if self.download_ready && ui.button("Install downloaded APK…").clicked() {
                        match self.install_download() {
                            Ok(()) => {
                                self.downloading = true;
                                self.update_status = "Verifying downloaded APK…".into();
                            }
                            Err(error) => self.update_status = error,
                        }
                    }
                    if ui.button("Hide update status").clicked() { self.updates_open = false; }
                });
                if ui.checkbox(&mut self.startup_check, "Check for PDFCraft Android updates at startup").changed() {
                    if let Err(error) = self.save_startup_setting(self.startup_check) {
                        self.update_status = format!("Could not save startup preference: {error}");
                    }
                }
                ui.label(egui::RichText::new("Downloads only published PDFCraft Android APKs. Android requires explicit confirmation; test packages cannot replace stable apps.").small());
            }
        });
        hide_requested
    }
    pub fn handle_menu(&mut self, action: u8) {
        match action {
            4 => {
                self.fonts_open = false;
                self.do_update_check();
                return;
            }
            5 => {
                self.fonts_open = false;
                // DeckCraft-style immediate toggle: no modal settings dialog.
                // Keep the previously persisted OFF state across upgrades.
                let enabled = !self.startup_check;
                match self.save_startup_setting(enabled) {
                    Ok(()) => self.startup_check = enabled,
                    Err(error) => {
                        self.update_status = format!("Could not save startup preference: {error}");
                        self.updates_open = true;
                    }
                }
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
            9 => {
                self.about_open = true;
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
    fn updater_dialog(&mut self, ctx: &egui::Context) {
        let mut open = self.updates_open;
        egui::Window::new("PDFCraft updates")
            .open(&mut open)
            .default_width(380.0)
            .min_width(300.0)
            .resizable(false)
            .show(ctx, |ui| {
                let package_type = if self.installed_package == "com.artcraft.pdfcraft" {
                    "standard package"
                } else if self.installed_package.starts_with("com.artcraft.pdfcraft.") {
                    "separate test package"
                } else {
                    "package unavailable"
                };
                ui.label(format!("Installed: PDFCraft {} ({package_type})", self.installed_version));
                ui.label(&self.update_status);
                if self.checking || self.downloading { ui.spinner(); }
                ui.horizontal_wrapped(|ui| {
                    if ui.add_enabled(!self.checking && !self.downloading,
                        egui::Button::new("Check again")).clicked() {
                        self.do_update_check();
                    }
                    if let Some(url) = self.update_url.clone() {
                        if ui.button("View release").clicked() {
                            if let Err(error) = self.release_page(&url) { self.update_status = error; }
                        }
                    }
                    if let Some(asset) = self.update_asset_url.clone() {
                        if ui.add_enabled(!self.downloading && !self.download_ready,
                            egui::Button::new("Download APK")).clicked() {
                            match self.download_update(&asset) {
                                Ok(()) => { self.downloading = true; self.update_status = "Starting Android download…".into(); }
                                Err(error) => self.update_status = error,
                            }
                        }
                    }
                    if self.download_ready && ui.button("Install downloaded APK…").clicked() {
                        match self.install_download() {
                            Ok(()) => { self.downloading = true; self.update_status = "Verifying downloaded APK…".into(); }
                            Err(error) => self.update_status = error,
                        }
                    }
                });
                if ui.checkbox(&mut self.startup_check, "Check for updates at startup").changed() {
                    if let Err(error) = self.save_startup_setting(self.startup_check) {
                        self.update_status = format!("Could not save startup preference: {error}");
                    }
                }
                ui.label(egui::RichText::new(
                    "Published releases only. Installation requires Android confirmation. Test packages cannot replace the stable app."
                ).small());
            });
        self.updates_open = open;
    }
    pub fn dialog(&mut self, ctx: &egui::Context) {
        if self.updates_open { self.updater_dialog(ctx); }
        if self.about_open {
            let mut open = self.about_open;
            egui::Window::new("About PDFCraft")
                .open(&mut open)
                .default_width(340.0)
                .resizable(false)
                .show(ctx, |ui| {
                    ui.heading("PDFCraft");
                    ui.label(format!("Version {}", self.installed_version));
                    ui.label(format!("Android package: {}", self.installed_package));
                    if self.installed_package == "com.artcraft.pdfcraft" {
                        ui.label("Standard PDFCraft package");
                    } else if self.installed_package.starts_with("com.artcraft.pdfcraft.") {
                        ui.label("Separate test package — cannot replace stable PDFCraft");
                    } else {
                        ui.label("Package identity unavailable");
                    }
                    ui.label("PDF editor for Android");
                    ui.label("Updates: published PDFCraft releases only");
                });
            self.about_open = open;
        }
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
                ui.label(crate::pdfcraft_ocr::status());
            });
            if self.gpu_details_open {
                ui.separator();
                ui.label(&self.renderer);
                if ui.button("Hide GPU diagnostics").clicked() { self.gpu_details_open = false; }
            }
            if self.trackpad_details_open {
                ui.separator();
                ui.heading("Trackpad diagnostics");
                if ui.checkbox(&mut self.performance_enabled, "Enable performance measurements").changed() {
                    egui_winit::pdfcraft_input::enabled(self.performance_enabled);
                    self.perf_last_frame = None;
                }
                ui.label("Enable, close this window, scroll the PDF, then reopen to inspect. Measurements continue until disabled.");
                let (events, scrolls, source, action, ns, hz, latency) = egui_winit::pdfcraft_input::snapshot();
                ui.label(format!("Native mouse/trackpad events: {events}; axis-scroll events: {scrolls}"));
                ui.monospace(format!("source=0x{source:X}, action={action}, event timestamp={ns} ns"));
                ui.label(format!("Capture average (includes idle): {hz:.1} axis events/s; last dispatch-to-UI: {latency:.2} ms"));
                let (history, recovered, mean_gap, max_gap, max_latency) = egui_winit::pdfcraft_input::timing_snapshot();
                ui.label(format!("Historical samples: {history}; nonzero scroll samples recovered: {recovered}"));
                ui.label(format!("Within-burst input gaps: mean {mean_gap:.2} ms / max {max_gap:.2} ms; max dispatch-to-UI {max_latency:.2} ms"));
                let variation = if self.perf_frame_count > 1 { (self.perf_m2_ms / (self.perf_frame_count-1) as f64).sqrt() } else { 0.0 };
                let fps = if self.perf_mean_ms > 0.0 { 1000.0 / self.perf_mean_ms } else { 0.0 };
                ui.label(format!("Active UI interval: {:.2} ms; mean {:.2} ms; variation {:.2} ms; {:.1} passes/s",
                    self.perf_last_ms, self.perf_mean_ms, variation, fps));
                ui.label(format!("PDF/UI CPU work: {:.2} ms; intervals >33.3 ms: {}", self.perf_ui_ms, self.perf_slow_frames));
                ui.label("UI-pass timing is not display FPS. GPU upload/present time, dropped display frames and raster-worker time are not measured here. Native Android classification is unavailable in this binding; source/axes/tool drive classification.");
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
                        // PDFCRAFT_ANDROID_CURSOR_OUTPUT_DIAGNOSTICS:
                        // Show the egui cursor and hover state in addition to Java JNI status.
                        ui.label(format!("egui pointer position: {:?}",
                            ui.ctx().input(|i| i.pointer.latest_pos())));
                        ui.label(format!("egui cursor requested: {:?}",
                            ui.ctx().output(|o| o.cursor_icon)));
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

        });
        self.panel_open = open;
    }
}
