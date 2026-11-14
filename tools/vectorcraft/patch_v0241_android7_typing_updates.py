"""VectorCraft v0.24.1-android.7: gated physical Type input and PhotoCraft update UI.

Applied *after* the reviewed Android.6 and Android.5 updater overlays.
No upstream merge, no release/install/signing changes.
"""
from pathlib import Path
import sys


def replace_once(source: str, before: str, after: str, label: str) -> str:
    count = source.count(before)
    if count != 1:
        raise RuntimeError(f"Android.7 {label}: expected one anchor, got {count}")
    return source.replace(before, after, 1)


def in_method(source: str, begin: str, end: str, before: str, after: str, label: str) -> str:
    start = source.index(begin)
    stop = source.index(end, start + len(begin))
    return (source[:start] + replace_once(source[start:stop], before, after, label)
            + source[stop:])


def patch(root: Path) -> None:
    base = root / "adapters/vectorcraft"
    activity_path = base / "java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    host_path = base / "src/lib.rs"
    ime_path = base / "src/ime_bridge.rs"
    menu_path = root / "source/vectorcraft/crates/ui-egui/src/menus/bar.rs"
    activity = activity_path.read_text()
    host = host_path.read_text()
    ime = ime_path.read_text()
    menu = menu_path.read_text()

    # A NativeActivity may receive hardware keys while its hidden EditText
    # owns focus. The Android.12 fallback intentionally handles canvas shortcuts
    # only; this separate, explicitly Type-scoped path handles printable keys.
    activity = replace_once(activity,
        "    private volatile boolean imeWanted = false;",
        """    private volatile boolean imeWanted = false;
    private volatile boolean vcPhysicalTypeEditing = false;
    public void vcSetPhysicalTypeEditing(boolean editing) {
        if (vcPhysicalTypeEditing == editing) return;
        vcPhysicalTypeEditing = editing;
        if (!editing) {
            // No prior document's queued typing can reach a later editor.
            imeEvents.removeIf(value -> value.startsWith("h"));
        }
    }""", "Type mode flag")
    key_fallback = """        // MagicOS physical keyboards can deliver keys to NativeActivity
        // without a corresponding winit Text event after the IME has focus.
        // Consume ONLY printable keys in an active native Type edit session.
        // Never intercept Gboard/virtual keyboard, IME preedit, control keys,
        // Escape, delete/navigation, Ctrl+Q/W/Z or AltGr composition.
        final int unicode = event.getUnicodeChar(event.getMetaState());
        final boolean physical = event.getDeviceId()
                != android.view.KeyCharacterMap.VIRTUAL_KEYBOARD;
        if (vcPhysicalTypeEditing && physical
                && !event.isCtrlPressed() && !event.isAltPressed()
                && !event.isMetaPressed()
                && (unicode & android.view.KeyCharacterMap.COMBINING_ACCENT) == 0
                && Character.isValidCodePoint(unicode)
                && unicode > 0 && !Character.isISOControl(unicode)) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && imeEvents.size() < 128) {
                imeEvents.offer("h" + new String(Character.toChars(unicode)));
                vcWakeNativeLoop();
            }
            // Match key-up to key-down; suppress duplicate native Text events.
            return true;
        }
        return super.dispatchKeyEvent(event);"""
    activity = in_method(activity,
        "    public boolean dispatchKeyEvent(KeyEvent event) {",
        "    public ", "        return super.dispatchKeyEvent(event);",
        key_fallback, "physical dispatch fallback") if False else activity
    # dispatchKeyEvent precedes the next annotated method, not a new public
    # declaration on all pinned builders. Use the uniquely reviewed final call.
    activity = replace_once(activity,
        "        return super.dispatchKeyEvent(event);",
        key_fallback, "physical key dispatch")

    # Separate 'h' (hardware printable text) from 'c' (soft-IME commit). The
    # upstream Type sequence takes Text directly; do not synthesize IME reset
    # completion or change the editor's stale-composition checks.
    ime = replace_once(ime,
        "            'p' => Some(egui::Event::Ime(egui::ImeEvent::Preedit {",
        """            'h' if !payload.is_empty() => Some(egui::Event::Text(payload.to_owned())),
            'p' => Some(egui::Event::Ime(egui::ImeEvent::Preedit {""",
        "hardware text translate")

    # JNI mode follows real tool_wants_text state, not an Android cached
    # preference or merely selecting T (which may have no insertion caret).
    host = replace_once(host,
        "    fn set_hardware_shortcut_mode(&self, mode: i32) -> Result<(), String> {",
        """    fn set_physical_type_editing(&self, editing: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcSetPhysicalTypeEditing"),
                jni_sig!("(Z)V"), &[JValue::Bool(if editing { 1 } else { 0 })])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }
    fn set_hardware_shortcut_mode(&self, mode: i32) -> Result<(), String> {""",
        "JNI hardware typing mode")
    host = replace_once(host,
        "    last_hardware_shortcut_mode: i32,",
        """    last_hardware_shortcut_mode: i32,
    last_physical_type_editing: bool,
    vc_update_toast: Option<(String, std::time::Instant)>,""",
        "app state")
    host = replace_once(host,
        "                last_hardware_shortcut_mode: -1,",
        """                last_hardware_shortcut_mode: -1,
                last_physical_type_editing: false,
                vc_update_toast: None,""",
        "initial app state")
    host = replace_once(host,
        "        let editing = self.inner.session.tool_wants_text();",
        """        let editing = self.inner.session.tool_wants_text();
        if editing != self.last_physical_type_editing {
            match self.bridge.set_physical_type_editing(editing) {
                Ok(()) => self.last_physical_type_editing = editing,
                Err(error) => log::warn!("Android.7 physical Type mode handoff failed: {error}"),
            }
        }""", "Type editor handoff")

    # Match PhotoCraft's compact Vc submenu checkmark without changing the
    # persistent preference ownership: the existing Android bit toggles it.
    menu = replace_once(menu,
        '''                if ui.button("Check at Startup").clicked() {
                    clicked = Some(("android.vectorcraft.startupUpdates".into(), serde_json::json!({})));
                    ui.close();
                }''',
        '''                let mut startup = super::ANDROID_STARTUP_ENABLED.load(
                    std::sync::atomic::Ordering::Acquire);
                if ui.checkbox(&mut startup, "Check for updates at startup").changed() {
                    clicked = Some(("android.vectorcraft.startupUpdates".into(), serde_json::json!({})));
                    ui.close();
                }''', "checked startup update setting")

    # The About/Updates tab stays available for detailed status and verified
    # download. Checking through Vc menu must not force an About modal on top
    # of the canvas; use a non-interactive bottom-center charcoal pill.
    host = replace_once(host,
        "        if self.updates.checking || self.updates.downloading {",
        """        let vc_update_status_before = self.updates.message.clone();
        if self.updates.checking || self.updates.downloading {""",
        "update status start")
    host = replace_once(host,
        "        // Then deliver any file the system asked us to open, through the same inbox.",
        """        if self.updates.message != vc_update_status_before {
            self.vc_update_toast = Some((
                self.updates.message.clone(),
                std::time::Instant::now() + std::time::Duration::from_secs(4),
            ));
        }
        // Then deliver any file the system asked us to open, through the same inbox.""",
        "update status toast")
    host = replace_once(host,
        '''            self.inner.ui.about = true;
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("about_tab"), 3u8));
            if !self.updates.checking {''',
        '''            // Vc menu checks quietly, while About → Updates remains
            // available for channel selection and verified installation.
            if !self.updates.checking {''', "menu update workflow")
    host = replace_once(host,
        '''        if menu & 16 != 0 { self.startup_updates = !self.startup_updates; }''',
        '''        if menu & 16 != 0 {
            self.startup_updates = !self.startup_updates;
            self.vc_update_toast = Some((
                if self.startup_updates {
                    "Automatic update checks enabled".into()
                } else {
                    "Automatic update checks disabled".into()
                },
                std::time::Instant::now() + std::time::Duration::from_secs(3),
            ));
        }''', "startup toggle notice")
    host = replace_once(host,
        '''                match self.bridge.check_for_updates() {
                    Ok(()) => self.updates.checking = true,''',
        '''                self.vc_update_toast = Some((
                    self.updates.message.clone(),
                    std::time::Instant::now() + std::time::Duration::from_secs(3),
                ));
                match self.bridge.check_for_updates() {
                    Ok(()) => self.updates.checking = true,''',
        "check-in-progress notice")
    host = replace_once(host,
        "        // Adaptive cursor from ArtCraft builder v0.2.0, without replacing the",
        """        // PhotoCraft-style bottom-center announcement, independent of the
        // existing eight-segment stylus wheel and its notification.
        if let Some((message, expiry)) = self.vc_update_toast.as_ref() {
            let remaining = expiry.saturating_duration_since(std::time::Instant::now());
            if remaining.is_zero() {
                self.vc_update_toast = None;
            } else {
                let fade = (remaining.as_secs_f32() / 0.45).clamp(0.0, 1.0);
                egui::Area::new(egui::Id::new("vc-update-notification"))
                    .anchor(egui::Align2::CENTER_BOTTOM, egui::vec2(0.0, -24.0))
                    .order(egui::Order::Foreground)
                    .interactable(false)
                    .show(ctx, |ui| {
                        egui::Frame::new()
                            .fill(egui::Color32::from_rgb(37, 37, 39).linear_multiply(fade))
                            .stroke(egui::Stroke::new(0.8,
                                egui::Color32::from_gray(90).linear_multiply(fade)))
                            .corner_radius(egui::CornerRadius::same(18))
                            .inner_margin(egui::Margin::symmetric(16, 9))
                            .show(ui, |ui| {
                                ui.set_min_width(380.0);
                                ui.set_max_width(450.0);
                                ui.label(egui::RichText::new(message)
                                    .color(egui::Color32::WHITE.linear_multiply(fade)));
                            });
                    });
                ctx.request_repaint_after(std::time::Duration::from_millis(60));
            }
        }
        // Adaptive cursor from ArtCraft builder v0.2.0, without replacing the""",
        "bottom-center toast")

    for path, text in ((activity_path, activity), (ime_path, ime),
                       (host_path, host), (menu_path, menu)):
        path.write_text(text)
    print("PASS: Android.7 native Type printable keys, stable IME protocol, checked App Updates and bottom pill")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_v0241_android7_typing_updates.py STAGED_BUILDER")
    patch(Path(sys.argv[1]))
