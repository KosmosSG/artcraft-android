"""Android.9 isolated VectorCraft IME lifecycle, pen-hover and compact Vc wheel menu.

Runs AFTER Android.8 overlays, before expensive ARM64 compilation.
No production files, keys, desktop input handlers or published APKs are changed.
"""
from pathlib import Path
import sys
from patch_android8_wheel_touch import once


def in_method(path, beginning, ending, old, new):
    source = path.read_text()
    a = source.index(beginning)
    b = source.index(ending, a + len(beginning))
    part = source[a:b]
    if part.count(old) != 1:
        raise RuntimeError(f"{path}: expected one {old[:60]!r} in {beginning!r}, got {part.count(old)}")
    path.write_text(source[:a] + part.replace(old, new, 1) + source[b:])


def patch(root):
    adapter = root / "adapters/vectorcraft"
    java = adapter / "java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    host = adapter / "src/lib.rs"
    ui = root / "source/vectorcraft/crates/ui-egui/src"

    # Tokenize asynchronous hide/end/show operations. A close, SAF return, or
    # queued IME reset from the previous document must never steal the NEW
    # document's keyboard focus or discard its newly committed characters.
    once(java, '    private volatile boolean imeWanted = false;',
         '''    private volatile boolean imeWanted = false;
    private final java.util.concurrent.atomic.AtomicLong vcImeFocusEpoch =
        new java.util.concurrent.atomic.AtomicLong(0L);
    private volatile boolean vcPenHoverVisible = false;
    private volatile long vcPenHoverAtMs = 0L;
    private SurfaceView vcPenHoverSurface = null;''')
    in_method(java, '    public void imeShow() {',
              '    public void vcEndTypeEditing() {',
              '        final EditText view = imeView;',
              '''        final long focusToken = vcImeFocusEpoch.incrementAndGet();
        final EditText view = imeView;''')
    in_method(java, '    public void imeShow() {',
              '    public void vcEndTypeEditing() {',
              'if (!imeWanted) {', 'if (!imeWanted || vcImeFocusEpoch.get() != focusToken) {')
    in_method(java, '    public void imeShow() {',
              '    public void vcEndTypeEditing() {',
              '                view.setFocusable(true);',
              '''                view.setVisibility(View.VISIBLE);
                final boolean alreadyFocused = view.hasFocus();
                view.setFocusable(true);''')
    in_method(java, '    public void imeShow() {',
              '    public void vcEndTypeEditing() {',
              '                if (imm != null && imm.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT)) {',
              '''                if (imm != null && !alreadyFocused) {\n                    vcImeGeneration++;\n                    imm.restartInput(view);\n                }
                if (imm != null && imm.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT)) {''')
    # The same show callback has a retry closure: guard its own epoch, too.
    in_method(java, '    public void imeShow() {',
              '    public void vcEndTypeEditing() {',
              'if (!imeWanted) {', 'if (!imeWanted || vcImeFocusEpoch.get() != focusToken) {')

    in_method(java, '    public void vcEndTypeEditing() {',
              '    public void imeHide() {',
              '        imeWanted = false;',
              '''        final long focusToken = vcImeFocusEpoch.incrementAndGet();
        imeWanted = false;''')
    in_method(java, '    public void vcEndTypeEditing() {',
              '    public void imeHide() {',
              '        runOnUiThread(() -> {',
              '''        runOnUiThread(() -> {
            if (vcImeFocusEpoch.get() != focusToken || imeWanted) return;''')
    in_method(java, '    public void imeHide() {',
              '    public void vcResetIme(long requestId) {',
              '        imeWanted = false;',
              '''        final long focusToken = vcImeFocusEpoch.incrementAndGet();
        imeWanted = false;''')
    in_method(java, '    public void imeHide() {',
              '    public void vcResetIme(long requestId) {',
              '        runOnUiThread(() -> {',
              '''        runOnUiThread(() -> {
            if (vcImeFocusEpoch.get() != focusToken || imeWanted) return;''')
    # The scheduled SAF-return cleanup must recheck its precondition when
    # actually executed; otherwise it can cancel a subsequent Type editor.
    once(java, 'getWindow().getDecorView().post(this::vcEndTypeEditing);',
         '''getWindow().getDecorView().post(() -> {
                    if (!imeWanted && imeView != null && imeView.hasFocus()) vcEndTypeEditing();
                });''')
    in_method(java, '    public void vcResetIme(long requestId) {',
              '    public String imePoll() {',
              '        runOnUiThread(() -> {',
              '''        final long focusToken = vcImeFocusEpoch.get();
        runOnUiThread(() -> {
            if (vcImeFocusEpoch.get() != focusToken) {
                // Finish the old fence without touching the new editor's input.
                imeEvents.offer("r" + Long.toUnsignedString(requestId));
                vcWakeNativeLoop();
                return;
            }''')
    in_method(java, '    public void vcResetIme(long requestId) {',
              '    public String imePoll() {',
              '            imeEvents.clear();',
              '''            // Keep valid committed text; only stale preedit should be reset.
            imeEvents.removeIf(e -> e.startsWith("p") || e.startsWith("f"));''')

    # Synchronous queue invalidation plus epoch-guarded UI cleanup on a real
    # document UID change. The new session may start immediately: its later
    # imeShow increments the token and prevents this stale cleanup from running.
    once(java, '    public String imePoll() {',
         '''    public void vcDocumentChanged() {
        final long token = vcImeFocusEpoch.incrementAndGet();
        imeWanted = false;
        imeEvents.clear();
        runOnUiThread(() -> {
            if (vcImeFocusEpoch.get() != token || imeWanted) return;
            vcImeGeneration++;
            try {
                final EditText view = imeView;
                if (view != null) {
                    InputMethodManager imm =
                        (InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
                    if (imm != null) imm.hideSoftInputFromWindow(view.getWindowToken(), 0);
                    view.clearFocus();
                    view.setText("");
                }
                SurfaceView nativeSurface = findNativeSurface(getWindow().getDecorView());
                if (nativeSurface != null && nativeSurface.isShown()) nativeSurface.requestFocus();
                Log.i(TAG, "VC_IME_DOCUMENT_CHANGED: previous edit host cleared");
            } catch (RuntimeException error) {
                Log.w(TAG, "VC_IME_DOCUMENT_CHANGED failed", error);
            }
        });
    }

    public boolean vcStylusHoverActive() {
        return vcPenHoverVisible &&
            android.os.SystemClock.uptimeMillis() - vcPenHoverAtMs < 380L;
    }

    // This passive listener does NOT consume hover: winit receives the normal
    // native pen motion for its existing pointer/gesture processing.
    private void vcInstallPenHoverListener() {
        runOnUiThread(() -> {
            SurfaceView surface = findNativeSurface(getWindow().getDecorView());
            if (surface == null || surface == vcPenHoverSurface) return;
            vcPenHoverSurface = surface;
            surface.setOnHoverListener((view, motion) -> {
                if (motion.getPointerCount() < 1) return false;
                int type = motion.getToolType(0);
                if (type != android.view.MotionEvent.TOOL_TYPE_STYLUS &&
                    type != android.view.MotionEvent.TOOL_TYPE_ERASER) {
                    vcPenHoverVisible = false;
                    return false;
                }
                int action = motion.getActionMasked();
                if (action == android.view.MotionEvent.ACTION_HOVER_ENTER ||
                    action == android.view.MotionEvent.ACTION_HOVER_MOVE) {
                    vcPenHoverVisible = true;
                    vcPenHoverAtMs = android.os.SystemClock.uptimeMillis();
                } else if (action == android.view.MotionEvent.ACTION_HOVER_EXIT) {
                    vcPenHoverVisible = false;
                }
                return false;
            });
        });
    }

    public String imePoll() {''')
    once(java, '''    public void vcNativeUiReady() {
        // JNI is a signal''',
         '''    public void vcNativeUiReady() {
        vcInstallPenHoverListener();
        // JNI is a signal''')
    once(java, '''            nativePointerIconType = -1;
            applyImmersiveFullscreen();''',
         '''            nativePointerIconType = -1;
            vcPenHoverSurface = null;
            vcPenHoverVisible = false;
            vcInstallPenHoverListener();
            applyImmersiveFullscreen();''')

    once(host, '    fn files_dir(&self) -> Result<String, String> {',
         '''    fn vc_document_changed(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcDocumentChanged"), jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }
    fn vc_stylus_hovering(&self) -> Result<bool, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcStylusHoverActive"), jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| e.to_string())
    }
    fn files_dir(&self) -> Result<String, String> {''')
    once(host, '    stylus_device_scan_at: std::time::Instant,',
         '''    stylus_device_scan_at: std::time::Instant,
    vc_last_doc_uid: Option<u64>,''')
    once(host, '                stylus_device_scan_at: std::time::Instant::now(),',
         '''                stylus_device_scan_at: std::time::Instant::now(),
                vc_last_doc_uid: None,''')
    once(host, '        self.ime.poll(ctx, raw);',
         '''        // Compare immutable document UIDs, never tab positions. The
        // upstream tool is reset on close/switch, but its Android IME host
        // otherwise can remain focused and poison a newly created document.
        let current_uid = self.inner.session.active().map(|doc| doc.uid);
        if current_uid != self.vc_last_doc_uid {
            self.vc_last_doc_uid = current_uid;
            let reset_key = egui::Id::unique(("vc-android-ime-reset", ctx.viewport_id()));
            ctx.data_mut(|data| data.remove_temp::<Option<egui::ImeResetId>>(reset_key));
            if let Err(error) = self.bridge.vc_document_changed() {
                log::warn!("Type document transition focus cleanup failed: {error}");
            }
        }
        self.ime.poll(ctx, raw);''')
    # Wheel owns its approved hover highlights; avoid painting over it.
    with (adapter / "src/stylus_wheel.rs").open("a") as wheel_src:
        wheel_src.write("\nimpl Wheel { pub(crate) fn is_visible(&self) -> bool { self.open } }\n")
    once(host, '        self.stylus_wheel.render(ui);',
         '''        self.stylus_wheel.render(ui);
        // Draw a very light pen-hover marker only for a real hovering stylus.
        // Do not reinterpret touch, mouse, trackpad, or any wheel button input.
        let ctx = ui.ctx();
        if self.bridge.vc_stylus_hovering().unwrap_or(false)
            && !ctx.input(|i| i.pointer.any_down())
            && !self.inner.session.tool_wants_text()
            && self.inner.ui.dialog.is_none()\n            && !self.inner.ui.palette_open\n            && !self.stylus_wheel.is_visible()\n            && !egui::Popup::is_any_open(ctx)
        {
            if let Some(pos) = ctx.pointer_hover_pos() {
                let painter = ctx.layer_painter(egui::LayerId::new(
                    egui::Order::Foreground, egui::Id::new("vc-pencil-hover")));
                painter.circle_stroke(pos, 7.0,
                    egui::Stroke::new(1.2, egui::Color32::from_rgb(245, 154, 83)));
                painter.circle_filled(pos, 1.6, egui::Color32::from_rgb(245, 154, 83));
            }
        }''')

    # Group the controls in the ACTUAL top-left Vc launcher icon menu, not
    # just the unused desktop menus/tree entry. Preserve the persisted bit IDs.
    menus = ui / "menus.rs"
    once(menus, '''            let mut wheel_enabled = ANDROID_WHEEL_ENABLED.load(std::sync::atomic::Ordering::Acquire);
            if ui.checkbox(&mut wheel_enabled, "Stylus Wheel").changed() {
                clicked = Some(("android.vectorcraft.stylusWheel".into(), serde_json::json!({})));
                ui.close();
            }
            if ui.button("Customize Stylus Wheel…").clicked() {
                clicked = Some(("android.vectorcraft.stylusWheelCustomize".into(), serde_json::json!({})));
                ui.close();
            }''',
         '''            ui.menu_button("Stylus Wheel", |ui| {
                let mut wheel_enabled = ANDROID_WHEEL_ENABLED.load(std::sync::atomic::Ordering::Acquire);
                if ui.checkbox(&mut wheel_enabled, "Stylus Wheel On").changed() {
                    clicked = Some(("android.vectorcraft.stylusWheel".into(), serde_json::json!({})));
                    ui.close();
                }
                if ui.button("Customization").clicked() {
                    clicked = Some(("android.vectorcraft.stylusWheelCustomize".into(), serde_json::json!({})));
                    ui.close();
                }
            });''')
    once(ui / "menus/tree.rs",
         '''                c("Stylus Wheel", "android.vectorcraft.stylusWheel"),
                c("Customize Stylus Wheel…", "android.vectorcraft.stylusWheelCustomize"),''',
         '''                sub("Stylus Wheel", vec![
                    c("Stylus Wheel On", "android.vectorcraft.stylusWheel"),
                    c("Customization", "android.vectorcraft.stylusWheelCustomize"),
                ]),''')
    print("PASS: Android.9 IME document lifetime, adaptive cursor parity, passive hover, nested wheel menu")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
