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
    from patch_keyboard_diagnostics_v021 import patch as diagnostics
    diagnostics(root)


def patch_adapter(root):
    p=root/'adapters/vectorcraft/src/lib.rs';s=p.read_text()
    start=s.index('        // Treat Ctrl+Q as a native application quit request');end=s.index('        let selection_idle',start)
    s=s[:start]+'''        // Finish inline editing before the normal upstream close/quit command.
        let close_chord = !modal && !field_focused && !composing && editing
            && raw.events.iter().any(|e| matches!(e, egui::Event::Key {
                key: egui::Key::W | egui::Key::Q, pressed: true, repeat: false, modifiers, ..
            } if modifiers.command && !modifiers.alt && !modifiers.shift));
        if close_chord {
            let view = self.inner.view_info();
            match self.inner.session.tool_key(ToolKey::Escape, Mods::default(), view) {
                Ok(requests) => for request in requests {
                    if let UiRequest::SwitchTool(tool) = request { self.inner.select_tool(&tool); }
                },
                Err(error) => log::warn!("Close edit commit failed: {error}"),
            }
            if !self.inner.session.tool_wants_text() {
                if let Err(error) = self.bridge.end_type_editing() { log::warn!("Close focus: {error}"); }
            }
        }
'''+s[end:]
    start=s.index('                CanvasHardwareCommand::Selection\n');end=s.index('\n            }\n            if handled',start)
    s=s[:start]+'''                CanvasHardwareCommand::Selection | CanvasHardwareCommand::Type
                | CanvasHardwareCommand::Pen => {}'''+s[end:]
    s=s.replace('AndroidModifiers, AndroidMenuScrollSmoother,','AndroidModifiers,').replace('consume_type_close_chord, ','')
    s=s.replace('    menu_scroll: AndroidMenuScrollSmoother,\n','').replace('                menu_scroll: AndroidMenuScrollSmoother::default(),\n','')
    s=once(s,'        self.menu_scroll.apply(ctx, raw);','        // egui is the only scroll integrator; preserve delta and phase.')
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
    let result=match key {
        Key::C|Key::Escape=>app.run("ui.dialog.cancel",json!({})),
        Key::D=>app.run("ui.dialog.set",json!({"field":"discard","value":true}))
            .and_then(|_|app.run("ui.dialog.confirm",json!({}))),
        Key::S=>app.run("ui.dialog.confirm",json!({})),
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
    s=s[:start]+'''            pixels.recycle();
            // Probe begins after a second UI traversal. A presented dark frame
            // is valid; never use theme brightness as readiness detection.
            if (result == PixelCopy.SUCCESS) {
                startupStage("first_presented_frame");
                nativeEditorReady = true;
                dismissStartupCover();
            } else if (!isFinishing() && !isDestroyed()) {
                splashHandler.postDelayed(this::probeFirstPresentedFrame, 16);
            }'''+s[end:]
    s=once(s,'        splash.setKeepOnScreenCondition(() -> !nativeEditorReady);','''        // Do not block Android pre-draw while waiting for its native surface.
        // The app cover remains until PixelCopy confirms a presented buffer.
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
