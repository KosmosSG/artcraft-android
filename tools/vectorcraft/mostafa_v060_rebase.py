"""Selective owner features on the immutable MostafaXS1 v0.6.0 VectorCraft Android base.

Do NOT transplant the owner's historic native winit, IME, cursor, trackpad or
touchscreen patches. Preserve Mostafa's working input source and its upstream
document/brush/gesture fixes. Fail on unreviewed UI/source anchors.
"""
from pathlib import Path
import shutil
import subprocess
import sys

def once(path: Path, old: str, new: str, label: str):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: {path}: expected exactly one anchor, found {count}")
    path.write_text(text.replace(old, new, 1))

def apply(builder: Path, owner: Path):
    b = builder / "adapters/vectorcraft"
    rust = b / "src/lib.rs"
    java = b / "java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    ui = builder / "source/vectorcraft/crates/ui-egui/src"
    tools = owner / "tools/vectorcraft"
    assert 'ARTCRAFT_ANDROID_NATIVE_IME_V1' in rust.read_text(), "Must start from Mostafa native IME adapter"
    assert 'mod touch_gestures;' in rust.read_text(), "Must retain Mostafa two-/three-finger gestures"
    assert 'com.artcraft.ime.ArtCraftIme.wake()' in java.read_text(), "Must retain Mostafa IME host"
    assert "fn recognise_touch_gesture(" in (builder / "vendor/winit/src/platform_impl/android/mod.rs").read_text()
    assert not (b / "src/ime_bridge.rs").exists(), "Must NOT inherit owner legacy IME bridge"

    # Restore the approved Vc top-left brand popup and existing Android menu
    # command IDs, without altering Mostafa native input or document semantics.
    subprocess.run([sys.executable, str(tools/"patch_android_menus_v020.py"), str(builder)], check=True)
    subprocess.run([sys.executable, str(tools/"patch_vc_icon_menu_v021.py"), str(builder)], check=True)
    shutil.copy2(tools / "stylus_wheel.rs", b / "src/stylus_wheel.rs")
    shutil.copy2(tools / "stylus_wheel_vc.rgba", b / "src/stylus_wheel_vc.rgba")
    shutil.copy2(tools / "VectorCraftUpdateInstaller.java",
                 b / "java/com/artcraft/vectorcraft/VectorCraftUpdateInstaller.java")
    assert (b / "src/stylus_wheel_vc.rgba").stat().st_size == 192*120*4
    once(rust, "mod touch_gestures;\n", "mod touch_gestures;\nmod stylus_wheel;\n", "wheel module")

    # Add only an Activity-level pen-button signal queue, guarded by exact
    # physical Magic-Pencil 4s device name. Ordinary keys, winit and IME stay
    # owned by Mostafa. The wheel remains operable through the Vc menu.
    once(java, "    private final ConcurrentLinkedQueue<String> imeQueue = new ConcurrentLinkedQueue<>();",
         """    private final ConcurrentLinkedQueue<String> imeQueue = new ConcurrentLinkedQueue<>();
    private final ConcurrentLinkedQueue<String> vcWheelSignals = new ConcurrentLinkedQueue<>();
    private volatile boolean vcWheelEnabled = true;
    private long vcWheelLastSignalAt;
    private final ExecutorService vcUpdatesIo = Executors.newSingleThreadExecutor();
    private VectorCraftUpdateInstaller vcVerifiedUpdater;
    public void vcWheelSetEnabled(boolean enabled) {
        vcWheelEnabled = enabled;
        getSharedPreferences("vc-wheel-approval", MODE_PRIVATE).edit().putBoolean("enabled", enabled).apply();
        if (!enabled) vcWheelSignals.clear();
    }
    public String vcWheelPoll() { return vcWheelSignals.poll(); }
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (event != null && vcWheelEnabled && event.getDeviceId() > 0) {
            final InputDevice device = InputDevice.getDevice(event.getDeviceId());
            final String name = device == null ? "" : device.getName();
            final int code = event.getKeyCode();
            if (name != null && name.contains("Magic-Pencil 4s") &&
                (code == KeyEvent.KEYCODE_DPAD_DOWN || code == KeyEvent.KEYCODE_DPAD_UP)) {
                if (event.getAction() == KeyEvent.ACTION_UP && event.getRepeatCount() == 0) {
                    long now = SystemClock.uptimeMillis();
                    if (now - vcWheelLastSignalAt >= 450L && vcWheelSignals.size() < 12) {
                        vcWheelLastSignalAt = now;
                        vcWheelSignals.offer(code == KeyEvent.KEYCODE_DPAD_DOWN ? "S" : "D");
                        wakeNativeLoop();
                    }
                }
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }
    public void vcCheckUpdates() {
        vcUpdatesIo.execute(() -> {
            String detail = "Could not check releases.";
            String version = "";
            String assetUrl = null;
            String digest = null;
            long bytes = 0L;
            try {
                java.net.HttpURLConnection c = (java.net.HttpURLConnection)
                    new java.net.URL("https://api.github.com/repos/KosmosSG/artcraft-android/releases/latest")
                        .openConnection();
                c.setConnectTimeout(8000); c.setReadTimeout(8000);
                c.setRequestProperty("Accept","application/vnd.github+json");
                c.setRequestProperty("User-Agent","VectorCraft-Android");
                if (c.getResponseCode() == 200) {
                    java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
                    try (java.io.InputStream in = c.getInputStream()) {
                        byte[] part = new byte[8192]; int n;
                        while ((n = in.read(part)) > 0 && out.size() < 1000000) out.write(part,0,n);
                    }
                    org.json.JSONObject release = new org.json.JSONObject(out.toString("UTF-8"));
                    String tag = release.optString("tag_name","");
                    version = tag.startsWith("vectorcraft-v") ? tag.substring(13) : "";
                    org.json.JSONArray assets = release.optJSONArray("assets");
                    if (assets != null && !version.isEmpty()) {
                        String expected = "VectorCraft-v" + version + "-arm64-v8a.apk";
                        for (int i=0;i<assets.length();i++) {
                            org.json.JSONObject a = assets.optJSONObject(i);
                            if (a != null && expected.equals(a.optString("name"))) {
                                assetUrl=a.optString("browser_download_url");
                                digest=a.optString("digest");
                                bytes=a.optLong("size");
                                break;
                            }
                        }
                    }
                    detail = version.isEmpty() ? "No compatible production VectorCraft release listed."
                        : "Latest production VectorCraft release: " + version;
                }
                c.disconnect();
            } catch (Exception e) { Log.w(TAG, "Vc release check",e); }
            if (vcVerifiedUpdater != null) vcVerifiedUpdater.remember(version,assetUrl,digest,bytes);
            final String display = detail, latest = version;
            runOnUiThread(() -> {
                android.app.AlertDialog.Builder dialog = new android.app.AlertDialog.Builder(this)
                    .setTitle("VectorCraft App Updates")
                    .setMessage(display + (getPackageName().equals("com.artcraft.vectorcraft")
                        ? "\nVerified in-app download is available only for matching published APK signatures."
                        : "\nTEST BUILD: production installer disabled; your stable VectorCraft is safe."))
                    .setNegativeButton("Close",null)
                    .setNeutralButton("View Releases",(d,w) -> {
                        try {startActivity(new Intent(Intent.ACTION_VIEW,
                            Uri.parse("https://github.com/KosmosSG/artcraft-android/releases"))); }
                        catch (Exception e) {Log.w(TAG, "Open releases", e);}
                    });
                if (vcVerifiedUpdater != null && vcVerifiedUpdater.canDownload(latest)) {
                    dialog.setPositiveButton("Download in App",(d,w) ->
                        vcVerifiedUpdater.start(latest,vcUpdatesIo));
                }
                dialog.show();
            });
        });
    }""",
        "Mostafa Java isolated pen and in-app updater")

    once(java, "        super.onCreate(savedInstanceState);",
         """        super.onCreate(savedInstanceState);
        vcWheelEnabled = getSharedPreferences("vc-wheel-approval",MODE_PRIVATE).getBoolean("enabled",true);
        vcVerifiedUpdater = new VectorCraftUpdateInstaller(this,
            new ConcurrentLinkedQueue<String>());""",
         "initialize wheel/update on launch")

    # The official owner release installer checks SHA-256, package and signer;
    # it refuses to install from a separate test package. This class is copied
    # unchanged and its callback remains attached to Activity lifecycle.
    once(java, "        handleIncomingFiles(intent);\n", """        handleIncomingFiles(intent);
        if (vcVerifiedUpdater != null &&
            VectorCraftUpdateInstaller.INSTALL_ACTION.equals(intent.getAction())) {
            vcVerifiedUpdater.onInstallStatus(intent);
        }
""", "installer callback in onNewIntent")

    bridge = r"""    fn vc_wheel_poll(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("vcWheelPoll"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if value.is_null() { return Ok(None); }
            let value = JString::cast_local(env, value)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }
    fn vc_wheel_set_enabled(&self, enabled: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcWheelSetEnabled"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
    fn vc_check_updates(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcCheckUpdates"),
                jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
"""
    once(rust, "    fn files_dir(&self) -> Result<String, String> {",
         bridge + "    fn files_dir(&self) -> Result<String, String> {", "JNI bridge methods")
    once(rust, "    inner: VectorcraftApp,\n", """    inner: VectorcraftApp,
    stylus_wheel: stylus_wheel::Wheel,
    startup_updates: bool,
    touch_dock: bool,
""", "Mostafa app state")

    raw = """    fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        mobile_text_bar::process_raw_input(ctx, raw);"""
    enhanced = """    fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        // D / S / C belong ONLY to the upstream Save Changes dialog; never
        // interpret document typing or a physical keyboard shortcut as a
        // destructive action outside this modal.
        if self.inner.ui.dialog.as_ref().is_some_and(|d| d.kind == "saveChanges") {
            let command = raw.events.iter().find_map(|event| match event {
                egui::Event::Key { key, pressed: true, repeat: false, .. } =>
                    match key {
                        egui::Key::D => Some('d'),
                        egui::Key::S => Some('s'),
                        egui::Key::C | egui::Key::Escape => Some('c'),
                        _ => None,
                    },
                egui::Event::Text(value) if value.len() == 1 =>
                    match value.to_ascii_lowercase().as_str() {
                        "d" => Some('d'), "s" => Some('s'), "c" => Some('c'), _ => None,
                    },
                _ => None,
            });
            if let Some(command) = command {
                if command == 'd' {
                    if let Some(d) = self.inner.ui.dialog.as_mut() {
                        d.fields.insert("discard".into(), serde_json::json!(true));
                    }
                }
                let action = if command == 'c' {"ui.dialog.cancel"} else {"ui.dialog.confirm"};
                if let Err(error) = self.inner.run(action, serde_json::json!({})) {
                    log::warn!("Save Changes {command}: {error}");
                }
                raw.events.retain(|e| !matches!(e,
                    egui::Event::Text(t) if t.len() == 1
                       && "dsc".contains(t.to_ascii_lowercase().as_str()))
                    && !matches!(e, egui::Event::Key {
                        key: egui::Key::D | egui::Key::S | egui::Key::C
                          | egui::Key::Escape, pressed: true, ..
                    }));
                ctx.request_repaint();
            }
        }
        let wheel_blocked = self.inner.session.active().is_none()
            || self.inner.session.tool_wants_text()
            || ctx.text_edit_focused()
            || self.inner.ui.dialog.is_some()
            || egui::Popup::is_any_open(ctx);
        for _ in 0..8 {
            match self.bridge.vc_wheel_poll() {
                Ok(Some(code)) => if !wheel_blocked { self.stylus_wheel.signal(&code, ctx); },
                _ => break,
            }
        }
        self.stylus_wheel.capture(ctx, raw, wheel_blocked);
        mobile_text_bar::process_raw_input(ctx, raw);"""
    once(rust,raw,enhanced,"modal D/S/C and wheel input, leaving native IME untouched")

    rust_ui="""        system_fonts::install_system_fonts(ui.ctx());
        self.inner.ui(ui);
        mobile_text_bar::show_text_bar(ui.ctx());"""
    enhanced_ui="""        system_fonts::install_system_fonts(ui.ctx());
        if let Some(action) = self.stylus_wheel.take_action() {
            if action.starts_with("edit.") {
                if let Err(error) = self.inner.run(action, serde_json::json!({})) {
                    log::warn!("Vc wheel action: {error}");
                }
            } else { self.inner.select_tool(action); }
        }
        vectorcraft_ui_egui::menus::set_android_preferences(self.touch_dock, self.startup_updates);
        vectorcraft_ui_egui::menus::set_android_wheel_enabled(self.stylus_wheel.enabled);
        self.inner.ui(ui);
        self.stylus_wheel.render(ui);
        if let Some(layout) = self.stylus_wheel.take_layout_change() {
            if let Some(dir) = &self.persist {
                persist_write(dir, "vc-wheel-layout.txt", layout.as_bytes());
            }
        }
        let bits = vectorcraft_ui_egui::menus::take_android_menu_bits();
        if bits & 256 != 0 {
            let enable = !self.stylus_wheel.enabled;
            self.stylus_wheel.toggle(enable, ui.ctx());
            if let Err(error) = self.bridge.vc_wheel_set_enabled(enable) {
                log::warn!("Stylus wheel enable: {error}");
            }
            if let Some(dir) = &self.persist {
                persist_write(dir, "vc-wheel-enabled.txt", if enable {b"1"} else {b"0"});
            }
        }
        if bits & 512 != 0 { self.stylus_wheel.open_customizer(ui.ctx()); }
        if bits & 8 != 0 {
            if let Err(error) = self.bridge.vc_check_updates() {
                log::warn!("Vc in-app updater check: {error}");
            }
        }
        if bits & 16 != 0 {
            self.startup_updates = !self.startup_updates;
            if let Some(dir) = &self.persist {
                persist_write(dir, "vc-updates-startup.txt",
                    if self.startup_updates {b"1"} else {b"0"});
            }
        }
        if bits & 32 != 0 { self.touch_dock = !self.touch_dock; }
        mobile_text_bar::show_text_bar(ui.ctx());"""
    once(rust, rust_ui, enhanced_ui,"VectorCraft UI wheel and Vc menu routing")

    # Mostafa's SAF/IME system state stays in place. Preserve persisted
    # wheel layout + option across app restarts without changing documents.
    once(rust, """            Ok(Box::new(VectorCraftAndroidApp {
                inner: app,""",
         """            let mut wheel = stylus_wheel::Wheel::new(persist.as_ref()
                .and_then(|p| persist_read(p, "vc-wheel-enabled.txt"))
                .map_or(true, |v| v == b"1"));
            if let Some(saved) = persist.as_ref().and_then(|p| persist_read(p, "vc-wheel-layout.txt")) {
                if let Ok(text) = String::from_utf8(saved) { wheel.set_layout_string(&text); }
            }
            let startup_updates = persist.as_ref()
                .and_then(|p| persist_read(p, "vc-updates-startup.txt"))
                .is_some_and(|v| v == b"1");
            Ok(Box::new(VectorCraftAndroidApp {
                inner: app,
                stylus_wheel: wheel,
                startup_updates,
                touch_dock: false,""",
         "instantiate wheel with persisted settings")

    menu = ui/"menus.rs"
    once(menu, """            if ui.button("Touch Shortcut Pad").clicked() {""",
         """            ui.menu_button("Stylus Wheel", |ui| {
                let mut enabled = ANDROID_WHEEL_ENABLED.load(std::sync::atomic::Ordering::Acquire);
                if ui.checkbox(&mut enabled, "Enable Stylus Wheel").changed() {
                    clicked = Some(("android.vectorcraft.stylusWheel".into(), serde_json::json!({})));
                    ui.close();
                }
                if ui.button("Customization…").clicked() {
                    clicked = Some(("android.vectorcraft.stylusWheelCustomize".into(), serde_json::json!({})));
                    ui.close();
                }
            });
            if ui.button("Touch Shortcut Pad").clicked() {""", "Vc icon wheel submenu")
    with menu.open("a") as f:
        f.write("""
#[cfg(target_os = "android")]
static ANDROID_WHEEL_ENABLED: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(true);
#[cfg(target_os = "android")]
pub fn set_android_wheel_enabled(enabled: bool) {
    ANDROID_WHEEL_ENABLED.store(enabled, std::sync::atomic::Ordering::Release);
}
""")
    run = ui/"menus/run.rs"
    once(run, """            "android.vectorcraft.fontImport" => 1,""",
         """            "android.vectorcraft.stylusWheel" => 256,
            "android.vectorcraft.stylusWheelCustomize" => 512,
            "android.vectorcraft.fontImport" => 1,""", "wire Vc menu wheel bits")
    tree = ui/"menus/tree.rs"
    once(tree, """            "Vc",
            vec![""",
         """            "Vc",
            vec![
                c("Stylus Wheel", "android.vectorcraft.stylusWheel"),
                c("Customize Stylus Wheel…", "android.vectorcraft.stylusWheelCustomize"),""",
         "preserve native Vc tree")

    manifest = b / "Cargo.toml"
    if 'android.permission.REQUEST_INSTALL_PACKAGES' not in manifest.read_text():
        with manifest.open("a") as f:
            f.write('\n[[package.metadata.android.uses_permission]]\nname = "android.permission.REQUEST_INSTALL_PACKAGES"\n')
    assert 'ARTCRAFT_ANDROID_NATIVE_IME_V1' in rust.read_text()
    assert 'touch_gestures::process_raw_input(ctx, raw);' in rust.read_text()
    assert 'mod stylus_wheel;' in rust.read_text()
    assert 'app.ui.dialog' not in rust.read_text() or 'saveChanges' in rust.read_text()
    assert 'android.vectorcraft.stylusWheel' in run.read_text()
    assert "vcCheckUpdates" in java.read_text()
    assert "vcWheelPoll" in java.read_text()
    print("PASS: Mostafa v0.6.0 adapter retained; Vc icon, menu, wheel, scoped D/S/C, verified in-app updater staged")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: mostafa_rebase.py BUILDER OWNER")
    apply(Path(sys.argv[1]),Path(sys.argv[2]))
