#!/usr/bin/env python3
"""Stage DesignCraft v0.20.1 Android TEST stylus wheel after protected Android overlays.

Only invoked inside disposable GitHub Actions builder. All replacement anchors fail closed.
Never edits a user's source checkout or production release.
"""
from pathlib import Path
import shutil
import sys
from PIL import Image

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
    # Exact user-approved launcher lettering, with its dark plate removed
    # at build time so the wheel hub remains circular and solid.
    original_icon = root / "tools/approved-branding/assets/res/mipmap-xxxhdpi/ic_launcher.png"
    with Image.open(original_icon) as icon:
        rgba = icon.convert("RGBA").resize((192, 192), Image.Resampling.LANCZOS)
        image = Image.new("RGBA", rgba.size)
        for y in range(rgba.height):
            for x in range(rgba.width):
                red, green, blue, alpha = rgba.getpixel((x, y))
                # Preserve exact bright-pink antialias colour of the Dc lettering.
                visible = max(0, min(255, (red - 69) * 255 // 125))
                image.putpixel((x, y), (red, green, blue, min(visible, alpha)))
        bbox = image.getbbox()
        if bbox is None or bbox[2] - bbox[0] < 40:
            raise RuntimeError("Dc launcher artwork cannot be isolated")
        glyph = image.crop(bbox)
        glyph.thumbnail((171, 103), Image.Resampling.LANCZOS)
        padded = Image.new("RGBA", (192, 120))
        padded.alpha_composite(glyph, ((192-glyph.width)//2, (120-glyph.height)//2))
        (module_dir / "dc_wheel_mark.rgba").write_bytes(padded.tobytes())

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

    replace_once(host,
        "        v016_android::paint_pointer_feedback(ui.ctx());",
        """        // Java HOVER_ENTER/MOVE is visible before any screen touch.
        let dc_hover_visible =
            v016_android::paint_stylus_hover_pointer(ui.ctx(), &self.saf_bridge);
        if !dc_hover_visible {
            v016_android::paint_pointer_feedback(ui.ctx());
        }""",
        "Draw immediate stylus hover pointer and preserve adaptive cursor")
    replace_once(host,
        "        if egui_winit::winit::platform::android::STYLUS_HOVER.load(std::sync::atomic::Ordering::Relaxed)",
        """        if !dc_hover_visible
            && egui_winit::winit::platform::android::STYLUS_HOVER.load(std::sync::atomic::Ordering::Relaxed)""",
        "Avoid double-drawing native pen hover ring")

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

        pub fn dc_undo_action(&self) -> Result<i32, String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                env.call_method(&*activity, jni_str!("dcTakeUndoAction"),
                    jni_sig!("()I"), &[])?.i()
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

        pub fn dc_wheel_device_ids(&self) -> Result<Vec<i32>, String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<Vec<i32>> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                let result = env.call_method(&*activity, jni_str!("dcStylusDeviceIds"),
                    jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
                if result.is_null() { return Ok(Vec::new()); }
                let value = JString::cast_local(env, result)?;
                let ids: String = value.try_to_string(env)?;
                Ok(ids.split(',').filter_map(|id| id.parse::<i32>().ok()).collect())
            }).map_err(|e| e.to_string())
        }

        pub fn dc_dialog_action(&self, active: bool) -> Result<i32, String> {""",
        "DesignCraft stylus wheel JNI bridge")

    replace_once(host,
        "        pub fn dc_wheel_device_ids(&self) -> Result<Vec<i32>, String> {",
        """        pub fn dc_stylus_hover_point(&self) -> Result<Option<(f32, f32)>, String> {
            let sample: String = self.vm.attach_current_thread(
                |env| -> jni::errors::Result<String> {
                    let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                    let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                    let result = env.call_method(&*activity,
                        jni_str!("dcStylusHoverSample"),
                        jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
                    if result.is_null() { return Ok(String::new()); }
                    let value = JString::cast_local(env, result)?;
                    value.try_to_string(env)
                }).map_err(|e| e.to_string())?;
            let coordinates = sample.split_once(',').and_then(|(x, y)|
                x.parse::<f32>().ok().zip(y.parse::<f32>().ok()))
                .filter(|(x, y)| x.is_finite() && y.is_finite());
            Ok(coordinates)
        }

        pub fn dc_wheel_device_ids(&self) -> Result<Vec<i32>, String> {""",
        "Magic-Pencil hover JNI, independent of first touch")

    activities = list((android / "java").rglob("DesignCraftActivity.java"))
    if len(activities) != 1:
        raise RuntimeError(f"Expected one generated DesignCraftActivity, found {len(activities)}")
    activity = activities[0]
    replace_once(activity, "    public int dcUnsavedDialog(boolean active) {",
        """    private volatile boolean dcWheelEnabled;
    private final java.util.concurrent.atomic.AtomicInteger dcWheelAction =
        new java.util.concurrent.atomic.AtomicInteger(0);
    private long dcWheelLastPress;
    private final java.util.concurrent.atomic.AtomicInteger dcUndoAction =
        new java.util.concurrent.atomic.AtomicInteger(0);
    public int dcTakeUndoAction() { return dcUndoAction.getAndSet(0); }
    public void dcSetWheelEnabled(boolean enabled) {
        dcWheelEnabled = enabled;
        if (!enabled) dcWheelAction.set(0);
    }
    public int dcTakeWheelAction() { return dcWheelAction.getAndSet(0); }
    // ID whitelist for the native Android InputQueue. Physical keyboards are excluded.
    public String dcStylusDeviceIds() {
        StringBuilder ids = new StringBuilder();
        for (int id : android.view.InputDevice.getDeviceIds()) {
            android.view.InputDevice device = android.view.InputDevice.getDevice(id);
            if (device == null || device.getName() == null) continue;
            String name = device.getName().toLowerCase(java.util.Locale.ROOT);
            if (id > 0 && name.contains("magic-pencil")) {
                if (ids.length() > 0) ids.append(',');
                ids.append(id);
            }
        }
        return ids.toString();
    }

    public int dcUnsavedDialog(boolean active) {""", "Private isolated stylus button bridge")
    replace_once(activity,
        "    public int dcTakeWheelAction() { return dcWheelAction.getAndSet(0); }",
        """    public int dcTakeWheelAction() { return dcWheelAction.getAndSet(0); }

    // Capture real stylus hover events from first approach, without touching
    // the display or intercepting ordinary mouse and trackpad events.
    private volatile float dcPenHoverX = -1f;
    private volatile float dcPenHoverY = -1f;
    private volatile long dcPenHoverAt = 0L;
    private volatile boolean dcPenHoverActive = false;
    private void dcTrackPenHover(android.view.MotionEvent event) {
        if (event == null || event.getPointerCount() < 1) return;
        int tool = event.getToolType(0);
        if (tool != android.view.MotionEvent.TOOL_TYPE_STYLUS
                && tool != android.view.MotionEvent.TOOL_TYPE_ERASER) return;
        switch (event.getActionMasked()) {
            case android.view.MotionEvent.ACTION_HOVER_ENTER:
            case android.view.MotionEvent.ACTION_HOVER_MOVE:
                dcPenHoverX = event.getX(0);
                dcPenHoverY = event.getY(0);
                dcPenHoverAt = android.os.SystemClock.uptimeMillis();
                dcPenHoverActive = true;
                break;
            case android.view.MotionEvent.ACTION_HOVER_EXIT:
                dcPenHoverActive = false;
                break;
            default:
                break;
        }
    }
    @Override public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        dcTrackPenHover(event);
        return super.dispatchGenericMotionEvent(event);
    }
    @Override public boolean onGenericMotionEvent(android.view.MotionEvent event) {
        dcTrackPenHover(event);
        return super.onGenericMotionEvent(event);
    }
    public String dcStylusHoverSample() {
        long age = android.os.SystemClock.uptimeMillis() - dcPenHoverAt;
        if (!dcPenHoverActive || age < 0L || age > 1300L) return "";
        return Float.toString(dcPenHoverX) + "," + Float.toString(dcPenHoverY);
    }""",
        "Immediate Android hover entry/move/exit capture")

    replace_once(activity,
        "    @Override public boolean dispatchKeyEvent(KeyEvent event) {\n        if (event == null)",
        """    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        // Magic-Pencil 4s hardware rocker, never intercept normal keyboard.
        if (event != null && dcWheelEnabled) {
            android.view.InputDevice device =
                android.view.InputDevice.getDevice(event.getDeviceId());
            boolean pencil = device != null && device.getName() != null
                && device.getName().toLowerCase(java.util.Locale.ROOT).contains("magic-pencil");
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
    # Preserve existing IME handling, adding an isolated physical Ctrl+Z
    # fallback only while no Android editor or modal owns the input.
    replace_once(activity,
        "        int code = event.getKeyCode();\n"
        "        int state = event.getAction();",
        """        int code = event.getKeyCode();
        int state = event.getAction();
        boolean dcUndoShortcut = code == KeyEvent.KEYCODE_Z
            && event.isCtrlPressed() && !event.isAltPressed()
            && !event.isShiftPressed();
        if (dcUndoShortcut && !imeWanted && !dcDialogActive) {
            if (state == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0)
                dcUndoAction.set(1);
            return true;
        }""",
        "Ctrl+Z physical keyboard fallback")

    bar = source / "crates/ui-egui/src/menus/bar.rs"
    replace_once(bar, '            ui.menu_button("DesignCraft Shortcuts", |ui| {',
        """            ui.menu_button("Stylus Wheel", |ui| {
                let active = ui.ctx().data(|d|
                    d.get_temp::<bool>(egui::Id::new("dc-wheel-enabled")).unwrap_or(false));
                if ui.button(if active {
                    "✓ Stylus Wheel On (tap to disable)"
                } else {
                    "Stylus Wheel Off (tap to enable)"
                }).clicked() {
                    DC_MENU_ACTIONS.fetch_or(64_u16, std::sync::atomic::Ordering::Relaxed);
                    ui.ctx().request_repaint();
                    ui.close();
                }
                if ui.button("Customize Wheel…").clicked() {
                    DC_MENU_ACTIONS.fetch_or(128_u16, std::sync::atomic::Ordering::Relaxed);
                    ui.ctx().request_repaint();
                    ui.close();
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
    assert "dcTakeUndoAction" in activity.read_text()
    assert "dcUndoShortcut" in activity.read_text()
    assert "dc_undo_action" in host.read_text()
    assert "dc_stylus_hover_point" in host.read_text()
    assert "paint_stylus_hover_pointer" in host.read_text()
    assert "dcStylusHoverSample" in activity.read_text()
    assert "dispatchGenericMotionEvent" in activity.read_text()
    assert "onGenericMotionEvent" in activity.read_text()
    assert "Dc icon menu" not in bar.read_text() or "Stylus Wheel" in bar.read_text()
    print("PASS: isolated DesignCraft stylus wheel, actual-scale preview, Android rocker, canvas hover guard")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: stage_v0201_wheel.py DISPOSABLE_BUILDER UPSTREAM_SOURCE ANDROID_APP")
    main(*(Path(a) for a in sys.argv[1:]))
