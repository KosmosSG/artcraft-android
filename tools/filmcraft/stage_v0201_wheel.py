#!/usr/bin/env python3
"""FilmCraft v0.20.1-only wheel staging; changes disposable CI builder, not published app.

The original v0.19 Android overlay remains the protected baseline. This
adds a separate foreground egui module and intercepting control surface.
All replacements are single-anchor and fail closed on upstream/builder drift.
"""
from pathlib import Path
import argparse
from render_approved_fc_mark import render_logo

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
    (project / "src" / "filmcraft_fc_logo.rgba").write_bytes(
        Path(__file__).with_name("filmcraft_fc_logo.rgba").read_bytes())
''' + RUNTIME_WRITE_ANCHOR
FEATURE_ANCHOR = "impl FilmcraftFeatures {\n"
FEATURE_ADD = FEATURE_ANCHOR + "    pub fn storage_dir(&self) -> Option<PathBuf> { self.app_dir.clone() }\n"
HEADER_ANCHOR = '                ui.menu_button("FilmCraft Shortcuts", |ui| {'
HEADER_ADD = '''                ui.menu_button("Stylus Wheel", |ui| {
                    let mut enabled = ui.ctx().data(|data| data.get_temp::<bool>(
                        egui::Id::new("filmcraft.stylus.enabled")).unwrap_or(true));
                    if ui.checkbox(&mut enabled, "Enable Stylus Wheel")
                        .on_hover_cursor(egui::CursorIcon::PointingHand).changed() {
                        ui.ctx().data_mut(|data| data.insert_temp(
                            egui::Id::new("filmcraft.stylus.menu.enabled"), enabled));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                    if ui.button("Customize Wheel…")
                        .on_hover_cursor(egui::CursorIcon::PointingHand).clicked() {
                        ui.ctx().data_mut(|data| data.insert_temp(
                            egui::Id::new("filmcraft.stylus.settings.open"), true));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                });
''' + HEADER_ANCHOR

# The Android bridge already supports genuine in-app download/verify/install.
# Show the official release checker only; that check offers download on user
# approval, and verified downloads offer Android-approved installation.
# Keep package identity and signer checks for production and .test isolation.
# Keep download and install functionality behind Check for Updates, but do
# not clutter Fc > App Updates with separate administrative commands.
HEADER_DOWNLOAD_ANCHOR = 'action(ui, "Download Verified APK…", 8);'
HEADER_DOWNLOAD_LABEL = '// Verified download offered by Check for Updates dialog.'
HEADER_INSTALL_ANCHOR = 'action(ui, "Install Verified Download…", 10);'
HEADER_INSTALL_LABEL = '// Install offered only after verification and Android approval.'
HEADER_RELEASE_ANCHOR = 'action(ui, "Open Official Release Page…", 6);'
HEADER_RELEASE_LABEL = '// Release information is included in verified update metadata.'



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
        RUNTIME_EXTRA.replace("JAVA_STYLUS_BRIDGE", repr(JAVA_STYLUS_BRIDGE))
        + RUNTIME_ANCHOR, "runtime wrapper hook")
    updated_runtime = replace_once(updated_runtime, RUNTIME_WRITE_ANCHOR,
        RUNTIME_WRITE_REPLACE, "wheel Rust copy")
    compile(updated_runtime, str(runtime), "exec")
    feature_src = replace_once(feature.read_text(), FEATURE_ANCHOR, FEATURE_ADD, "settings path")
    header_src = replace_once(header.read_text(), HEADER_ANCHOR, HEADER_ADD, "Fc menu")
    header_src = replace_once(header_src, HEADER_DOWNLOAD_ANCHOR,
        HEADER_DOWNLOAD_LABEL, "in-app verified APK download menu")
    header_src = replace_once(header_src, HEADER_INSTALL_ANCHOR,
        HEADER_INSTALL_LABEL, "in-app Android installer menu")
    header_src = replace_once(header_src, HEADER_RELEASE_ANCHOR,
        HEADER_RELEASE_LABEL, "redundant official release page menu")
    for hidden in (HEADER_DOWNLOAD_ANCHOR, HEADER_INSTALL_ANCHOR, HEADER_RELEASE_ANCHOR,
                   "Download & Verify APK in App…",
                   "Install Verified APK (Android Approval)…"):
        if hidden in header_src:
            raise RuntimeError(f"STOP: FilmCraft exposed redundant update action: {hidden}")
    if 'action(ui, "Check for Updates…", 4);' not in header_src:
        raise RuntimeError("STOP: single visible update check entry missing")
    # Check all changes first; do not partially modify the builder on an anchor failure.
    runtime.write_text(updated_runtime)
    feature.write_text(feature_src)
    header.write_text(header_src)
    icon = Path(__file__).with_name("fc-original-launcher-mask.b64")
    if not icon.is_file():
        raise RuntimeError("STOP: original FilmCraft Fc mark missing")
    logo_file = builder / "tools/filmcraft/filmcraft_fc_logo.rgba"
    navy, lavender = render_logo(icon, logo_file)
    wheel_source = wheel.read_text()
    palette = {
        "const NAVY: Color32 = Color32::from_rgb(0x00, 0x04, 0x7a);":
            f"const NAVY: Color32 = Color32::from_rgb({navy[0]}, {navy[1]}, {navy[2]});",
        "const LAVENDER: Color32 = Color32::from_rgb(0x9a, 0x9c, 0xd9);":
            f"const LAVENDER: Color32 = Color32::from_rgb({lavender[0]}, {lavender[1]}, {lavender[2]});",
        "const ACCENT: Color32 = Color32::from_rgb(0x36, 0x4c, 0xd9);":
            "const ACCENT: Color32 = Color32::from_rgb(" +
            ", ".join(str(round(navy[i]*0.58+lavender[i]*0.42)) for i in range(3)) + ");",
    }
    for original, new in palette.items():
        if wheel_source.count(original) != 1:
            raise RuntimeError("STOP: owner-approved Fc palette source drift")
        wheel_source = wheel_source.replace(original, new, 1)
    (builder / "tools/filmcraft/filmcraft_stylus_wheel.rs").write_text(wheel_source)
    print(f"PASS: user-supplied original Fc lettering verified; exact navy {navy} lavender {lavender}")
    print("PASS: PhotoCraft Fc menu with one update-check action; download/install confirmation retained internally")


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
        # Exercise the real approved icon without altering any GitHub files.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as scratch:
            icon = Path(__file__).with_name("fc-original-launcher-mask.b64")
            navy, lavender = render_logo(icon, Path(scratch) / "logo.rgba")
            assert lavender[0] > navy[0] + 50
            assert (Path(scratch) / "logo.rgba").stat().st_size == 40960
        print("FilmCraft wheel, icon and updater staging guard self-test PASS")
        return
    if args.builder is None:
        parser.error("disposable builder path required")
    wheel = Path(__file__).with_name("filmcraft_stylus_wheel.rs")
    prepare(args.builder.resolve(), wheel)


if __name__ == "__main__":
    main()
