#!/usr/bin/env python3
"""Stage PhotoCraft 0.19.0-android.6 Pc-icon app menu, font refresh and canvas gestures.

Only edits ephemeral GitHub Actions checkout after the official source preservation
gate; refuses any upstream SHA / known anchor drift. No release or signing changes.
"""
from pathlib import Path
import subprocess
import argparse

EXPECTED = "2df9f807702a935184041355a86405380bda8274"

def replace(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    n = content.count(old)
    if n != 1:
        raise RuntimeError(f"{path}: expected exactly one reviewed anchor, found {n}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"Android.6 stage: {path}")

def main() -> None:
    cli=argparse.ArgumentParser()
    cli.add_argument("--upstream",type=Path,required=True)
    cli.add_argument("--adapter",type=Path,required=True)
    args=cli.parse_args()
    sha=subprocess.check_output(["git","-C",str(args.upstream),"rev-parse","HEAD"],text=True).strip()
    if sha != EXPECTED:
        raise RuntimeError(f"Unreviewed upstream commit {sha}; no overlay applied")
    upstream=args.upstream
    adapter=args.adapter
    menus=upstream/"crates/ui-egui/src/menus.rs"
    brand=upstream/"crates/ui-egui/src/panels/brand.rs"
    host=adapter/"src/lib.rs"
    ai=adapter/"src/ai_menu.rs"
    fonts=adapter/"src/android_fonts.rs"
    activity=adapter/"java/com/artcraft/photocraft/PhotoCraftActivity.java"

    replace(menus, "pub use state::is_enabled;\n",
'''pub use state::is_enabled;

// Small command queue from the Pc icon to the NativeActivity shell.
// Keep the icon independent from the engine's editor mutable borrows.
#[cfg(target_os = "android")]
static ARTCRAFT_PC_MENU_ACTION: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);
#[cfg(target_os = "android")]
pub fn artcraft_queue_pc_menu_action(action: u8) {
    ARTCRAFT_PC_MENU_ACTION.store(action, std::sync::atomic::Ordering::Relaxed);
}
#[cfg(target_os = "android")]
pub fn artcraft_take_pc_menu_action() -> u8 {
    ARTCRAFT_PC_MENU_ACTION.swap(0, std::sync::atomic::Ordering::Relaxed)
}
''')
    replace(brand,
'''    ui.ctx().data_mut(|d| d.insert_temp(rect_id(), r));
}''',
'''    ui.ctx().data_mut(|d| d.insert_temp(rect_id(), r));
    // The blue Pc logo is the single, discoverable ArtCraft Android menu
    // launcher. This does not change the user's launcher / APK icon assets.
    #[cfg(target_os = "android")]
    {
        let response = ui.interact(r, egui::Id::new("artcraft_pc_icon_menu"), egui::Sense::click());
        let action = |ui: &mut egui::Ui, title: &str, value: u8| {
            if ui.button(title).clicked() {
                crate::menus::artcraft_queue_pc_menu_action(value);
                ui.close();
            }
        };
        egui::Popup::menu(&response).show(|ui| {
            ui.set_min_width(236.0);
            ui.strong("PhotoCraft · ArtCraft Android");
            ui.separator();
            ui.menu_button("AI Tools", |ui| {
                action(ui, "Remove Background · U2NetP…", 2);
                action(ui, "ComfyUI Connection…", 3);
                action(ui, "About AI Tools…", 4);
                ui.separator();
                action(ui, if crate::menus::artcraft_ai_tools_visible() {
                    "Hide AI Tools" } else { "Show AI Tools" }, 1);
            });
            ui.menu_button("Fonts", |ui| {
                action(ui, "Import Font…", 5);
                action(ui, "Import Font Folder…", 6);
                ui.separator();
                action(ui, "Refresh Fonts (background)", 7);
                ui.weak("Up to 5,000 fonts / 4 GiB");
            });
            ui.menu_button("Updates", |ui| {
                action(ui, "Check for Updates…", 8);
                action(ui, "Toggle Update Check at Startup", 9);
            });
            ui.separator();
            ui.menu_button("Appearance", |ui| {
                ui.menu_button("Theme", |ui| {
                    action(ui, "Dark", 14);
                    action(ui, "Light", 15);
                    action(ui, "Follow System", 16);
                });
                action(ui, "Next Appearance Mode", 13);
                ui.menu_button("Shortcut Pad", |ui| {
                    action(ui, if crate::menus::artcraft_pad_visible() {
                        "Hide Shortcut Pad" } else { "Show Shortcut Pad" }, 10);
                    action(ui, "Dock Left", 11);
                    action(ui, "Dock Right", 12);
                });
                action(ui, if crate::menus::artcraft_ai_tools_visible() {
                    "Hide AI Tools" } else { "Show AI Tools" }, 1);
            });
        });
    }
}''')

    # The original AI toolbar is no longer a full-width top strip.
    # Keep all dialogs, consent protections and state unchanged.
    source=ai.read_text(encoding="utf-8")
    start=source.find('        egui::Panel::top("artcraft_photocraft_android_ai_menu")')
    end=source.find('        if self.show_background_setup {',start)
    if start < 0 or end < start or source.count('        egui::Panel::top("artcraft_photocraft_android_ai_menu")') != 1:
        raise RuntimeError("AI toolbar source changed: require review")
    source=source[:start]+'''        // AI actions now live under the top-left Pc launcher menu.
        // Keep the dialogs below available and independently consent gated.
'''+source[end:]
    ai.write_text(source,encoding="utf-8")
    replace(ai, "impl AndroidAiMenu {\n",
'''impl AndroidAiMenu {
    pub(crate) fn open_from_pc(&mut self, kind: u8) {
        // Pc menu actions open the existing safe dialogs; never start AI jobs.
        photocraft_ui_egui::menus::artcraft_set_ai_tools_visible(true);
        match kind {
            2 => self.show_background_setup = true,
            3 => self.show_connection = true,
            4 => self.show_about = true,
            _ => {}
        }
    }
''')
    replace(fonts,
'''pub(crate) struct AndroidFonts {
    message: Option<String>,''',
'''pub(crate) struct AndroidFonts {
    font_dir: PathBuf,
    message: Option<String>,''')
    replace(fonts,
'''        let _ = jobs.send(Job::Restore(dir.join("PhotoCraft/fonts-imported")));
        Self { message: None, visible: false, tx: jobs, rx }
    }
    pub(crate) fn poll(&mut self, bridge: &AndroidFileBridge) {''',
'''        let font_dir = dir.join("PhotoCraft/fonts-imported");
        let _ = jobs.send(Job::Restore(font_dir.clone()));
        Self { font_dir, message: None, visible: false, tx: jobs, rx }
    }
    pub(crate) fn refresh(&mut self) {
        if self.tx.send(Job::Restore(self.font_dir.clone())).is_ok() {
            self.message = Some("Refreshing the 5,000-file / 4 GiB font catalog in the background…".into());
        } else {
            self.message = Some("Font indexer unavailable".into());
        }
        self.visible = true;
    }
    pub(crate) fn poll(&mut self, bridge: &AndroidFileBridge) {''')

    replace(host, "mod trackpad_wheel;\n", "mod trackpad_wheel;\nmod canvas_gesture;\n")
    replace(host,
'''    touch_scroll: ui_touch_scroll::UiTouchScroll,
''',
'''    touch_scroll: ui_touch_scroll::UiTouchScroll,
    canvas_gesture: canvas_gesture::CanvasTouchGestures,
''')
    replace(host,
'''                touch_scroll: ui_touch_scroll::UiTouchScroll::default(),
''',
'''                touch_scroll: ui_touch_scroll::UiTouchScroll::default(),
                canvas_gesture: canvas_gesture::CanvasTouchGestures::default(),
''')
    replace(host, "        self.touch_scroll.route(ctx, raw);\n",
'''        self.canvas_gesture.route(ctx, raw);
        self.touch_scroll.route(ctx, raw);
''')
    replace(host, "        self.inner.logic(ctx, frame);\n",
'''        self.inner.logic(ctx, frame);
        self.canvas_gesture.apply(&mut self.inner);
''')

    replace(host,
'''        self.inner.ui(ui, _frame);
''',
'''        self.inner.ui(ui, _frame);
        // The in-app Pc mark is a menu launcher; act only after upstream
        // painted its title bar, to avoid borrowing the document UI twice.
        match photocraft_ui_egui::menus::artcraft_take_pc_menu_action() {
            1 => {
                let visible = !photocraft_ui_egui::menus::artcraft_ai_tools_visible();
                photocraft_ui_egui::menus::artcraft_set_ai_tools_visible(visible);
            }
            2..=4 => self.ai_menu.open_from_pc(
                photocraft_ui_egui::menus::artcraft_take_pc_menu_action_unused_placeholder()
            ),
            5 => { if let Err(e) = self.bridge.request_font_import(false) { log::warn!("Font import: {e}"); } },
            6 => { if let Err(e) = self.bridge.request_font_import(true) { log::warn!("Font folder: {e}"); } },
            7 => self.android_fonts.refresh(),
            8 => { if let Err(e) = self.bridge.request_update_check() { log::warn!("Update check: {e}"); } },
            9 => { if let Err(e) = self.bridge.toggle_startup_updates() { log::warn!("Startup updates: {e}"); } },
            10 => {
                let visible = !photocraft_ui_egui::menus::artcraft_pad_visible();
                photocraft_ui_egui::menus::artcraft_pad_set_visible(visible);
            }
            11 => { photocraft_ui_egui::menus::artcraft_pad_set_left(true);
                    photocraft_ui_egui::menus::artcraft_pad_set_visible(true); }
            12 => { photocraft_ui_egui::menus::artcraft_pad_set_left(false);
                    photocraft_ui_egui::menus::artcraft_pad_set_visible(true); }
            13..=16 => {
                let id = match photocraft_ui_egui::menus::artcraft_take_pc_menu_action_unused_placeholder() {
                    13 => "window.theme.toggle",
                    14 => "window.theme.pro",
                    15 => "window.theme.proLight",
                    _ => "window.theme.system"
                };
                if let Err(e) = photocraft_ui_egui::menus::invoke(
                    &mut self.inner, ui.ctx(), id, serde_json::json!({})
                ) { log::warn!("Theme: {e}"); }
            }
            _ => {}
        }
''')
    # Replace the sentinel with a single action variable rather than consuming
    # the atomic twice (the second take would always return 0).
    h=host.read_text(encoding="utf-8")
    needle='''        match photocraft_ui_egui::menus::artcraft_take_pc_menu_action() {'''
    if h.count(needle) != 1:
        raise RuntimeError("Action queue staged incorrectly")
    h=h.replace(needle,'''        let pc_action = photocraft_ui_egui::menus::artcraft_take_pc_menu_action();
        match pc_action {''',1)
    sentinel='photocraft_ui_egui::menus::artcraft_take_pc_menu_action_unused_placeholder()'
    if h.count(sentinel) != 2:
        raise RuntimeError("Action queue placeholders changed")
    h=h.replace(sentinel,'pc_action')
    host.write_text(h,encoding="utf-8")

    replace(host, "    fn request_update_check(&self) -> Result<(), String> {\n",
'''    fn toggle_startup_updates(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pcToggleStartupUpdates"),
                jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn request_update_check(&self) -> Result<(), String> {
''')
    replace(activity, '    public void pcCheckUpdates() {\n',
'''    public void pcToggleStartupUpdates() {
        runOnUiThread(() -> {
            java.io.File off = new java.io.File(getFilesDir(), "update-check-off");
            if (off.exists()) {
                if (!off.delete()) android.util.Log.w(TAG, "Could not enable startup checks");
            } else {
                try {
                    if (!off.createNewFile()) android.util.Log.w(TAG, "Could not disable startup checks");
                } catch (java.io.IOException e) {
                    android.util.Log.w(TAG, "Could not change startup checks", e);
                }
            }
            android.widget.Toast.makeText(this,
                off.exists() ? "Update checks at startup: OFF" : "Update checks at startup: ON",
                android.widget.Toast.LENGTH_SHORT).show();
        });
    }

    public void pcCheckUpdates() {
''')
    # Repair Escape and single-key shortcuts independently of the upstream
    # v0.19 IME reset handshake (NativeActivity's custom winit has no reset ACK).
    # This fallback only runs for physical egui::Key events and never consumes
    # arbitrary characters or reads sensitive token text.
    replace(host,
'''    canvas_gesture: canvas_gesture::CanvasTouchGestures,
''',
'''    canvas_gesture: canvas_gesture::CanvasTouchGestures,
    artcraft_esc_pending: bool,
    artcraft_tool_pending: Option<&'static str>,
''')
    replace(host,
'''                canvas_gesture: canvas_gesture::CanvasTouchGestures::default(),
''',
'''                canvas_gesture: canvas_gesture::CanvasTouchGestures::default(),
                artcraft_esc_pending: false,
                artcraft_tool_pending: None,
''')
    replace(host, "        self.canvas_gesture.route(ctx, raw);\n",
'''        // Store commands before the upstream IME editor filters raw events.
        for event in &raw.events {
            if let egui::Event::Key { key, pressed: true, modifiers, .. } = event {
                if *key == egui::Key::Escape && self.inner.ui.text_edit.is_some() {
                    self.artcraft_esc_pending = true;
                }
                if !modifiers.ctrl && !modifiers.alt && !modifiers.shift
                    && self.inner.ui.text_edit.is_none() {
                    self.artcraft_tool_pending = match key {
                        egui::Key::V => Some("tools.select.move"),
                        egui::Key::T => Some("tools.select.type"),
                        egui::Key::B => Some("tools.select.brush"),
                        _ => self.artcraft_tool_pending,
                    };
                }
            }
        }
        self.canvas_gesture.route(ctx, raw);
''')
    replace(host,
'''        self.canvas_gesture.apply(&mut self.inner);
''',
'''        self.canvas_gesture.apply(&mut self.inner);
        // On some Android NativeActivity builds the 0.19 IME reset ACK never
        // arrives. Let the editor have first chance; commit explicitly only
        // if Escape is still pending and the text layer is still being edited.
        if self.artcraft_esc_pending && self.inner.ui.text_edit.is_some() {
            photocraft_ui_egui::type_tool::commit(&mut self.inner);
        }
        self.artcraft_esc_pending = false;
        if let Some(command) = self.artcraft_tool_pending.take() {
            if self.inner.ui.text_edit.is_none() {
                if let Err(error) = photocraft_ui_egui::menus::invoke(
                    &mut self.inner, ctx, command, serde_json::json!({})
                ) {
                    log::warn!("Tool shortcut: {error}");
                }
            }
        }
''')
    # A physical touchpad often routes two-finger drags as pointer MOVE,
    # not AXIS_VSCROLL. NativeActivity must convert that gesture before
    # pointer emulation can select menu rows (do not intercept touchscreen).
    replace(activity,
'''    private long artcraftLastKeyTime = -1L;
''',
'''    private boolean artcraftTrackpadMoving;
    private float artcraftTrackpadX;
    private float artcraftTrackpadY;

    @Override
    public boolean dispatchTouchEvent(android.view.MotionEvent event) {
        int source = event.getSource();
        boolean touchpad = (source & android.view.InputDevice.SOURCE_TOUCHPAD)
            == android.view.InputDevice.SOURCE_TOUCHPAD;
        boolean mouse = (source & android.view.InputDevice.SOURCE_MOUSE)
            == android.view.InputDevice.SOURCE_MOUSE;
        if ((touchpad || mouse) && event.getPointerCount() >= 2) {
            float cx = (event.getX(0) + event.getX(1)) / 2.0f;
            float cy = (event.getY(0) + event.getY(1)) / 2.0f;
            if (event.getActionMasked() == android.view.MotionEvent.ACTION_MOVE
                    && artcraftTrackpadMoving) {
                float dx = cx - artcraftTrackpadX;
                float dy = cy - artcraftTrackpadY;
                if ((Math.abs(dx) > .1f || Math.abs(dy) > .1f)
                    && artcraftTrackpadScroll.size() < 32) {
                    android.view.View decor = getWindow().getDecorView();
                    // Rust's standard wheel conversion multiplies by 42.
                    artcraftTrackpadScroll.offer(dx / 42.0f + "," + dy / 42.0f
                        + "," + cx + "," + cy
                        + "," + decor.getWidth() + "," + decor.getHeight());
                }
            }
            artcraftTrackpadX = cx;
            artcraftTrackpadY = cy;
            artcraftTrackpadMoving = true;
        } else {
            artcraftTrackpadMoving = false;
        }
        return super.dispatchTouchEvent(event);
    }

    private long artcraftLastKeyTime = -1L;
''')

    # The slim Shortcut Pad's held keys are emitted as balanced egui events,
    # and its keyboard button opens the existing NativeActivity IME host.
    replace(host,
'''        self.touch_scroll.route(ctx, raw);
''',
'''        self.touch_scroll.route(ctx, raw);
        self.shortcut_pad.inject_controls(raw);
''')
    replace(host,
'''            13..=16 => {
''',
'''            17 => {
                if let Err(e) = self.bridge.show_native_keyboard() {
                    log::warn!("Shortcut Pad keyboard: {e}");
                }
            }
            13..=16 => {
''')
    replace(host,
'''    fn toggle_startup_updates(&self) -> Result<(), String> {
''',
'''    fn show_native_keyboard(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("imeShow"), jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn toggle_startup_updates(&self) -> Result<(), String> {
''')

    print("Prepared PhotoCraft Android.6 icon menu, font refresh and canvas view gestures.")

if __name__ == "__main__":
    main()
