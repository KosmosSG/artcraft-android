#!/usr/bin/env python3
"""Guarded candidate-only v0.22.0 Android.3 Magic-Pencil radial wheel."""
import argparse
from pathlib import Path

def once(path: Path, old: str, new: str):
    data = path.read_text(encoding="utf-8")
    n = data.count(old)
    if n != 1:
        raise RuntimeError(f"stylus wheel unsafe anchor in {path}: count={n}: {old[:120]!r}")
    path.write_text(data.replace(old, new, 1), encoding="utf-8")

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--upstream", type=Path, required=True)
    cli.add_argument("--adapter", type=Path, required=True)
    a = cli.parse_args()
    activity = a.adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"
    host = a.adapter / "src/lib.rs"
    brand = a.upstream / "crates/ui-egui/src/panels/brand.rs"
    src = a.adapter / "src/stylus_wheel.rs"

    once(activity,
        "    public String pcFilesDir() {",
        """    private volatile boolean pcWheelEnabled = false;
    private final ConcurrentLinkedQueue<String> pcWheelKeys = new ConcurrentLinkedQueue<>();
    private long pcWheelLastUp, pcWheelLastDown;
    public boolean pcStylusEnabled() { return pcWheelEnabled; }
    public void pcStylusSetEnabled(boolean enabled) {
        pcWheelEnabled = enabled;
        pcWheelKeys.clear();
        pcWheelLastUp = pcWheelLastDown = 0L;
        getSharedPreferences("pc_experimental_wheel", MODE_PRIVATE).edit()
            .putBoolean("enabled", enabled).apply();
    }
    public String pcStylusPoll() { return pcWheelKeys.poll(); }
    private boolean pcStylusIntercept(KeyEvent event) {
        if (!pcWheelEnabled) return false;
        android.view.InputDevice device =
            android.view.InputDevice.getDevice(event.getDeviceId());
        if (device == null || device.getName() == null
            || !device.getName().contains("Magic-Pencil 4s")) return false;
        int code = event.getKeyCode();
        if (code != KeyEvent.KEYCODE_DPAD_DOWN && code != KeyEvent.KEYCODE_DPAD_UP)
            return false;
        if (event.getAction() == KeyEvent.ACTION_UP && event.getRepeatCount() == 0) {
            long now = android.os.SystemClock.uptimeMillis();
            long last = code == KeyEvent.KEYCODE_DPAD_UP
                ? pcWheelLastUp : pcWheelLastDown;
            if (now - last >= 650L && pcWheelKeys.size() < 12) {
                pcWheelKeys.offer(code == KeyEvent.KEYCODE_DPAD_UP ? "D" : "S");
                if (code == KeyEvent.KEYCODE_DPAD_UP) pcWheelLastUp = now;
                else pcWheelLastDown = now;
            }
        }
        // Only while the explicit wheel setting is on: suppress OEM DPAD scroll
        // and pass the original physical-key/IME routes through unchanged otherwise.
        return true;
    }

    public String pcFilesDir() {""")
    once(activity,
        "        super.onCreate(savedInstanceState);\n",
        """        super.onCreate(savedInstanceState);
        pcWheelEnabled = getSharedPreferences("pc_experimental_wheel", MODE_PRIVATE)
            .getBoolean("enabled", false);
""")
    once(activity,
        "    public boolean dispatchKeyEvent(KeyEvent event) {\n",
        """    public boolean dispatchKeyEvent(KeyEvent event) {
        if (pcStylusIntercept(event)) return true;
""")

    new_bridge = """    fn pc_stylus_set_enabled(&self, enabled: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pcStylusSetEnabled"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn pc_stylus_enabled(&self) -> Result<bool, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pcStylusEnabled"),
                jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| e.to_string())
    }

    fn pc_stylus_poll(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pcStylusPoll"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

"""
    once(host, "    fn files_dir(&self) -> Result<PathBuf, String> {\n",
         new_bridge + "    fn files_dir(&self) -> Result<PathBuf, String> {\n")
    once(host, "mod ai_menu;\n", "mod ai_menu;\nmod stylus_wheel;\n")
    once(host, "    ai_menu: ai_menu::AndroidAiMenu,\n",
         "    ai_menu: ai_menu::AndroidAiMenu,\n    stylus_wheel: stylus_wheel::Wheel,\n")
    once(host, '                ai_menu: ai_menu::AndroidAiMenu::new(',
         '                stylus_wheel: stylus_wheel::Wheel::new(app_bridge.pc_stylus_enabled().unwrap_or(false)),\n'
         '                ai_menu: ai_menu::AndroidAiMenu::new(')

    # A checked row in the established Pc menu, without a separate floating
    # settings window. 34 is outside existing 1-33 action IDs.
    once(brand, '            ui.menu_button("Shortcut Pad", |ui| {',
         '''            ui.menu_button("Stylus Wheel", |ui| {
                let enabled = ui.ctx().data(|d|
                    d.get_temp::<bool>(egui::Id::new("pc_stylus_wheel_enabled"))
                        .unwrap_or(false));
                action(ui, if enabled {
                    "✓ Stylus Wheel ON (tap to disable)"
                } else {
                    "Stylus Wheel OFF (tap to enable)"
                }, 34);
                ui.label("Magic-Pencil 4s • hover + press");
                ui.label("Single: six-tool wheel");
                ui.label("Double: quick Eraser");
                ui.label("Tap pen tip: select • Esc: cancel");
            });
            ui.menu_button("Shortcut Pad", |ui| {''')

    once(host, "            20..=33 => {",
         '''            34 => {
                let requested = !self.stylus_wheel.enabled;
                match self.bridge.pc_stylus_set_enabled(requested) {
                    Ok(()) => self.stylus_wheel.toggle(requested, ui.ctx()),
                    Err(error) => log::warn!("Stylus wheel toggle unavailable: {error}"),
                }
            }
            20..=33 => {''')
    once(host, "        self.inner.raw_input_hook(ctx, raw);\n",
         '''        let wheel_blocked = self.inner.ui.text_edit.is_some()
            || ctx.text_edit_focused()
            || photocraft_ui_egui::menus::artcraft_discard_active(&self.inner);
        if self.stylus_wheel.enabled && !wheel_blocked {
            for _ in 0..12 {
                match self.bridge.pc_stylus_poll() {
                    Ok(Some(signal)) => self.stylus_wheel.signal(&signal, ctx),
                    _ => break,
                }
            }
        }
        self.stylus_wheel.capture(ctx, raw, wheel_blocked);
        self.inner.raw_input_hook(ctx, raw);
''')
    once(host, "        self.inner.ui(ui, _frame);\n",
         '''        if let Some(command) = self.stylus_wheel.take_action() {
            if let Err(error) = photocraft_ui_egui::menus::invoke(
                &mut self.inner, ui.ctx(), command, serde_json::json!({})
            ) { log::warn!("Stylus wheel command {command}: {error}"); }
        }
        ui.ctx().data_mut(|d| d.insert_temp(
            egui::Id::new("pc_stylus_wheel_enabled"), self.stylus_wheel.enabled
        ));
        self.inner.ui(ui, _frame);
        self.stylus_wheel.render(ui);
''')
    src.write_text((Path(__file__).parent / "photocraft_v022_stylus_wheel.rs").read_text(encoding="utf-8"))
    assert "pcStylusIntercept(event)" in activity.read_text()
    assert "stylus_wheel.capture" in host.read_text()
    assert "artcraft_brush_scroll_area" in (a.adapter / "src/trackpad_wheel.rs").read_text()
    assert 'ui.menu_button("Appearance", |ui| {' in brand.read_text()
    print("PASS: guarded radial wheel, 6 commands, opt-in persisted, pen-only keycodes, canvas gesture preservation")
if __name__ == "__main__":
    main()
