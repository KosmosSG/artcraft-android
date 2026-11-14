#!/usr/bin/env python3
"""Targeted CADCraft v0.19.0 Android-only UI compatibility overlay.

Apply only to a separately checked-out official Storytold CADCraft release.
Fail closed on upstream code changes; never modify other Craft apps.
"""
from pathlib import Path
import argparse
import shutil


def apply(source: Path) -> None:
    menu = source / "crates/ui-egui/src/menus.rs"
    original = menu.read_text(encoding="utf-8")
    anchor = "                // Titles first, so a hovered title can take over before any menu is drawn."
    if original.count(anchor) != 1:
        raise SystemExit("CADCraft menu_bar changed upstream: refusing unreviewed patch")
    if "CADCRAFT_ANDROID_CC_MENU_V2" in original:
        raise SystemExit("CADCraft Cc menu already patched: refusing duplicate")

    # The extra menu is Android-only. It does not change CADCraft's desktop menus,
    # native keyboard shortcuts, CAD command registry or reference menu tree.
    # Every menu action reuses an existing CADCraft command, rather than a fake row.
    injected = """                // CADCRAFT_ANDROID_CC_MENU_V2: native-icon compact menu.
                #[cfg(target_os = "android")]
                crate::cadcraft_android_wheel::cc_menu(app, ui, &mut clicked);
"""

    revised = original.replace(anchor, injected + anchor, 1)
    menu.write_text(revised, encoding="utf-8")
    assert revised.count("CADCRAFT_ANDROID_CC_MENU_V2") == 1
    assert "cadcraft_android_wheel::cc_menu" in revised
    print("PASS: native-Cc PhotoCraft-style compact CADCraft Android menu injected.")


def install_cadcraft_updater(reference: Path) -> None:
    """Replace reference-builder updater with a CADCraft-only in-app downloader.

    This affects solely the disposable CADCraft Actions checkout. The reference
    builder's unrelated versions must never be promoted to CADCraft users.
    """
    root = Path(__file__).resolve().parent
    java_source = root / "CadCraftUpdateCheck.java"
    if not java_source.is_file():
        raise SystemExit("Missing reviewed CADCraft Android updater")
    target = reference / "templates/android/UpdateCheck.java"
    original = target.read_text(encoding="utf-8")
    if 'private static final String BUILDER_VERSION = "__BUILDER_VERSION__"' not in original:
        raise SystemExit("Pinned Android builder updater changed; refusing unsafe replacement")
    reviewed = java_source.read_text(encoding="utf-8")
    if ("public static void checkNow(final Activity activity)" not in reviewed
            or "KosmosSG/artcraft-android/releases?" not in reviewed):
        raise SystemExit("CADCraft-only updater code validation failed")
    target.write_text(reviewed, encoding="utf-8")
    builder = reference / "lib/build-common.sh"
    source = builder.read_text(encoding="utf-8")
    needle = 'name = "android.permission.INTERNET"\n'
    if source.count(needle) != 1:
        raise SystemExit("Builder Android permission manifest anchor changed")
    source = source.replace(needle, needle + """
# Allow explicit user-approved APK installation from CADCraft's in-app downloader.
[[package.metadata.android.uses_permission]]
name = "android.permission.REQUEST_INSTALL_PACKAGES"
""", 1)
    builder.write_text(source, encoding="utf-8")
    print("PASS: CADCraft-only GitHub release checker and in-app APK download/installer staged.")



def install_pen_button(reference: Path) -> None:
    """Native-only HONOR pen DPAD routing, guarded by Java-validated device IDs.

    No physical keyboard arrow keys, touch gestures or unrelated Craft apps are
    intercepted. This edits only the CI reference checkout.
    """
    java = reference / "templates/android/SafActivity.java"
    source = java.read_text(encoding="utf-8")
    anchor = "public final class __CLASS__ extends NativeActivity {"
    if source.count(anchor) != 1:
        raise SystemExit("CADCraft pen Activity anchor changed")
    inject = """public final class __CLASS__ extends NativeActivity {
    // Java Activity is the safe classloader boundary for the CAD updater.
    public void cadCheckUpdates() {
        runOnUiThread(() -> {
            try {
                com.artcraft.updater.UpdateCheck.checkNow(this);
            } catch (Throwable failure) {
                Log.e(TAG, "CADCraft updater error", failure);
                try {
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("CADCraft updates")
                        .setMessage("Unable to check for updates. Please try again later.")
                        .setPositiveButton("OK", null).show();
                } catch (Throwable ignored) { }
            }
        });
    }
    // PhotoCraft parity: Java Activity + NativeActivity can receive different
    // routes for the SAME HONOR pen key, depending on IME focus on MagicOS.
    // Only a physically named Magic-Pencil device may enter this queue.
    private volatile boolean cadWheelEnabled = true;
    // The Java Activity name is fixed by the isolated test package.
    // A direct JNI callback bridges the pen's verified release even when
    // querying Java from the Rust render thread is temporarily unavailable.
    private native void cadWheelButtonNative(int code);
    private final java.util.concurrent.ConcurrentLinkedQueue<Integer> cadWheelKeys =
        new java.util.concurrent.ConcurrentLinkedQueue<>();
    private long cadWheelLastDown = 0L, cadWheelLastUp = 0L;
    public void cadStylusSetEnabled(boolean enabled) {
        cadWheelEnabled = enabled;
        if (!enabled) cadWheelKeys.clear();
    }
    public int cadStylusPoll() {
        Integer code = cadWheelKeys.poll();
        return code == null ? 0 : code;
    }
    private boolean cadStylusIntercept(KeyEvent event) {
        if (!cadWheelEnabled || event == null) return false;
        final int code = event.getKeyCode();
        if (code != KeyEvent.KEYCODE_DPAD_DOWN && code != KeyEvent.KEYCODE_DPAD_UP) return false;
        final InputDevice device = InputDevice.getDevice(event.getDeviceId());
        if (device == null || device.getName() == null) return false;
        final String name = device.getName().toLowerCase(java.util.Locale.ROOT);
        if (!name.contains("magic-pencil") && !name.contains("magic pencil")) return false;
        // Do not trigger on ACTION_DOWN or repeat. The pen's key release is
        // the one-shot event matching the existing PhotoCraft wheel behavior.
        if (event.getAction() == KeyEvent.ACTION_UP && event.getRepeatCount() == 0) {
            long now = android.os.SystemClock.uptimeMillis();
            long prior = code == KeyEvent.KEYCODE_DPAD_DOWN ? cadWheelLastDown : cadWheelLastUp;
            if (now - prior >= 650L && cadWheelKeys.size() < 12) {
                cadWheelKeys.offer(code);
                try {
                    cadWheelButtonNative(code);
                } catch (UnsatisfiedLinkError error) {
                    // Preserve the Java polling fallback until the native
                    // library is loaded, e.g. very early in app startup.
                    Log.w(TAG, "CADCraft pen direct JNI not available", error);
                }
                if (code == KeyEvent.KEYCODE_DPAD_DOWN) cadWheelLastDown = now;
                else cadWheelLastUp = now;
                Log.d(TAG, "CADCraft validated Magic-Pencil button " + code);
            }
        }
        return true;
    }
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (cadStylusIntercept(event)) return true;
        return super.dispatchKeyEvent(event);
    }
    @Override
    public boolean dispatchKeyShortcutEvent(KeyEvent event) {
        if (cadStylusIntercept(event)) return true;
        return super.dispatchKeyShortcutEvent(event);
    }
    // Match real HONOR Magic-Pencil hardware IDs before consuming DPAD events.
    public String cadStylusDeviceIds() {
        StringBuilder names = new StringBuilder();
        for (int id : InputDevice.getDeviceIds()) {
            InputDevice device = InputDevice.getDevice(id);
            if (device == null || device.getName() == null) continue;
            String name = device.getName().toLowerCase(java.util.Locale.ROOT);
            if (name.contains("magic-pencil") || name.contains("magic pencil")) {
                if (names.length() > 0) names.append(',');
                names.append(id);
            }
        }
        return names.toString();
    }
"""
    source = source.replace(anchor, inject, 1)
    # The hidden IME's InputConnection may see a key without Activity dispatch;
    # mirror the same verified-pen guard before the inherited editor route.
    ime_anchor = """                public boolean sendKeyEvent(KeyEvent event) {
                    if (event != null && !isFromSoftKeyboard(event)) {"""
    if source.count(ime_anchor) != 1:
        raise SystemExit("CADCraft IME key routing changed; refusing unsafe fallback")
    source = source.replace(ime_anchor,
        """                public boolean sendKeyEvent(KeyEvent event) {
                    if (cadStylusIntercept(event)) return true;
                    if (event != null && !isFromSoftKeyboard(event)) {""", 1)
    java.write_text(source, encoding="utf-8")

    # Vendor crate is copied into the CADCraft source during the builder step.
    vendor = reference / "vendor/android-activity"
    root = vendor / "src/lib.rs"
    original = root.read_text(encoding="utf-8")
    if "cad_stylus_native_take" in original:
        raise SystemExit("CADCraft pen queue already exists")
    original += r'''
// CADCRAFT_ISOLATED_PEN_KEY_QUEUE: only an explicit, verified Magic-Pencil ID.
#[cfg(feature = "native-activity")]
struct CadStylusKeys {
    enabled: bool,
    allowed_ids: Vec<i32>,
    events: Vec<u8>,
    last: Option<std::time::Instant>,
}
#[cfg(feature = "native-activity")]
static CAD_STYLUS_KEYS: std::sync::Mutex<CadStylusKeys> =
    std::sync::Mutex::new(CadStylusKeys {
        enabled: false, allowed_ids: Vec::new(), events: Vec::new(), last: None
    });

#[cfg(feature = "native-activity")]
pub fn cad_stylus_configure(enabled: bool, ids: &[i32]) {
    if let Ok(mut state) = CAD_STYLUS_KEYS.lock() {
        let new_ids: Vec<i32> = ids.iter().copied().take(16).filter(|id| *id > 0).collect();
        if state.enabled != enabled || state.allowed_ids != new_ids {
            state.events.clear();
            state.last = None;
        }
        state.enabled = enabled;
        state.allowed_ids = new_ids;
    }
}
#[cfg(feature = "native-activity")]
pub fn cad_stylus_capture(device: i32, code: i32, action: i32, repeat: i32) -> bool {
    let Ok(mut state) = CAD_STYLUS_KEYS.lock() else { return false };
    if !state.enabled || !state.allowed_ids.contains(&device) ||
        (code != 19 && code != 20) { return false; }
    // Swallow both DPAD_DOWN and DPAD_UP from the named pen; only release
    // triggers a wheel toggle. Never swallow physical keyboard arrows.
    if action == 1 && repeat == 0 {
        let now = std::time::Instant::now();
        if state.last.is_none_or(|t| now.duration_since(t) >= std::time::Duration::from_millis(650))
            && state.events.len() < 16 {
            state.events.push(code as u8);
            state.last = Some(now);
            log::info!("CADCraft: verified Magic-Pencil button code={code} device={device}");
        }
    }
    true
}
#[cfg(feature = "native-activity")]
pub fn cad_stylus_native_take() -> Vec<u8> {
    if let Ok(mut state) = CAD_STYLUS_KEYS.lock() {
        std::mem::take(&mut state.events)
    } else { Vec::new() }
}
'''
    root.write_text(original, encoding="utf-8")

    native = vendor / "src/native_activity/mod.rs"
    original = native.read_text(encoding="utf-8")
    # The previous implementation intercepted AFTER pre_dispatch; some
    # MagicOS pen releases are consumed by that IME pre-dispatch stage.
    # Always identify the verified device and key BEFORE it runs.
    anchor = "        if let Ok(Some(ndk_event)) = queue.event() {"
    if original.count(anchor) != 1:
        raise SystemExit("NativeActivity input queue changed; refuse pen interception")
    injected = """        if let Ok(Some(ndk_event)) = queue.event() {
            // CADCraft: intercept a named HONOR Magic-Pencil 4s keyboard event
            // BEFORE pre_dispatch can consume its orphan key-release.
            // All non-pen keys still follow the stock Android/winit path.
            if let ndk::event::InputEvent::KeyEvent(ref key) = ndk_event {
                let ptr = key.ptr().as_ptr();
                let device = unsafe { ndk_sys::AInputEvent_getDeviceId(ptr) };
                let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(ptr) };
                let action = unsafe { ndk_sys::AKeyEvent_getAction(ptr) };
                let repeat = unsafe { ndk_sys::AKeyEvent_getRepeatCount(ptr) };
                if crate::cad_stylus_capture(device, code, action, repeat) {
                    queue.finish_event(ndk_event, true);
                    return true;
                }
            }
"""
    native.write_text(original.replace(anchor, injected, 1), encoding="utf-8")
    print("PASS: native stylus-only capture plus safe updater Activity method")



def patch_cadcraft_ui(source: Path) -> None:
    """Persist wheel customization through native prefs without changing desktop behavior."""
    lib = source / "crates/ui-egui/src/lib.rs"
    src = lib.read_text(encoding="utf-8")

    def replace_once(text: str, needle: str, replacement: str) -> str:
        if text.count(needle) != 1:
            raise SystemExit("CADCraft v0.19.0 UI anchor changed; refusing unreviewed patch: " + needle[:70])
        return text.replace(needle, replacement, 1)

    src = replace_once(src, "pub mod menus;\n",
        'pub mod menus;\n#[cfg(target_os = "android")]\npub mod cadcraft_android_wheel;\n')
    src = replace_once(src, "    pub last_pgp_dir: Option<String>,\n",
        """    pub last_pgp_dir: Option<String>,
    /// Android-only PhotoCraft-style CAD stylus wheel controls.
    pub cad_wheel_open: bool,
    pub cad_wheel_enabled: bool,
    pub cad_wheel_customize: bool,
    pub cad_wheel_actions: Vec<String>,
    pub cad_wheel_size: f32,
    pub cad_wheel_opacity: f32,
""")
    src = replace_once(src, "            last_pgp_dir: None,\n",
        """            last_pgp_dir: None,
            cad_wheel_open: false,
            cad_wheel_enabled: true,
            cad_wheel_customize: false,
            cad_wheel_actions: vec![
                "select", "line", "circle", "ui.panel.layers", "pan", "trim", "redo", "undo",
            ].into_iter().map(str::to_string).collect(),
            cad_wheel_size: 0.75,
            cad_wheel_opacity: 0.85,
""")
    src = replace_once(src, "        prefs.to_string()\n",
        """        #[cfg(target_os = "android")]
        {
            prefs["cadWheelPresetVersion"] = json!(2);
            prefs["cadWheelEnabled"] = json!(self.ui.cad_wheel_enabled);
            prefs["cadWheelActions"] = json!(self.ui.cad_wheel_actions);
            prefs["cadWheelSize"] = json!(self.ui.cad_wheel_size);
            prefs["cadWheelOpacity"] = json!(self.ui.cad_wheel_opacity);
        }
        prefs.to_string()
""")
    src = replace_once(src, '        if let Some(keys) = v.get("shortcuts").filter(|k| k.is_object()) {\n',
        """        #[cfg(target_os = "android")]
        {
            if let Some(enabled) = v.get("cadWheelEnabled").and_then(Value::as_bool) {
                self.ui.cad_wheel_enabled = enabled;
            }
            if let Some(actions) = v.get("cadWheelActions").and_then(Value::as_array) {
                if actions.len() == 8
                    && actions.iter().all(|v| v.as_str().is_some_and(crate::cadcraft_android_wheel::valid_action))
                {
                    self.ui.cad_wheel_actions = actions.iter()
                        .filter_map(Value::as_str).map(str::to_string).collect();
                }
            }
            if let Some(size) = v.get("cadWheelSize").and_then(Value::as_f64) {
                if size.is_finite() {
                    // Previous Android.4 stored 100% as the untouched default.
                    // Upgrade that default to 75%, preserve other user choices.
                    let old_preset = v.get("cadWheelPresetVersion").and_then(Value::as_u64)
                        .unwrap_or(1) < 2;
                    self.ui.cad_wheel_size =
                        if old_preset && (size - 1.0).abs() < 0.0001 { 0.75 }
                        else { (size as f32).clamp(0.75, 1.25) };
                }
            }
            if let Some(opacity) = v.get("cadWheelOpacity").and_then(Value::as_f64) {
                if opacity.is_finite() { self.ui.cad_wheel_opacity = (opacity as f32).clamp(0.60, 1.0); }
            }
        }
        if let Some(keys) = v.get("shortcuts").filter(|k| k.is_object()) {
""")
    src = replace_once(src, "        self.opening.show(ui.ctx());\n",
        """        #[cfg(target_os = "android")]
        crate::cadcraft_android_wheel::show(self, ui.ctx(), ui.max_rect());
        self.opening.show(ui.ctx());
""")
    lib.write_text(src, encoding="utf-8")

    template = Path(__file__).with_name("cadcraft_android_wheel.rs")
    if not template.is_file():
        raise SystemExit("Missing reviewed Android wheel module")
    dest = source / "crates/ui-egui/src/cadcraft_android_wheel.rs"
    if dest.exists():
        raise SystemExit("CADCraft wheel module exists upstream; refusing overwrite")
    dest.write_bytes(template.read_bytes())
    # JNI bridge is compiled only for the Android UI target; no desktop graph changes.
    cargo = source / "crates/ui-egui/Cargo.toml"
    manifest = cargo.read_text(encoding="utf-8")
    dep_section = """\n[target.'cfg(target_os = "android")'.dependencies]\ncadcraft-android-updater-bridge = { path = "../cadcraft-android-updater-bridge" }
android-activity = { version = "0.6", default-features = false, features = ["native-activity"] }\n"""
    if "cadcraft-android-updater-bridge" in manifest or "[target.'cfg(target_os = \"android\")'.dependencies]" in manifest:
        raise SystemExit("CADCraft Android JNI dependencies changed; inspect manifest")
    cargo.write_text(manifest + dep_section, encoding="utf-8")
    # JNI unsafe boundary is in a tiny Android-only crate, outside the
    # upstream UI crate which forbids unsafe code.
    bridge = source / "crates/cadcraft-android-updater-bridge"
    bridge_src = bridge / "src"
    bridge_src.mkdir(parents=True, exist_ok=True)
    (bridge / "Cargo.toml").write_text(
        '[package]\nname = "cadcraft-android-updater-bridge"\nversion = "0.1.0"\nedition = "2021"\n'
        '[dependencies]\njni = "0.21"\nndk-context = "0.1"\n', encoding="utf-8")
    (bridge_src / "lib.rs").write_text(
        Path(__file__).with_name("cadcraft_android_updater_bridge.rs").read_text(encoding="utf-8"),
        encoding="utf-8")
    print("PASS: 8 CAD actions, live size/opacity preview, native updater entry and saved prefs staged.")


def prepare_exact_icon(reference: Path, source: Path) -> None:
    """Generate the PNG and an embedded matching 64px Cc menu/wheel icon."""
    import subprocess
    from PIL import Image
    root = Path(__file__).resolve().parent.parent
    png = reference / "assets/cadcraft/cc-icon-1024.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "java", "-Djava.awt.headless=true",
        str(root / "tools/CadCraftIcon.java"),
        str(root / "assets/cadcraft/Cc-launcher-icon.svg"),
        str(png)
    ], check=True)
    icon = Image.open(png).convert("RGBA")
    if icon.getpixel((icon.width // 2, icon.height // 6))[:3] != (209, 49, 83):
        raise SystemExit("Cc icon is not exact #D13153: refusing Android build")
    raw = icon.resize((64, 64), Image.Resampling.LANCZOS).tobytes()
    if len(raw) != 64 * 64 * 4:
        raise SystemExit("Invalid CADCraft native menu icon")
    (source / "crates/ui-egui/src/cadcraft_cc_icon.rgba").write_bytes(raw)
    # Transparent cream glyph for the circular solid-pink center hub, preserving
    # the exact Cc letterforms (never place a rounded square inside the hub).
    work = icon.resize((256, 256), Image.Resampling.LANCZOS)
    pixels = work.load()
    glyph = Image.new("RGBA", work.size, (0, 0, 0, 0))
    gp = glyph.load()
    for y in range(256):
        for x in range(256):
            r, g, b, a = pixels[x, y]
            coverage = max(0, min(255, round((g - 49) * 255 / (228 - 49))))
            if coverage > 1 and a > 0:
                gp[x, y] = (243, 228, 231, round(a * coverage / 255))
    bbox = glyph.getbbox()
    if bbox is None:
        raise SystemExit("Cc center glyph extraction failed")
    glyph = glyph.crop(bbox)
    glyph.thumbnail((52, 39), Image.Resampling.LANCZOS)
    center = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    center.alpha_composite(glyph, ((64 - glyph.width) // 2, (64 - glyph.height) // 2))
    (source / "crates/ui-egui/src/cadcraft_cc_glyph.rgba").write_bytes(center.tobytes())
    from cadcraft_icon_fix import patch_reference
    patch_reference(reference)
    print("PASS: Cc menu/wheel artwork uses exact supplied red #D13153 and cream #F3E4E7.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path)
    args = p.parse_args()
    apply(args.source)
    patch_cadcraft_ui(args.source)
    prepare_exact_icon(args.reference, args.source)
    install_cadcraft_updater(args.reference)
    install_pen_button(args.reference)


if __name__ == "__main__":
    main()
