#!/usr/bin/env python3
"""EffectCraft v0.24.1-only UI and verified pen-input integration.

Run AFTER integrate_updater.py, before build.sh. Patch the temporary EffectCraft
upstream clone, Android packager recipe and Java template; never published source.
Fail closed if official source or approved Android hooks drift.
"""
from pathlib import Path
import sys

def one(path, old, new):
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"STOP: EffectCraft stylus hook changed: {path} {old[:80]!r} count={count}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

def main(root):
    root = Path(root)
    source = root / "source/effectcraft/crates/ui-egui/src"
    lib = source / "lib.rs"
    app = source / "app.rs"
    header = source / "header.rs"
    java = root / "templates/android/SafActivity.java"
    builder = root / "lib/build-common.sh"
    updater = root / "tools/effectcraft/android_updater.rs"

    # A private, Android-only editor module. Keeps the full official desktop/UI
    # source untouched outside the disposable Actions checkout.
    one(lib, "pub mod header;\n", "pub mod header;\n#[cfg(target_os = \"android\")]\nmod stylus_wheel;\n")
    one(lib, "    pub ui: UiState,\n", """    pub ui: UiState,
    #[cfg(target_os = "android")]
    pub(crate) stylus_wheel: stylus_wheel::Wheel,
""")
    one(app, "        EffectcraftApp {\n            session,\n",
        """        EffectcraftApp {
            session,
            #[cfg(target_os = "android")]
            stylus_wheel: Default::default(),
""")
    one(app, "    pub fn window_title(&self) -> &str {",
        """    #[cfg(target_os = "android")]
    pub fn set_stylus_wheel_storage(&mut self, path: std::path::PathBuf) {
        self.stylus_wheel.set_storage(path);
    }

    #[cfg(target_os = "android")]
    pub fn stylus_wheel_enabled(&self) -> bool { self.stylus_wheel.enabled }

    #[cfg(target_os = "android")]
    pub fn stylus_button(&mut self, code: i32, ctx: &egui::Context) {
        if self.dialog.is_none() && self.session.state.text_edit.is_none()
            && !egui::Popup::is_any_open(ctx) {
            self.stylus_wheel.pen_button(code, ctx);
        }
    }

    pub fn window_title(&self) -> &str {""")
    one(app, "        if pointer_wrap::prepare_input(ctx, raw_input, injected) {",
        """        #[cfg(target_os = "android")]
        self.stylus_wheel.capture(ctx, raw_input,
            self.dialog.is_some() || self.session.state.text_edit.is_some());
        if pointer_wrap::prepare_input(ctx, raw_input, injected) {""")
    one(app, "        self.draw(ui, frame);\n",
        """        self.draw(ui, frame);
        #[cfg(target_os = "android")]
        {
            if let Some(command) = self.stylus_wheel.take_action() {
                use crate::stylus_wheel::WheelAction;
                match command {
                    WheelAction::Panel(panel) => self.show_panel(panel),
                    WheelAction::CropRegion => {
                        self.show_panel(crate::dock::PanelKind::Composition);
                        self.ui.viewer.roi_draw = true;
                    }
                    WheelAction::Invoke(command) => {
                        if let Err(error) = crate::menus::invoke(
                            self, ui.ctx(), command, serde_json::json!({})) {
                            self.ui.status = error;
                        }
                    }
                }
            }
            self.stylus_wheel.render(ui.ctx());
        }
""")

    # Integrate with existing compact Ec menu, immediately above Appearance.
    one(header, """                        // Like GridCraft: one nested Appearance menu, no extra toolbar.""",
        """                        // The same Default eight-segment wheel UI as PhotoCraft:
                        // opt-in, per-app saved choices and a real 1:1 preview.
                        ui.separator();
                        let wheel_on = app.stylus_wheel.enabled;
                        if ui.button(if wheel_on {
                            "✓ Stylus Wheel ON"
                        } else {
                            "Stylus Wheel OFF"
                        }).clicked() {
                            app.stylus_wheel.toggle(ui.ctx());
                            ui.close();
                        }
                        if ui.add_enabled(wheel_on, egui::Button::new("Open Stylus Wheel")).clicked() {
                            app.stylus_wheel.open_at_hover(ui.ctx());
                            ui.close();
                        }
                        if ui.button("Customize Stylus Wheel…").clicked() {
                            app.stylus_wheel.settings_open = true;
                            ui.close();
                        }
                        // Like GridCraft: one nested Appearance menu, no extra toolbar.""")

    (source / "stylus_wheel.rs").write_text(
        (root / "tools/effectcraft/stylus_wheel.rs").read_text(encoding="utf-8"),
        encoding="utf-8")

    # Use EffectCraft's own app-private directory, never Android/data shared files.
    one(builder, 'inner.session.load_settings();\'\'\'',
        '''inner.session.load_settings();
    inner.set_stylus_wheel_storage(dir.join("effectcraft-stylus-wheel-default.v1"));\'\'\' '''.rstrip())
    # The generated launcher already has a tested Updater with JNI access.
    # Its on-frame hook can poll a verified input queue without changing IME.
    one(builder,
        '        self.updates.keyboard_shortcuts(&mut self.inner, ui.ctx());',
        '''        self.updates.stylus_shortcuts(&mut self.inner, ui.ctx());
        self.updates.keyboard_shortcuts(&mut self.inner, ui.ctx());''')

    # Android Java must be the input device identity authority.
    if "ecConsumePhysicalShortcut" not in java.read_text(encoding="utf-8"):
        raise RuntimeError("STOP: approved keyboard and IME bridge missing")
    one(java, "\n        if (ecConsumeDialogKey(event) || ecConsumePhysicalShortcut(event)) return true;",
        "\n        if (ecWheelKey(event) || ecConsumeDialogKey(event) || ecConsumePhysicalShortcut(event)) return true;")
    one(java,
        "                            if (ecConsumeDialogKey(event) || ecConsumePhysicalShortcut(event)) return true;",
        "                            if (ecWheelKey(event) || ecConsumeDialogKey(event) || ecConsumePhysicalShortcut(event)) return true;")
    for a in [
        "                public boolean onKeyDown(int keyCode, KeyEvent event) {",
        "                public boolean onKeyUp(int keyCode, KeyEvent event) {",
    ]:
        one(java, a, a + "\n                    if (ecWheelKey(event)) return true;")
    j = java.read_text(encoding="utf-8").rstrip()
    if "ecWheelKey" not in j or not j.endswith("}"):
        raise RuntimeError("STOP: no Java class closing brace")
    j = j[:-1] + r'''
    // Only the HONOR Magic-Pencil 4s is an allowed stylus source. Never
    // consume a physical keyboard arrow, touchpad or ordinary IME input.
    private volatile boolean ecWheelEnabled;
    private final java.util.concurrent.ConcurrentLinkedQueue<Integer> ecWheelButtons =
        new java.util.concurrent.ConcurrentLinkedQueue<>();
    private final java.util.HashSet<Integer> ecWheelHeld = new java.util.HashSet<>();
    private long ecWheelLastDown, ecWheelLastUp;
    public void ecWheelSetEnabled(boolean value) {
        ecWheelEnabled = value;
        if (!value) { ecWheelButtons.clear(); ecWheelHeld.clear(); }
    }
    public String ecWheelDeviceIds() {
        StringBuilder found = new StringBuilder();
        for (int id : android.view.InputDevice.getDeviceIds()) {
            android.view.InputDevice device = android.view.InputDevice.getDevice(id);
            if (device != null && device.getName() != null
                    && device.getName().contains("Magic-Pencil 4s")) {
                if (found.length() > 0) found.append(',');
                found.append(id);
            }
        }
        return found.toString();
    }
    public int ecWheelPoll() {
        Integer event = ecWheelButtons.poll();
        return event == null ? 0 : event.intValue();
    }
    private boolean ecWheelKey(android.view.KeyEvent event) {
        if (!ecWheelEnabled || event == null
            || (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) != 0)
            return false;
        int code = event.getKeyCode();
        if (code != android.view.KeyEvent.KEYCODE_DPAD_DOWN
            && code != android.view.KeyEvent.KEYCODE_DPAD_UP) return false;
        android.view.InputDevice device = android.view.InputDevice.getDevice(event.getDeviceId());
        if (device == null || device.getName() == null
            || !device.getName().contains("Magic-Pencil 4s")) return false;
        synchronized (ecWheelHeld) {
            if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                ecWheelHeld.add(code);
                return true;
            }
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) {
                ecWheelHeld.remove(code);
                long now = android.os.SystemClock.uptimeMillis();
                long last = code == android.view.KeyEvent.KEYCODE_DPAD_UP
                    ? ecWheelLastUp : ecWheelLastDown;
                if (event.getRepeatCount() == 0 && now - last >= 650L
                        && ecWheelButtons.size() < 12) {
                    ecWheelButtons.offer(code == android.view.KeyEvent.KEYCODE_DPAD_UP ? 2 : 1);
                    if (code == android.view.KeyEvent.KEYCODE_DPAD_UP) ecWheelLastUp = now;
                    else ecWheelLastDown = now;
                }
                return true;
            }
        }
        return false;
    }
}
'''
    java.write_text(j, encoding="utf-8")

    # Small adapter-side JNI path: pre-winit native queue or Java IME route.
    hook = r'''
    /// Poll only the explicitly verified Magic-Pencil 4s button events.
    /// The editor itself gates text edits, popups and unsaved dialogs.
    pub fn stylus_shortcuts(&mut self, inner: &mut EffectcraftApp, ctx: &egui::Context) {
        let enabled = inner.stylus_wheel_enabled();
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let outcome = vm.attach_current_thread(|env| -> jni::errors::Result<(Vec<i32>, Vec<i32>)> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("ecWheelSetEnabled"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled.into())])?;
            let devices = env.call_method(&*activity, jni_str!("ecWheelDeviceIds"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            let ids = if devices.is_null() { String::new() }
                else { JString::cast_local(env, devices)?.try_to_string(env)? };
            let ids = ids.split(',').filter_map(|v| v.parse::<i32>().ok()).take(16).collect();
            let mut buttons = Vec::new();
            for _ in 0..12 {
                let n = env.call_method(&*activity, jni_str!("ecWheelPoll"),
                    jni_sig!("()I"), &[])?.i()?;
                if n == 0 { break; }
                buttons.push(n);
            }
            Ok((ids, buttons))
        });
        if let Ok((ids, buttons)) = outcome {
            android_activity::ec_stylus_configure(enabled, &ids);
            // Both NativeActivity's input queue and the hidden IME Java bridge
            // can deliver the pen. They never consume generic keyboard arrows.
            let native = android_activity::ec_stylus_native_take();
            if !enabled { return; }
            for code in native.into_iter().chain(buttons) {
                inner.stylus_button(code, ctx);
            }
        } else if let Err(error) = outcome {
            log::warn!("EffectCraft stylus input identity bridge: {error}");
        }
    }
'''
    one(updater, "impl Updater {\n", "impl Updater {\n" + hook + "\n")
    print("PASS: EffectCraft wheel visuals, 1:1 preview, persisted settings, verified pen queue and editor isolation")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_stylus_wheel.py <repo-root>")
    main(Path(sys.argv[1]))
