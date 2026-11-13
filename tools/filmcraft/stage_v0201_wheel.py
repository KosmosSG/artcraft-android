#!/usr/bin/env python3
"""FilmCraft v0.20.1-only wheel staging; changes disposable CI builder, not published app.

The original v0.19 Android overlay remains the protected baseline. This
adds a separate foreground egui module and intercepting control surface.
All replacements are single-anchor and fail closed on upstream/builder drift.
"""
from pathlib import Path
import argparse

RUNTIME_ANCHOR = "    return rust, java, manifest\n"
JAVA_STYLUS_BRIDGE = '''    // FilmCraft-only Magic-Pencil 4s input bridge. Never change GameActivity's
    // normal finger, touchpad, pointer or physical keyboard forwarding.
    private volatile boolean fcWheelEnabled = false;
    private volatile boolean fcWheelHovering = false;
    private volatile long fcWheelHoverAt = 0L;
    private long fcWheelLastButton = 0L;
    private final java.util.concurrent.atomic.AtomicInteger fcWheelSignal =
        new java.util.concurrent.atomic.AtomicInteger();
    private final java.util.concurrent.atomic.AtomicLong fcWheelHover =
        new java.util.concurrent.atomic.AtomicLong();
    public void fcWheelSetEnabled(boolean enabled) {
        fcWheelEnabled = enabled;
        if (!enabled) fcWheelSignal.set(0);
    }
    public int fcWheelTakeSignal() { return fcWheelSignal.getAndSet(0); }
    public long fcWheelTakeHover() { return fcWheelHover.getAndSet(0L); }
    private void fcWheelButton() {
        long now = android.os.SystemClock.uptimeMillis();
        if (!fcWheelEnabled || !fcWheelHovering || now-fcWheelHoverAt > 1800L)
            return;
        if (now-fcWheelLastButton < 350L) return;
        fcWheelLastButton = now;
        fcWheelSignal.set(1);
    }
    private boolean fcWheelKey(android.view.KeyEvent event) {
        if (!fcWheelEnabled || event == null
            || !fcWheelHovering
            || android.os.SystemClock.uptimeMillis()-fcWheelHoverAt > 1800L)
            return false;
        android.view.InputDevice device =
            android.view.InputDevice.getDevice(event.getDeviceId());
        if (device == null || device.getName() == null
            || !device.getName().toLowerCase(java.util.Locale.ROOT).contains("pencil"))
            return false;
        int code = event.getKeyCode();
        if (code != android.view.KeyEvent.KEYCODE_DPAD_DOWN
            && code != android.view.KeyEvent.KEYCODE_DPAD_UP) return false;
        if (event.getAction() == android.view.KeyEvent.ACTION_UP
            && event.getRepeatCount() == 0 && code == android.view.KeyEvent.KEYCODE_DPAD_DOWN)
            fcWheelButton();
        return true; // Only the physically verified pen's side-button.
    }
    private boolean fcWheelMotion(android.view.MotionEvent e) {
        if (e == null || e.getPointerCount() < 1) return false;
        int tool = e.getToolType(0);
        if (tool != android.view.MotionEvent.TOOL_TYPE_STYLUS
            && tool != android.view.MotionEvent.TOOL_TYPE_ERASER) return false;
        int action=e.getActionMasked();
        if (action == android.view.MotionEvent.ACTION_HOVER_EXIT) {
            fcWheelHovering = false;
            fcWheelHover.set(-1L);
        } else if (action == android.view.MotionEvent.ACTION_HOVER_MOVE
                || action == android.view.MotionEvent.ACTION_HOVER_ENTER) {
            float x = e.getX(0), y = e.getY(0);
            if (Float.isFinite(x) && Float.isFinite(y)) {
                fcWheelHovering = true;
                fcWheelHoverAt = android.os.SystemClock.uptimeMillis();
                long packed = (((long)Float.floatToRawIntBits(x)) << 32)
                    | (Float.floatToRawIntBits(y) & 0xffffffffL);
                if (packed != 0L && packed != -1L) fcWheelHover.set(packed);
            }
        } else if (action == android.view.MotionEvent.ACTION_BUTTON_PRESS
                && (e.getActionButton() & android.view.MotionEvent.BUTTON_STYLUS_PRIMARY) != 0
                && fcWheelEnabled && fcWheelHovering) {
            fcWheelButton();
            return true;
        }
        return false;
    }
'''

RUNTIME_EXTRA = '''    rust = require_once(rust, "mod filmcraft_features;",
        "mod filmcraft_features;\\nmod filmcraft_stylus_wheel;", "Wheel module")
    rust = require_once(rust, "    features: filmcraft_features::FilmcraftFeatures,",
        "    features: filmcraft_features::FilmcraftFeatures,\\n    wheel: filmcraft_stylus_wheel::Wheel,",
        "Wheel shell field")
    rust = require_once(rust,
        "let fc_features = filmcraft_features::FilmcraftFeatures::new(&app);",
        "let fc_features = filmcraft_features::FilmcraftFeatures::new(&app);\\n"
        "        let fc_wheel = filmcraft_stylus_wheel::Wheel::new(fc_features.storage_dir());",
        "Wheel constructor")
    rust = require_once(rust, "features: fc_features,",
        "features: fc_features, wheel: fc_wheel,", "Wheel state")
    rust = require_once(rust, "        self.inner.ui(ui, frame);",
        "        self.inner.ui(ui, frame);\\n"
        "        if let Some(command) = self.wheel.show(ui.ctx()) {\\n"
        "            let _ = filmcraft_ui_egui::menus::invoke(\\n"
        "                &mut self.inner, ui.ctx(), command, serde_json::json!({}));\\n"
        "        }", "Wheel command routing")
    rust = require_once(rust,
        "Wheel::new(fc_features.storage_dir());",
        "Wheel::new(fc_features.storage_dir(), &app);", "Hardware wheel Activity handle")
    rust = require_once(rust, "        self.handle_clipboard_shortcuts(raw);",
        "        self.wheel.capture(ctx, raw);\\n        self.handle_clipboard_shortcuts(raw);",
        "Wheel input pre-editor interception")
    java = require_once(java, "public final class FilmCraftActivity extends GameActivity {",
        "public final class FilmCraftActivity extends GameActivity {\\n" + JAVA_STYLUS_BRIDGE,
        "Android native pen button and real hover bridge")
    java = require_once(java,
        "    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {",
        "    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {\\n"
        "        if (fcWheelKey(event)) return true;", "Magic-Pencil side-key isolation")
    import re
    already = re.search(
        r"public boolean dispatchGenericMotionEvent\\(android\\.view\\.MotionEvent\\s+(\\w+)\\)\\s*\\{",
        java)
    if already:
        matched = already.group(0)
        java = require_once(java, matched,
            matched + "\\n        if (fcWheelMotion(" + already.group(1) + ")) return true;",
            "Real stylus hover in existing generic-motion dispatch")
    else:
        java = require_once(java, "    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {",
            "    @Override public boolean dispatchGenericMotionEvent(android.view.MotionEvent e) {\\n"
            "        if (fcWheelMotion(e)) return true;\\n"
            "        return super.dispatchGenericMotionEvent(e);\\n    }\\n"
            "    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {",
            "Real stylus hover generic-motion dispatch")
'''
RUNTIME_WRITE_ANCHOR = '    print("FilmCraft native font/update integration overlaid on generated crate")'
RUNTIME_WRITE_REPLACE = '''    (project / "src" / "filmcraft_stylus_wheel.rs").write_text(
        Path(__file__).with_name("filmcraft_stylus_wheel.rs").read_text())
''' + RUNTIME_WRITE_ANCHOR
FEATURE_ANCHOR = "impl FilmcraftFeatures {\n"
FEATURE_ADD = FEATURE_ANCHOR + "    pub fn storage_dir(&self) -> Option<PathBuf> { self.app_dir.clone() }\n"
HEADER_ANCHOR = '                ui.menu_button("FilmCraft Shortcuts", |ui| {'
HEADER_ADD = '''                ui.menu_button("Stylus Wheel", |ui| {
                    if ui.button("Customize Stylus Wheel…")
                        .on_hover_cursor(egui::CursorIcon::PointingHand).clicked() {
                        ui.ctx().data_mut(|data| data.insert_temp(
                            egui::Id::new("filmcraft.stylus.settings.open"), true));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                });
''' + HEADER_ANCHOR


def replace_once(src: str, old: str, new: str, name: str) -> str:
    if src.count(old) != 1 or new in src:
        raise RuntimeError(f"STOP: FilmCraft {name} missing/ambiguous or patch already applied")
    return src.replace(old, new, 1)


def prepare(builder: Path, wheel: Path) -> None:
    if builder.name != "filmcraft-builder" or not (builder / "lib/build-common.sh").is_file():
        raise RuntimeError("STOP: expected disposable FilmCraft build checkout")
    if not wheel.is_file():
        raise RuntimeError("STOP: missing isolated FilmCraft wheel Rust module")
    runtime = builder / "tools/filmcraft/runtime_patch.py"
    feature = builder / "tools/filmcraft/filmcraft_features_v019_bottom_feedback.rs"
    header = builder / "source/filmcraft/crates/ui-egui/src/header.rs"
    for path in (runtime, feature, header):
        if not path.is_file():
            raise RuntimeError(f"STOP: missing FilmCraft reviewed source {path}")

    runtime_src = runtime.read_text()
    updated_runtime = replace_once(runtime_src, RUNTIME_ANCHOR,
        RUNTIME_EXTRA + RUNTIME_ANCHOR, "runtime wrapper hook")
    updated_runtime = replace_once(updated_runtime, RUNTIME_WRITE_ANCHOR,
        RUNTIME_WRITE_REPLACE, "wheel Rust copy")
    compile(updated_runtime, str(runtime), "exec")
    feature_src = replace_once(feature.read_text(), FEATURE_ANCHOR, FEATURE_ADD, "settings path")
    header_src = replace_once(header.read_text(), HEADER_ANCHOR, HEADER_ADD, "Fc menu")
    # Check all changes first; do not partially modify the builder on an anchor failure.
    runtime.write_text(updated_runtime)
    feature.write_text(feature_src)
    header.write_text(header_src)
    (builder / "tools/filmcraft/filmcraft_stylus_wheel.rs").write_bytes(wheel.read_bytes())
    print("PASS: separate FilmCraft stylus wheel wired to Fc menu, persisted prefs and commands")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        fixture = "before\\n" + RUNTIME_ANCHOR
        assert RUNTIME_EXTRA in replace_once(fixture, RUNTIME_ANCHOR,
            RUNTIME_EXTRA + RUNTIME_ANCHOR, "fixture")
        assert FEATURE_ADD in replace_once(FEATURE_ANCHOR, FEATURE_ANCHOR, FEATURE_ADD, "feature")
        try:
            replace_once("missing", HEADER_ANCHOR, HEADER_ADD, "negative")
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing header must fail closed")
        print("FilmCraft wheel staging guard self-test PASS")
        return
    if args.builder is None:
        parser.error("disposable builder path required")
    wheel = Path(__file__).with_name("filmcraft_stylus_wheel.rs")
    prepare(args.builder.resolve(), wheel)


if __name__ == "__main__":
    main()
