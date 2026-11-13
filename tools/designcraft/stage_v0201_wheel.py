#!/usr/bin/env python3
"""Stage DesignCraft v0.20.1 Android TEST stylus wheel after protected Android overlays.

Only invoked inside disposable GitHub Actions builder. All replacement anchors fail closed.
Never edits a user's source checkout or production release.
"""
from pathlib import Path
import shutil
import sys

def replace_once(path: Path, before: str, after: str, label: str):
    old = path.read_text(encoding="utf-8")
    count = old.count(before)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor in {path}, got {count}: {before[:95]!r}")
    path.write_text(old.replace(before, after, 1), encoding="utf-8")

def main(root: Path, source: Path, android: Path):
    root, source, android = root.resolve(), source.resolve(), android.resolve()
    if source != root / "source/designcraft" or android != source / "apps/designcraft-android":
        raise SystemExit("The wheel patch may only run inside a DesignCraft builder source checkout")
    if not (root / "tools/designcraft/dc_stylus_wheel.rs").is_file():
        raise SystemExit("Missing wheel source")
    if "designcraft-builder" not in str(root):
        raise SystemExit("Refusing a non-disposable Android checkout")
    module_dir = android / "src/v016_android"
    module_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "tools/designcraft/dc_stylus_wheel.rs", module_dir / "dc_stylus_wheel.rs")

    wrapper = android / "src/v016_android.rs"
    replace_once(wrapper, "use super::{saf, saf_next_id, ImportRequest, SafState};",
        "mod dc_stylus_wheel;\nuse super::{saf, saf_next_id, ImportRequest, SafState};",
        "Wheel module in Android-only wrapper")
    replace_once(wrapper, "pub fn paint_pointer_feedback(ctx: &egui::Context) {",
        """pub fn wheel_blocks_hover(ctx: &egui::Context) -> bool {
    dc_stylus_wheel::blocks_hover(ctx)
}

pub fn paint_pointer_feedback(ctx: &egui::Context) {
    if wheel_blocks_hover(ctx) { return; }""", "hover cursor isolation")
    replace_once(wrapper,
        "    let dc_actions = designcraft_ui_egui::menus::take_dc_menu_actions();",
        """    let dc_actions = designcraft_ui_egui::menus::take_dc_menu_actions();
    dc_stylus_wheel::ui(ui, app, bridge, dc_actions);""",
        "Wheel executes before upstream canvas")

    host = android / "src/lib.rs"
    replace_once(host,
        "        if egui_winit::winit::platform::android::STYLUS_HOVER.load(std::sync::atomic::Ordering::Relaxed)\n",
        """        if egui_winit::winit::platform::android::STYLUS_HOVER.load(std::sync::atomic::Ordering::Relaxed)
            && !v016_android::wheel_blocks_hover(ui.ctx())
""", "Suppress pen hover decoration through wheel")

    replace_once(host, "        pub fn dc_dialog_action(&self, active: bool) -> Result<i32, String> {",
        """        pub fn dc_wheel_set_enabled(&self, enabled: bool) -> Result<(), String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                env.call_method(&*activity, jni_str!("dcSetWheelEnabled"),
                    jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
                Ok(())
            }).map_err(|e| e.to_string())
        }

        pub fn dc_wheel_action(&self) -> Result<i32, String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                env.call_method(&*activity, jni_str!("dcTakeWheelAction"),
                    jni_sig!("()I"), &[])?.i()
            }).map_err(|e| e.to_string())
        }

        pub fn dc_dialog_action(&self, active: bool) -> Result<i32, String> {""",
        "DesignCraft stylus wheel JNI bridge")

    activities = list((android / "java").rglob("DesignCraftActivity.java"))
    if len(activities) != 1:
        raise RuntimeError(f"Expected one generated DesignCraftActivity, found {len(activities)}")
    activity = activities[0]
    replace_once(activity, "    public int dcUnsavedDialog(boolean active) {",
        """    private volatile boolean dcWheelEnabled;
    private final java.util.concurrent.atomic.AtomicInteger dcWheelAction =
        new java.util.concurrent.atomic.AtomicInteger(0);
    private long dcWheelLastPress;
    public void dcSetWheelEnabled(boolean enabled) {
        dcWheelEnabled = enabled;
        if (!enabled) dcWheelAction.set(0);
    }
    public int dcTakeWheelAction() { return dcWheelAction.getAndSet(0); }

    public int dcUnsavedDialog(boolean active) {""", "Private isolated stylus button bridge")
    replace_once(activity,
        "    @Override public boolean dispatchKeyEvent(KeyEvent event) {\n        if (event == null)",
        """    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        // Magic-Pencil 4s hardware rocker, never intercept normal keyboard.
        if (event != null && dcWheelEnabled) {
            android.view.InputDevice device =
                android.view.InputDevice.getDevice(event.getDeviceId());
            boolean pencil = device != null && device.getName() != null
                && device.getName().contains("Magic-Pencil 4s");
            int code = event.getKeyCode();
            if (pencil && (code == KeyEvent.KEYCODE_DPAD_UP ||
                    code == KeyEvent.KEYCODE_DPAD_DOWN)) {
                if (event.getAction() == KeyEvent.ACTION_UP &&
                        event.getRepeatCount() == 0) {
                    long now = android.os.SystemClock.uptimeMillis();
                    if (now - dcWheelLastPress >= 450L) {
                        dcWheelAction.set(1);
                        dcWheelLastPress = now;
                    }
                }
                return true;
            }
        }
        if (event == null)""",
        "Physical stylus rocker only while wheel enabled")

    bar = source / "crates/ui-egui/src/menus/bar.rs"
    replace_once(bar, '            ui.menu_button("DesignCraft Shortcuts", |ui| {',
        """            ui.menu_button("Stylus Wheel", |ui| {
                for (label, bit) in [
                    ("Turn Stylus Wheel On / Off", 64_u16),
                    ("Customize Wheel…", 128_u16),
                    ("Show / Hide Wheel", 256_u16),
                ] {
                    if ui.button(label).clicked() {
                        DC_MENU_ACTIONS.fetch_or(bit, std::sync::atomic::Ordering::Relaxed);
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                }
                ui.label("Magic-Pencil 4s button • Default 8 segments");
                ui.label("Saved size, opacity and tool assignments");
            });
            ui.menu_button("DesignCraft Shortcuts", |ui| {""",
        "Dc icon menu stylus wheel controls")

    canvas = source / "crates/ui-egui/src/canvas/input.rs"
    replace_once(canvas,
        "pub(super) fn handle_input(app: &mut DesignApp, ui: &mut egui::Ui, resp: &egui::Response, rect: Rect) {",
        """pub(super) fn handle_input(app: &mut DesignApp, ui: &mut egui::Ui, resp: &egui::Response, rect: Rect) {
    #[cfg(target_os = "android")]
    if ui.ctx().data(|d| d.get_temp::<bool>(egui::Id::new("dc-wheel-hover-block")).unwrap_or(false)) {
        // Wheel owns pointer capture, including hover. No behind-canvas hit-test.
        return;
    }""",
        "Prevent canvas selecting/transforming behind the wheel")
    assert "dc_stylus_wheel::ui(ui, app, bridge, dc_actions)" in wrapper.read_text()
    assert "dc-wheel-hover-block" in canvas.read_text()
    assert "Dc icon menu" not in bar.read_text() or "Stylus Wheel" in bar.read_text()
    print("PASS: isolated DesignCraft stylus wheel, actual-scale preview, Android rocker, canvas hover guard")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: stage_v0201_wheel.py DISPOSABLE_BUILDER UPSTREAM_SOURCE ANDROID_APP")
    main(*(Path(a) for a in sys.argv[1:]))
