"""Replace Android.9 workarounds in the isolated, pinned VectorCraft builder."""
from pathlib import Path
import shutil
import sys
from backend_stability import once
HERE=Path(__file__).parent


def patch(root):
    # Apply backend changes AFTER the builder's vendor copy, preserving non-Android patches.
    (root/'tools').mkdir(exist_ok=True)
    shutil.copyfile(HERE/'backend_stability.py', root/'tools/vectorcraft_backend_stability.py')
    p=root/'lib/build-common.sh';s=p.read_text()
    anchor='echo "Vendoring the mouse/scroll-aware winit for $TITLE..."'
    at=s.index(anchor);end=s.index("python3 - \"$SRC/Cargo.toml\" <<'PY'",at)
    s=s[:end]+'''if [[ "$APP" == "vectorcraft" ]]; then
    python3 "$ROOT/tools/vectorcraft_backend_stability.py" "$SRC/vendor/winit"
fi
'''+s[end:];p.write_text(s)
    patch_adapter(root)
    patch_dialog(root)
    patch_startup(root)
    from patch_smooth_menu_scroll_v021 import patch as smooth_menu
    smooth_menu(root)
    from patch_keyboard_diagnostics_v021 import patch as diagnostics
    diagnostics(root)


def patch_adapter(root):
    p=root/'adapters/vectorcraft/src/lib.rs';s=p.read_text()
    start=s.index('        // Treat Ctrl+Q as a native application quit request');end=s.index('        let selection_idle',start)
    s=s[:start]+'''        // The Android shell owns Ctrl+W and Ctrl+Q even when Type holds focus.
        // Do not invoke upstream twice: consume only the matching command press.
        let close_request = if !modal && !composing {
            raw.events.iter().find_map(|event| match event {
                egui::Event::Key {
                    key: egui::Key::W | egui::Key::Q,
                    pressed: true, repeat: false, modifiers, ..
                } if (modifiers.command || modifiers.ctrl) && !modifiers.alt && !modifiers.shift => {
                    match event {
                        egui::Event::Key { key: egui::Key::Q, .. } => Some("app.quit"),
                        _ => Some("file.close"),
                    }
                }
                _ => None,
            })
        } else { None };
        if let Some(command) = close_request {
            raw.events.retain(|event| !matches!(event,
                egui::Event::Key {
                    key: egui::Key::W | egui::Key::Q,
                    pressed: true, modifiers, ..
                } if (modifiers.command || modifiers.ctrl) && !modifiers.alt && !modifiers.shift
            ));
            if editing {
                let view = self.inner.view_info();
                match self.inner.session.tool_key(ToolKey::Escape, Mods::default(), view) {
                    Ok(requests) => for request in requests {
                        if let UiRequest::SwitchTool(tool) = request {
                            self.inner.select_tool(&tool);
                        }
                    },
                    Err(error) => log::warn!("Close: Type commit failed: {error}"),
                }
            }
            if !self.inner.session.tool_wants_text() {
                ctx.memory_mut(|memory| {
                    if let Some(id) = memory.focused() { memory.surrender_focus(id); }
                });
                if let Err(error) = self.bridge.end_type_editing() {
                    log::warn!("Close: keyboard focus restore: {error}");
                }
                if let Err(error) = self.inner.run(command, serde_json::json!({})) {
                    log::warn!("Close/quit request {command} failed: {error}");
                }
            } else {
                log::warn!("Close/quit deferred while Type editor is still active");
            }
            ctx.request_repaint();
        }
'''+s[end:]
    start=s.index('                CanvasHardwareCommand::Selection\n');end=s.index('\n            }\n            if handled',start)
    s=s[:start]+'''                CanvasHardwareCommand::Selection | CanvasHardwareCommand::Type
                | CanvasHardwareCommand::Pen => {}'''+s[end:]
    s=s.replace('AndroidModifiers, AndroidMenuScrollSmoother,','AndroidModifiers,').replace('consume_type_close_chord, ','')
    s=s.replace('    menu_scroll: AndroidMenuScrollSmoother,\n','').replace('                menu_scroll: AndroidMenuScrollSmoother::default(),\n','')
    s=once(s,'        self.menu_scroll.apply(ctx, raw);','        // egui is the only scroll integrator; preserve delta and phase.')
    s=once(s,'    android_quit_finished: bool,','    android_quit_finished: bool,\n    last_type_editing: bool,')
    s=once(s,'                android_quit_finished: false,','                android_quit_finished: false,\n                last_type_editing: false,')
    s=once(s,'        self.inner.ui(ui);','''        self.inner.ui(ui);
        // Tool/menu changes can end Type without Escape. Restore keyboard
        // focus exactly once on this transition, never during composition.
        let editing_now = self.inner.session.tool_wants_text();
        if self.last_type_editing && !editing_now {
            ui.ctx().memory_mut(|memory| {
                if let Some(id) = memory.focused() { memory.surrender_focus(id); }
            });
            if let Err(error) = self.bridge.end_type_editing() {
                log::warn!("Type exit: keyboard focus handoff failed: {error}");
            }
        }
        self.last_type_editing = editing_now;''')
    s=once(s,'    fn end_type_editing(&self) -> Result<(), String> {','''    // Android's hidden EditText may consume Ctrl+W/Q before winit sees them.
    // Poll only these commands; ordinary native keyboard events remain as-is.
    fn poll_hidden_ime_close(&self) -> Result<i32, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcPollHiddenImeClose"),
                jni_sig!("()I"), &[])?.i()
        }).map_err(|error| error.to_string())
    }

    fn end_type_editing(&self) -> Result<(), String> {''')
    s=once(s,'        self.ime.poll(raw);','''        self.ime.poll(raw);
        match self.bridge.poll_hidden_ime_close() {
            Ok(code @ (51 | 45)) => {
                let key = if code == 51 { egui::Key::W } else { egui::Key::Q };
                raw.events.push(egui::Event::Key {
                    key, physical_key: Some(key), pressed: true, repeat: false,
                    modifiers: egui::Modifiers {
                        ctrl: true, command: true, ..egui::Modifiers::NONE
                    },
                });
            }
            Ok(_) => {}
            Err(error) => log::warn!("Hidden IME close-key poll failed: {error}"),
        }''')
    s=once(s,'        let allow_letters = !ctx.text_edit_focused() && !self.inner.session.tool_wants_text();',
        '        let allow_letters = !modal && !composing && !ctx.text_edit_focused() && !self.inner.session.tool_wants_text();')
    s=once(s,'            match self.bridge.finish_android_after_quit() {','''            self.persist_now();
            if let Err(error) = self.bridge.end_type_editing() { log::warn!("Quit IME cleanup: {error}"); }
            match self.bridge.finish_android_after_quit() {''')
    s=once(s,'        Box::new(move |_cc| {','''        Box::new(move |_cc| {
            log::info!("VC_STARTUP renderer_initialized={}ms", startup_instant.elapsed().as_millis());''')
    p.write_text(s)
    p=root/'adapters/vectorcraft/src/android_modifiers.rs';s=p.read_text()
    start=s.index('pub fn apply_android_modifiers(');end=s.index('/// On some Android',start)
    s=s[:start]+'''pub fn apply_android_modifiers(_state: &mut AndroidModifiers, _raw: &mut egui::RawInput) {
    // The final winit backend forwards authoritative per-event Android meta
    // snapshots. Do not overwrite egui's modifiers with incomplete key history.
}

'''+s[end:]
    for key,name in [('V','Selection'),('T','Type'),('P','Pen')]:
        s=once(s,f'egui::Key::{key} => return Some(CanvasHardwareCommand::{name}),',f'egui::Key::{key} => {{}},')
    start=s.index('/// Frame-paced menu scrolling');end=s.index('/// Minimal event counters',start);s=s[:start]+s[end:]
    s=s[:s.index('#[cfg(test)]\nmod tests {')]+(HERE/'android_input_tests.rs').read_text();p.write_text(s)


def patch_dialog(root):
    src=root/'source/vectorcraft/crates/ui-egui/src';p=src/'shortcuts.rs';s=p.read_text()
    # Handle Save Changes keys even if Android left egui's viewport unfocused.
    s=once(s,'''    if !(ctx.input(|input| input.focused) || app.forwarded_frame && ctx.viewport_id() == egui::ViewportId::ROOT) {''','''    #[cfg(any(target_os = "android", test))]
    if app.ui.dialog.as_ref().is_some_and(|d| d.kind == crate::unsaved::KIND)
        && ctx.input(|input| input.events.iter().any(|event| matches!(event,
            egui::Event::Key { pressed: true, .. })))
        && android_save_changes_key(app, ctx) { return; }
    if !(ctx.input(|input| input.focused) || app.forwarded_frame && ctx.viewport_id() == egui::ViewportId::ROOT) {''')
    s=once(s,'''    if app.ui.dialog.is_some() || app.ui.palette_open {
        crate::ime::controls_without_editor(app, ctx);''','''    if app.ui.dialog.is_some() || app.ui.palette_open {
        crate::ime::controls_without_editor(app, ctx);
        #[cfg(any(target_os = "android", test))]
        if android_save_changes_key(app, ctx) { return; }''')
    s+='''
// The normal once-per-frame shortcut dispatcher owns modal keyboard actions.
#[cfg(any(target_os = "android", test))]
fn android_save_changes_key(app: &mut VectorcraftApp, ctx: &egui::Context) -> bool {
    if !app.ui.dialog.as_ref().is_some_and(|d| d.kind == crate::unsaved::KIND) { return false; }
    let key=ctx.input(|i| i.events.iter().find_map(|e| match e {
        egui::Event::Key { key, physical_key, pressed:true, repeat:false, modifiers }
            if !modifiers.ctrl && !modifiers.command && !modifiers.alt && !modifiers.shift => {
                let k=physical_key.unwrap_or(*key);
                matches!(k,Key::D|Key::C|Key::S|Key::Escape).then_some(k)
            },
        _=>None,
    }));
    let Some(key)=key else { return true; };
    ctx.input_mut(|i| i.events.retain(|e| !matches!(e,
        egui::Event::Key{..}|egui::Event::Text(_)|egui::Event::Ime(_))));
    // ui.dialog.* are CONTROL-protocol requests, not app.run commands.
    // Call the same native dialog actions as the actual buttons; otherwise
    // all three keyboard actions fail silently in production.
    let result=match key {
        Key::C|Key::Escape=>{
            crate::dialogs::cancel(app);
            Ok(serde_json::Value::Null)
        },
        Key::D=>{
            if let Some(dialog)=app.ui.dialog.as_mut() {
                crate::dialogs::set_field(dialog,"discard".into(),json!(true));
            }
            crate::dialogs::confirm(app)
        },
        Key::S=>crate::dialogs::confirm(app),
        _=>return true,
    };
    ctx.data_mut(|d| d.insert_temp(egui::Id::new("vc.keyboard.command"),
        format!("Save Changes {:?}: {}",key,if result.is_ok(){"accepted"}else{"failed; document retained"})));
    if let Err(error)=result { app.status(error); }
    ctx.request_repaint();
    true
}
'''+(HERE/'android_stability_tests.rs').read_text();p.write_text(s)
    p=src/'dialogs.rs';s=p.read_text()
    for old,new in [
        ('widgets::primary_button_enabled(ui, label, ok_enabled).clicked()', 'widgets::primary_button_enabled(ui, if d.kind == crate::unsaved::KIND { "Save (S)" } else { label }, ok_enabled).clicked()'),
        ('if widgets::secondary_button(ui, label).clicked() {\n                if resets {','if widgets::secondary_button(ui, if d.kind == crate::unsaved::KIND && !resets { "Cancel (C)" } else { label }).clicked() {\n                if resets {'),
        ('discard = widgets::secondary_button(ui, label).clicked();','discard = widgets::secondary_button(ui, if d.kind == crate::unsaved::KIND { "Don\'t Save (D)" } else { label }).clicked();')]:
        s=once(s,old,new)
    p.write_text(s)


def patch_startup(root):
    p=root/'adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java';s=p.read_text()
    s=once(s,'    private long firstFrameProbeStartMs;','''    private final long activityStartNs = android.os.SystemClock.elapsedRealtimeNanos();
    private long firstFrameProbeStartMs;
    private void startupStage(String stage) {
        Log.i(TAG, "VC_STARTUP " + stage + "=" + ((android.os.SystemClock.elapsedRealtimeNanos()-activityStartNs)/1000000L) + "ms");
    }''')
    start=s.index('            int bright = 0, dark = 0;');end=s.index('\n        }, splashHandler);',start)
    s=s[:start]+'''            // PixelCopy.SUCCESS alone may copy only the GPU's initial black
            // clear, especially on a cold boot after clearing app data. Do not
            // expose the native SurfaceView until UI contrast is visible twice.
            int min = 255, max = 0, varied = 0;
            int first = pixels.getPixel(0, 0);
            if (result == PixelCopy.SUCCESS) {
                for (int y = 0; y < pixels.getHeight(); y++) {
                    for (int x = 0; x < pixels.getWidth(); x++) {
                        int p = pixels.getPixel(x, y);
                        int lum = (Color.red(p) * 3 + Color.green(p) * 6 + Color.blue(p)) / 10;
                        min = Math.min(min, lum);
                        max = Math.max(max, lum);
                        if (p != first) varied++;
                    }
                }
            }
            pixels.recycle();
            boolean painted = result == PixelCopy.SUCCESS && varied >= 4 && max - min >= 24;
            verifiedNativeFrames = painted ? verifiedNativeFrames + 1 : 0;
            if (verifiedNativeFrames >= 2) {
                startupStage("first_painted_editor");
                nativeEditorReady = true;
                dismissStartupCover();
            } else if (!isFinishing() && !isDestroyed()) {
                splashHandler.postDelayed(this::probeFirstPresentedFrame, 48);
            }'''+s[end:]
    s=once(s,'    private volatile boolean nativeEditorReady;','''    private volatile boolean nativeEditorReady;
    private final java.util.concurrent.ConcurrentLinkedQueue<Integer> hiddenImeCloseKeys =
        new java.util.concurrent.ConcurrentLinkedQueue<>();
    public int vcPollHiddenImeClose() {
        Integer key = hiddenImeCloseKeys.poll();
        return key == null ? 0 : key.intValue();
    }''')
    s=once(s,'    @Override\n    protected void onNewIntent(Intent intent) {','''    // Only Ctrl+W/Q from the focused hidden IME are forwarded. No typed
    // letters, clipboard data, or other hardware events are intercepted.
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        final int key = event.getKeyCode();
        final boolean close = key == KeyEvent.KEYCODE_W || key == KeyEvent.KEYCODE_Q;
        if (imeView != null && imeView.hasFocus() && close && event.isCtrlPressed()
                && !event.isAltPressed() && !event.isShiftPressed()) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                hiddenImeCloseKeys.offer(key);
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    protected void onNewIntent(Intent intent) {''')
    s=once(s,'        startupStage("activity_created");','''        // The Android 12 system splash stays until our branded native cover
        // exists, NOT until the native frame (which would deadlock pre-draw).
        // This closes the black flash between system splash and SurfaceView.
        final long coverDeadlineMs = android.os.SystemClock.uptimeMillis() + 3000L;
        splash.setKeepOnScreenCondition(() -> startupCover == null
            && android.os.SystemClock.uptimeMillis() < coverDeadlineMs);
        startupStage("activity_created");''')
    s=s.replace('            probeFirstPresentedFrame();','            startupStage("editor_traversal_ready");\n            probeFirstPresentedFrame();')
    s=once(s,'        firstFrameProbePending = true;','        startupStage("native_surface_ready");\n        firstFrameProbePending = true;')
    s=once(s,'    @Override\n    protected void onNewIntent(Intent intent) {','''    @Override
    protected void onDestroy() {
        imeWanted=false;
        splashHandler.removeCallbacksAndMessages(null);
        io.shutdown();
        super.onDestroy();
    }

    @Override
    protected void onNewIntent(Intent intent) {''')
    p.write_text(s)


if __name__=='__main__': patch(Path(sys.argv[1]))
