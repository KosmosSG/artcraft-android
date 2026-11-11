"""Proposal A, ported from the owner-tested PhotoCraft wheel. Apply after Android.7."""
from pathlib import Path
import shutil, sys

def once(path, old, new):
    s=path.read_text()
    if s.count(old)!=1: raise ValueError(f'{path}: anchor count {s.count(old)}: {old[:90]}')
    path.write_text(s.replace(old,new,1))

def patch(root):
    src=Path(__file__).parent
    a=root/'adapters/vectorcraft'; host=a/'src/lib.rs'
    java=a/'java/com/artcraft/vectorcraft/VectorCraftActivity.java'
    ui=root/'source/vectorcraft/crates/ui-egui/src'
    for name in ('stylus_wheel.rs','stylus_wheel_vc.rgba'):
        shutil.copyfile(src/name,a/'src'/name)
    once(java,'    public String imePoll() {', '''    private volatile boolean vcWheelEnabled = false;
    private final ConcurrentLinkedQueue<String> vcWheelKeys = new ConcurrentLinkedQueue<>();
    private long vcWheelLastUp, vcWheelLastDown;
    public String vcStylusGetLayout() {
        return getSharedPreferences("vc_stylus_wheel", MODE_PRIVATE)
            .getString("layout", "0,1,2,3,4,5,6,7");
    }
    public void vcStylusSetLayout(String layout) {
        if (layout != null && layout.length() <= 64)
            getSharedPreferences("vc_stylus_wheel", MODE_PRIVATE)
                .edit().putString("layout", layout).apply();
    }
    public boolean vcStylusEnabled() { return vcWheelEnabled; }
    public void vcStylusSetEnabled(boolean enabled) {
        vcWheelEnabled = enabled;
        vcWheelKeys.clear();
        vcWheelLastUp = vcWheelLastDown = 0L;
        getSharedPreferences("vc_stylus_wheel", MODE_PRIVATE).edit().putBoolean("enabled", enabled).apply();
    }
    public String vcStylusPoll() { return vcWheelKeys.poll(); }
    public String vcStylusDeviceIds() {
        StringBuilder ids = new StringBuilder();
        for (int id : android.view.InputDevice.getDeviceIds()) {
            android.view.InputDevice input = android.view.InputDevice.getDevice(id);
            if (input != null && input.getName() != null && input.getName().contains("Magic-Pencil 4s")) {
                if (ids.length() > 0) ids.append(',');
                ids.append(id);
            }
        }
        return ids.toString();
    }
    private boolean vcStylusIntercept(KeyEvent event) {
        if (!vcWheelEnabled) return false;
        android.view.InputDevice d = android.view.InputDevice.getDevice(event.getDeviceId());
        if (d == null || d.getName() == null || !d.getName().contains("Magic-Pencil 4s")) return false;
        int code = event.getKeyCode();
        if (code != KeyEvent.KEYCODE_DPAD_UP && code != KeyEvent.KEYCODE_DPAD_DOWN) return false;
        if (event.getAction() == KeyEvent.ACTION_UP && event.getRepeatCount() == 0) {
            long now = android.os.SystemClock.uptimeMillis();
            long last = code == KeyEvent.KEYCODE_DPAD_UP ? vcWheelLastUp : vcWheelLastDown;
            if (now - last >= 650L && vcWheelKeys.size() < 12) {
                vcWheelKeys.offer(code == KeyEvent.KEYCODE_DPAD_UP ? "D" : "S");
                if (code == KeyEvent.KEYCODE_DPAD_UP) vcWheelLastUp = now; else vcWheelLastDown = now;
                vcWakeNativeLoop();
            }
        }
        return true;
    }
    public String imePoll() {''')
    once(java,'        super.onCreate(savedInstanceState);','''        super.onCreate(savedInstanceState);
        vcWheelEnabled = getSharedPreferences("vc_stylus_wheel", MODE_PRIVATE).getBoolean("enabled", false);''')
    once(java,'    public boolean dispatchKeyEvent(KeyEvent event) {','''    public boolean dispatchKeyEvent(KeyEvent event) {
        if (vcStylusIntercept(event)) return true;''')
    # IME host must not turn pen-button arrows into navigation.
    for signature in ('public boolean onKeyPreIme(int keyCode, KeyEvent event) {','public boolean onKeyDown(int keyCode, KeyEvent event) {','public boolean onKeyUp(int keyCode, KeyEvent event) {','public boolean sendKeyEvent(KeyEvent event) {'):
        if signature in java.read_text(): once(java, signature, signature+'\n                    if (vcStylusIntercept(event)) return true;')
    once(host,'mod adaptive_cursor;','mod adaptive_cursor;\nmod stylus_wheel;')
    once(host,'    ime: ime_bridge::ime::ImeBridge,','''    ime: ime_bridge::ime::ImeBridge,
    stylus_wheel: stylus_wheel::Wheel,
    stylus_device_scan_at: std::time::Instant,''')
    once(host,'    fn files_dir(&self) -> Result<String, String> {', '''    fn vc_stylus_get_layout(&self) -> Result<String, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("vcStylusGetLayout"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(String::new()); }
            let value = JString::cast_local(env, result)?;
            value.try_to_string(env)
        }).map_err(|e| e.to_string())
    }
    fn vc_stylus_set_layout(&self, layout: &str) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.new_string(layout)?;
            let object = JObject::from(value);
            env.call_method(&*activity, jni_str!("vcStylusSetLayout"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&object)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
    fn vc_stylus_set_enabled(&self, enabled: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcStylusSetEnabled"), jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
    fn vc_stylus_enabled(&self) -> Result<bool, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcStylusEnabled"), jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| e.to_string())
    }
    fn vc_stylus_poll(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("vcStylusPoll"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }
    fn vc_stylus_device_ids(&self) -> Result<Vec<i32>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Vec<i32>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("vcStylusDeviceIds"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if value.is_null() { return Ok(Vec::new()); }
            let value = JString::cast_local(env, value)?;
            let ids: String = value.try_to_string(env)?;
            Ok(ids.split(',').filter_map(|s| s.parse::<i32>().ok()).collect())
        }).map_err(|e| e.to_string())
    }
    fn files_dir(&self) -> Result<String, String> {''')
    once(host,'                ime: ime_bridge::ime::ImeBridge::new(&app_bridge.app),','''                ime: ime_bridge::ime::ImeBridge::new(&app_bridge.app),
                stylus_wheel: {
                    let enabled = app_bridge.vc_stylus_enabled().unwrap_or(false);
                    android_activity::vc_stylus_configure(enabled, &app_bridge.vc_stylus_device_ids().unwrap_or_default());
                    let mut wheel = stylus_wheel::Wheel::new(enabled);
                    if let Ok(layout) = app_bridge.vc_stylus_get_layout() { wheel.set_layout_string(&layout); }
                    wheel
                },
                stylus_device_scan_at: std::time::Instant::now(),''')
    once(host,'        self.inner.raw_input_hook(ctx, raw);','''        let wheel_blocked = self.inner.session.active().is_none()
            || self.inner.session.tool_wants_text() || ctx.text_edit_focused()
            || self.inner.ui.dialog.is_some() || self.inner.ui.palette_open
            || egui::Popup::is_any_open(ctx);
        if self.stylus_wheel.enabled && self.stylus_device_scan_at.elapsed() > std::time::Duration::from_secs(2) {
            if let Ok(ids) = self.bridge.vc_stylus_device_ids() { android_activity::vc_stylus_configure(true, &ids); }
            self.stylus_device_scan_at = std::time::Instant::now();
        }
        for code in android_activity::vc_stylus_native_take() {
            if !wheel_blocked { self.stylus_wheel.signal(if code == 19 { "D" } else { "S" }, ctx); }
        }
        for _ in 0..12 {
            match self.bridge.vc_stylus_poll() {
                Ok(Some(signal)) => if !wheel_blocked { self.stylus_wheel.signal(&signal, ctx); },
                _ => break,
            }
        }
        self.stylus_wheel.capture(ctx, raw, wheel_blocked);
        self.inner.raw_input_hook(ctx, raw);''')
    once(host,'        self.inner.ui(ui);','''        if let Some(action) = self.stylus_wheel.take_action() {
            if action.starts_with("edit.") {
                if let Err(error) = self.inner.run(action, serde_json::json!({})) { log::warn!("Wheel: {error}"); }
            } else { self.inner.select_tool(action); }
        }
        vectorcraft_ui_egui::menus::set_android_wheel_enabled(self.stylus_wheel.enabled);
        self.inner.ui(ui);
        self.stylus_wheel.render(ui);
        if let Some(layout) = self.stylus_wheel.take_layout_change() {
            if let Err(error) = self.bridge.vc_stylus_set_layout(&layout) {
                log::warn!("Wheel layout could not be saved: {error}");
            }
        }''')
    once(host,'        let menu = vectorcraft_ui_egui::menus::take_android_menu_bits();','''        let menu = vectorcraft_ui_egui::menus::take_android_menu_bits();
        if menu & 512 != 0 {
            self.stylus_wheel.open_customizer(ui.ctx());
        }
        if menu & 256 != 0 {
            let enabled = !self.stylus_wheel.enabled;
            match self.bridge.vc_stylus_set_enabled(enabled) {
                Ok(()) => {
                    self.stylus_wheel.toggle(enabled, ui.ctx());
                    android_activity::vc_stylus_configure(enabled, &self.bridge.vc_stylus_device_ids().unwrap_or_default());
                }
                Err(error) => log::warn!("Wheel preference: {error}"),
            }
        }''')
    # The branded Vc icon uses its own compact menu rendered directly in
    # menus.rs (patch_vc_icon_menu_v021.py). The upstream menu tree is NOT
    # painted when the owner taps Vc. Register actions in the visible menu too.
    once(ui/'menus.rs',
        '''            ui.separator();
            if ui.button("Touch Shortcut Pad").clicked() {''',
        '''            ui.separator();
            let mut wheel_enabled = ANDROID_WHEEL_ENABLED.load(std::sync::atomic::Ordering::Acquire);
            if ui.checkbox(&mut wheel_enabled, "Stylus Wheel").changed() {
                clicked = Some(("android.vectorcraft.stylusWheel".into(), serde_json::json!({})));
                ui.close();
            }
            if ui.button("Customize Stylus Wheel…").clicked() {
                clicked = Some(("android.vectorcraft.stylusWheelCustomize".into(), serde_json::json!({})));
                ui.close();
            }
            ui.separator();
            if ui.button("Touch Shortcut Pad").clicked() {''')
    # Preserve upstream tree registration for other menus and native parity.
    once(ui/'menus/tree.rs', '"Vc",\n            vec![', '"Vc",\n            vec![\n                c("Stylus Wheel", "android.vectorcraft.stylusWheel"),\n                c("Customize Stylus Wheel…", "android.vectorcraft.stylusWheelCustomize"),')
    once(ui/'menus/run.rs','            "android.vectorcraft.fontImport" => 1,','''            "android.vectorcraft.stylusWheel" => 256,
            "android.vectorcraft.stylusWheelCustomize" => 512,
            "android.vectorcraft.fontImport" => 1,''')
    once(ui/'menus/state.rs','        "android.vectorcraft.startupUpdates" =>', '''        "android.vectorcraft.stylusWheel" => return Some(super::ANDROID_WHEEL_ENABLED.load(std::sync::atomic::Ordering::Acquire)),
        "android.vectorcraft.startupUpdates" =>''')
    with (ui/'menus.rs').open('a') as f: f.write('''
#[cfg(target_os = "android")]
static ANDROID_WHEEL_ENABLED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
#[cfg(target_os = "android")]
pub fn set_android_wheel_enabled(enabled: bool) {
    ANDROID_WHEEL_ENABLED.store(enabled, std::sync::atomic::Ordering::Release);
}
''')
    # Android.6 had the raw touch centroid fallback only when egui lacked
    # multi_touch(), but wheel() also includes native/synthetic scrolling.
    # For consistent finger-following motion use measured raw centroid deltas
    # when present, native multi_touch translation otherwise; do not add both.
    once(ui/'canvas/input.rs',
         'if active && !has_native_multi_touch { translated } else { egui::Vec2::ZERO }',
         'if active { translated } else { egui::Vec2::ZERO }')
    once(ui/'canvas/input.rs',
         'let (touches, has_native_multi_touch) = ui.input(|input| {',
         'let (touches, _has_native_multi_touch) = ui.input(|input| {')
    # Keep the upstream wheel's pinch zoom unchanged.
    once(ui/'canvas/input.rs','''    if let Some(native_pan) = ui.input(|i| i.multi_touch().map(|t| t.translation_delta)) {
        scroll.y -= 2.0 * native_pan.y;
    } else {
        scroll.x += early_pan.x;
        scroll.y -= early_pan.y;
    }''','''    // Touchscreen and trackpad must not share an invert/scroll accumulator.
    // For a real two-contact canvas gesture the content follows the contact
    // centroid in X and Y: swipe left/up => artwork left/up. egui wheel()
    // may also contain smooth synthetic scroll, so REPLACE that scroll for
    // this touch gesture instead of adding it and double-panning.
    let native_canvas_touch = ui.input(|i| i.multi_touch())
        .filter(|t| rect.contains(t.center_pos));
    if early_two_touch_on_canvas || native_canvas_touch.is_some() {
        scroll = if early_pan != egui::Vec2::ZERO {
            early_pan
        } else {
            native_canvas_touch.map_or(egui::Vec2::ZERO, |t| t.translation_delta)
        };
    }''')
    # The final hook follows android-activity copying, after winit restoration.
    for name in ('patch_android8_wheel_touch.py', 'patch_android8_ime_reset.py', 'stylus_native.rs'):
        shutil.copyfile(src/name, root/'tools'/name)
    sh=root/'lib/build-common.sh'
    anchor='cp -a "$ROOT/vendor/android-activity" "$SRC/vendor/android-activity"\n'
    once(sh, anchor, anchor + 'if [ "$APP" = "vectorcraft" ]; then\n    python3 "$ROOT/tools/patch_android8_wheel_touch.py" "$SRC" --vendor\n    python3 "$ROOT/tools/patch_android8_ime_reset.py" "$SRC" --vendor\nfi\n')
    print('PASS: Proposal A wheel and same-direction touchscreen pan staged')

def vendor(root):
    lib=root/'vendor/android-activity/src/lib.rs'; native=root/'vendor/android-activity/src/native_activity/mod.rs'
    if 'vc_stylus_configure' in lib.read_text(): raise ValueError('duplicate native wheel')
    with lib.open('a') as f: f.write((Path(__file__).parent/'stylus_native.rs').read_text())
    once(native,'            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {','''
                if let ndk::event::InputEvent::KeyEvent(ref key) = ndk_event {
                    let raw = key.ptr().as_ptr();
                    let id = unsafe { ndk_sys::AInputEvent_getDeviceId(raw) };
                    let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(raw) };
                    let action = unsafe { ndk_sys::AKeyEvent_getAction(raw) };
                    let repeat = unsafe { ndk_sys::AKeyEvent_getRepeatCount(raw) };
                    if crate::vc_stylus_native_capture(id, code, action, repeat) {
                        queue.finish_event(ndk_event, true);
                        return true;
                    }
                }
            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {''')
    print('PASS: verified-pen-only native wheel queue installed')

if __name__=='__main__':
    (vendor if '--vendor' in sys.argv else patch)(Path(sys.argv[1]))
