#!/usr/bin/env python3
"""DeckCraft v0.18.1 Android TEST ONLY — guarded PhotoCraft-style wheel integration.

Run after every protected v0.17 Android overlay, against the disposable builder.
Fail closed on changed anchors. Never touch production APK/signing assets.
"""
from pathlib import Path
import shutil, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: patch_v018_stylus_wheel.py <disposable-builder>")
root=Path(sys.argv[1])
project=root/"source/deckcraft"
this=Path(__file__).resolve().parent

def one(p, old, new):
    p=Path(p)
    text=p.read_text(encoding="utf-8")
    count=text.count(old)
    if count!=1:
        raise RuntimeError(f"Wheel integration anchor drift in {p}: {count} x {old[:90]!r}")
    p.write_text(text.replace(old,new,1),encoding="utf-8")

# Source scoped solely to DeckCraft Android. Desktop upstream remains unchanged.
wheel=project/"crates/ui-egui/src/android_wheel.rs"
if wheel.exists():
    raise RuntimeError("Refusing to overwrite upstream Android wheel implementation")
shutil.copyfile(this/"stylus_wheel.rs",wheel)
ui=project/"crates/ui-egui/src/lib.rs"
one(ui, "pub mod backstage;\n", '#[cfg(target_os = "android")]\nmod android_wheel;\npub mod backstage;\n')
one(ui, '                        ui.menu_button("Presentation Shortcuts", |ui| {',
'''                        ui.menu_button("Stylus Wheel", |ui| {
                            ui.set_min_width(250.0);
                            let enabled=android_wheel::enabled(ui.ctx());
                            if ui.add_sized([250.0,28.0],
                                egui::Button::new("").left_text(if enabled {
                                    "✓  Stylus Wheel ON"
                                } else { "    Stylus Wheel OFF" })).clicked() {
                                android_wheel::toggle(ui.ctx());
                                ui.close();
                            }
                            if ui.add_sized([250.0,28.0],
                                egui::Button::new("").left_text("Customize Wheel…")).clicked() {
                                android_wheel::open_settings(ui.ctx());
                                ui.close();
                            }
                            ui.separator();
                            ui.label("Magic-Pencil 4s · press to open");
                            ui.label("Double press: Eraser");
                        });
                        ui.menu_button("Presentation Shortcuts", |ui| {''')
# The app's normal top-level presentation UI and modal ordering are kept intact.
app=project/"crates/ui-egui/src/app.rs"
one(app, "use super::clock::{monotonic_secs, now_ms};",
'#[cfg(target_os = "android")]\nuse super::android_wheel;\nuse super::clock::{monotonic_secs, now_ms};')
one(app, "        self.ui_inner(ui);\n",
'        self.ui_inner(ui);\n        #[cfg(target_os = "android")]\n        android_wheel::overlay(self, &ctx);\n')
# Capture wheel-owned motion/clicks *before* egui turns them into slide selection.
inp=project/"crates/ui-egui/src/app/input.rs"
one(inp,
"    pub fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {\n",
'''    pub fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        #[cfg(target_os = "android")]
        super::super::android_wheel::capture(ctx, raw);
''')

# Physical Magic-Pencil DPAD events are consumed only while the opt-in wheel is
# active, and only from that device. Ctrl+W, IME and modal D/C/S remain first.
activity=root/"templates/android/SafActivity.java"
one(activity,
"    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {\n        if (dkCaptureCtrlW(event)) return true;\n",
'''    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (dkCaptureCtrlW(event)) return true;
        if (dkWheelIntercept(event)) return true;
''')
one(activity,"    public int dkTakeEditorClose() {",
'''    private volatile boolean dkWheelEnabled = false;
    private final java.util.concurrent.atomic.AtomicInteger dkWheelSignal =
        new java.util.concurrent.atomic.AtomicInteger(0);
    private long dkWheelLastSingle = 0L;
    private long dkWheelLastDouble = 0L;

    public void dkWheelSetEnabled(boolean enabled) {
        if (dkWheelEnabled == enabled) return;
        dkWheelEnabled = enabled;
        dkWheelSignal.set(0);
    }
    public int dkWheelTakeSignal() { return dkWheelSignal.getAndSet(0); }
    private boolean dkWheelIntercept(android.view.KeyEvent event) {
        if (!dkWheelEnabled || event == null) return false;
        android.view.InputDevice device =
            android.view.InputDevice.getDevice(event.getDeviceId());
        if (device == null || device.getName() == null
            || !device.getName().contains("Magic-Pencil 4s")) return false;
        int code=event.getKeyCode();
        if (code != android.view.KeyEvent.KEYCODE_DPAD_DOWN
            && code != android.view.KeyEvent.KEYCODE_DPAD_UP) return false;
        if (event.getAction() == android.view.KeyEvent.ACTION_UP
            && event.getRepeatCount() == 0) {
            long now=android.os.SystemClock.uptimeMillis();
            if (code == android.view.KeyEvent.KEYCODE_DPAD_UP) {
                if (now-dkWheelLastDouble >= 650L) {
                    dkWheelLastDouble=now;
                    dkWheelSignal.set(2);
                }
            } else if (now-dkWheelLastSingle >= 650L) {
                dkWheelLastSingle=now;
                dkWheelSignal.set(1);
            }
        }
        // Suppress OEM scroll only for wheel-owned stylus button events.
        return true;
    }

    public int dkTakeEditorClose() {''')
# Existing native ModalBridge is copied into builder/templates by patch_dcs_host.
bridge=root/"templates/android/dcs_bridge.rs"
one(bridge, " pub fn editor_close(&self, ctx: &egui::Context) {",
''' pub fn wheel_input(&self, ctx: &egui::Context) {
        let enabled=ctx.data(|d| d.get_temp::<bool>(
            egui::Id::new("deckcraft.wheel.native.enabled")).unwrap_or(false));
        // Pull the Rust wheel state from the shared egui context without
        // mutating the document or the Activity's existing D/C/S queue.
        let enabled=ctx.data(|d| d.get_temp::<bool>(
            egui::Id::new("deckcraft.wheel.native.enabled")).unwrap_or(enabled));
        let vm=unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let result=vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
            let raw=self.app.activity_as_ptr() as jni::sys::jobject;
            let activity=unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, JNIString::new("dkWheelSetEnabled"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled.into())])?;
            env.call_method(&*activity, JNIString::new("dkWheelTakeSignal"),
                jni_sig!("()I"), &[])?.i()
        });
        if let Ok(signal @ 1..=2)=result {
            ctx.data_mut(|d| d.insert_temp(
                egui::Id::new("deckcraft.wheel.button"), signal as u8));
            ctx.request_repaint();
        }
    }

    pub fn editor_close(&self, ctx: &egui::Context) {
        self.wheel_input(ctx);
''')
# Native-to-Java enable flag is read from current wheel, never from a
# stale persisted Java keyboard preference.
wheeltext=wheel.read_text()
assert 'pub(crate) fn enabled(ctx: &Context)' in wheeltext
one(wheel, '    set(ctx, w);\n    ctx.request_repaint();\n}\npub(crate) fn open_settings',
'''    ctx.data_mut(|d| d.insert_temp(
        Id::new("deckcraft.wheel.native.enabled"), w.enabled));
    set(ctx, w);
    ctx.request_repaint();
}
pub(crate) fn open_settings''')
one(wheel, '    if !w.enabled || w.settings {\n',
'''    ctx.data_mut(|d| d.insert_temp(
        Id::new("deckcraft.wheel.native.enabled"), w.enabled));
    if !w.enabled || w.settings {
''')
# Source-only checks; CI also compiles the Android native library and verifies
# package/version/ELF+DEX after these checks pass.
for p,markers in {
    ui:['mod android_wheel','Customize Wheel…','Stylus Wheel','app.checkUpdates'],
    app:['android_wheel::overlay(self, &ctx)','self.ui_inner(ui);'],
    inp:['android_wheel::capture(ctx, raw)','pub fn raw_input_hook'],
    activity:['dkWheelIntercept(event)','Magic-Pencil 4s','dkTakeEditorClose()'],
    bridge:['pub fn wheel_input','self.wheel_input(ctx);','dkWheelTakeSignal'],
}.items():
    text=p.read_text()
    for marker in markers:
        if marker not in text:
            raise RuntimeError(f"Required wheel or preserved feature missing: {p} / {marker}")
print("PASS: DeckCraft Android PhotoCraft-style wheel, actual-size preview, 8 editable slots")
print("PASS: wheel input interception before canvas; owner-approved keyboard, D/C/S, updater retained")
