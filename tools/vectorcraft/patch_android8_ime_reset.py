"""Complete Android IME reset requests with an ordered, generation-guarded Java fence.

The pinned backend only hides/shows the IME and ignores request_id. Upstream
VectorCraft waits for that ID after retargeting composition, so later commits
can remain blocked. Never fabricate completion without resetting the host.
"""
from pathlib import Path
import sys
from patch_android8_wheel_touch import once

def patch(root):
    a=root/'adapters/vectorcraft'
    java=a/'java/com/artcraft/vectorcraft/VectorCraftActivity.java'
    once(java,'    public String imePoll() {', '''    private long vcImeGeneration = 0L;
    private boolean vcImeResetting = false;
    public void vcResetIme(long requestId) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed() || imeView == null) return;
            InputMethodManager imm = (InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
            if (imm == null) return;
            // All InputConnection callbacks and this reset run on the UI thread.
            // Invalidate the old connection before clearing its composing buffer.
            vcImeResetting = true;
            vcImeGeneration++;
            imeEvents.clear();
            android.view.inputmethod.BaseInputConnection.removeComposingSpans(imeView.getText());
            imeView.setText("");
            // A document opened via SAF can leave the hidden input host
            // invisible/unfocused even though the Type editor requests IME.
            // Restore only the active Type route; do not steal focus from
            // shortcuts, dialogs, or a non-editing canvas.
            if (imeWanted) {
                imeView.setVisibility(View.VISIBLE);
                imeView.setFocusable(true);
                imeView.setFocusableInTouchMode(true);
                if (!imeView.isFocused()) imeView.requestFocus();
            }
            imm.restartInput(imeView);
            // Queue the matching fence before permitting fresh connection commits.
            imeEvents.offer("r" + Long.toUnsignedString(requestId));
            vcImeResetting = false;
            vcWakeNativeLoop();
        });
    }
    public String imePoll() {''')
    signature='public InputConnection onCreateInputConnection(EditorInfo outAttrs) {'
    once(java,signature,signature+'\n                    final long connectionGeneration = vcImeGeneration;')
    # Reject late callbacks from the invalidated InputConnection. A new connection
    # captures the current epoch and resumes only after the completion marker.
    for sig in (
        'public boolean commitText(CharSequence text, int newCursorPosition) {',
        'public boolean setComposingText(CharSequence text, int newCursorPosition) {',
        'public boolean finishComposingText() {',
        'public boolean deleteSurroundingText(int beforeLength, int afterLength) {',
        'public boolean performEditorAction(int actionCode) {',
        'public boolean sendKeyEvent(KeyEvent event) {',
    ):
        once(java,sig,sig+'\n                            if (vcImeResetting || connectionGeneration != vcImeGeneration) return false;')
    # ImeResetId is intentionally opaque: it contains a viewport and a
    # process-unique serial, and cannot be reconstructed from an Android u64.
    # The upstream editor owns the exact request. Retain that request on the
    # egui Context, then match Java's *completed* serial to it before forwarding.
    # A stale, wrong-viewport or duplicate acknowledgement is discarded.
    upstream_ime=root/'source/vectorcraft/crates/ui-egui/src/ime.rs'
    once(upstream_ime,
        '    let request = ctx.request_ime_reset(viewport);',
        '''    let request = ctx.request_ime_reset(viewport);
    #[cfg(target_os = "android")]
    {
        let key = egui::Id::unique(("vc-android-ime-reset", viewport));
        ctx.data_mut(|data| {
            if let Some(request_id) = request {
                data.insert_temp(key, Some(request_id));
            } else {
                data.remove_temp::<Option<egui::ImeResetId>>(key);
            }
        });
    }''')
    # In imported Illustrator/AI artwork a selected live Text object may sit
    # below another hit-testable shape. A direct hit then returns that shape,
    # which made the Type tool silently fail to enter text editing. Prefer an
    # ordinary directly hit live-text object first; on Android only, fall back
    # to the already-selected live Text node IF the tap lands inside its
    # layout bounds. Do not edit paths, outlined glyphs or locked objects.
    live_type=root/'source/vectorcraft/crates/tools/src/text.rs'
    once(live_type, '''        let h = hit_test(cx.doc, p, vectorcraft_doc::hit::HitOptions { type_path_only: false, ..cx.hit_options() })?;
        let Some(NodeKind::Text(t)) = cx.doc.node(h.leaf).map(|n| &n.kind) else { return None };
        let lay = self.layout(t);
        let byte = vectorcraft_text::hit_byte(&lay, t.xf.inverse() * p);
        let mut out = self.finish(cx);
        self.start_editing(h.leaf, byte);
        self.remember(cx);
        self.clicks = (Some(p), 1);
        out.push(Action::Exec("select.set".into(), json!({"ids": [h.leaf.0]})));
        Some(out)''',
        '''        let h = hit_test(cx.doc, p, vectorcraft_doc::hit::HitOptions { type_path_only: false, ..cx.hit_options() });
        #[cfg(target_os = "android")]
        let text_id = h.and_then(|hit| {
            cx.doc.node(hit.leaf).is_some_and(|node| matches!(&node.kind, NodeKind::Text(_))).then_some(hit.leaf)
        }).or_else(|| {
            // A selected live text layer inside imported artwork can be hidden
            // behind another object's hit area. Only accept it within the
            // visible text layout; do not redirect unrelated canvas taps.
            cx.selection.objects.iter().copied().find(|id| {
                let Some(NodeKind::Text(t)) = cx.doc.node(*id).map(|n| &n.kind) else { return false };
                let local = t.xf.inverse() * p;
                self.layout(t).bounds.inflate(cx.tol(6.0), cx.tol(6.0)).contains(local)
            })
        })?;
        #[cfg(not(target_os = "android"))]
        let text_id = h?.leaf;
        let Some(NodeKind::Text(t)) = cx.doc.node(text_id).map(|n| &n.kind) else { return None };
        let lay = self.layout(t);
        let byte = vectorcraft_text::hit_byte(&lay, t.xf.inverse() * p);
        let mut out = self.finish(cx);
        self.start_editing(text_id, byte);
        self.remember(cx);
        self.clicks = (Some(p), 1);
        out.push(Action::Exec("select.set".into(), json!({"ids": [text_id.0]})));
        Some(out)''')
    assert 'cx.selection.objects.iter().copied().find' in live_type.read_text()
    assert 'let text_id = h?.leaf' in live_type.read_text()
    assert 'if (imeWanted)' in java.read_text()
    bridge=a/'src/ime_bridge.rs'
    once(bridge,
        '        pub fn poll(&mut self, raw: &mut egui::RawInput) {',
        '        pub fn poll(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {')
    once(bridge,
        '''                        if let Some(event) = translate(&event) {
                            raw.events.push(event);
                        }''',
        '''                        if let Some(encoded) = event.strip_prefix('r') {
                            // Never parse a numeric ID directly into opaque ImeResetId.
                            // Only the editor's actual outstanding request can be acked.
                            let key = egui::Id::unique(("vc-android-ime-reset", ctx.viewport_id()));
                            let matching = encoded.parse::<u64>().ok().and_then(|serial| {
                                ctx.data(|data| data.get_temp::<Option<egui::ImeResetId>>(key).flatten())
                                    .filter(|id| id.as_u64() == serial
                                        && id.viewport_id() == ctx.viewport_id())
                            });
                            if let Some(request_id) = matching {
                                ctx.data_mut(|data| {
                                    data.remove_temp::<Option<egui::ImeResetId>>(key);
                                });
                                raw.events.push(egui::Event::ImeResetCompleted { request_id });
                            }
                        } else if let Some(event) = translate(&event) {
                            raw.events.push(event);
                        }''')
    host=a/'src/lib.rs'
    once(host, '        self.ime.poll(raw);', '        self.ime.poll(ctx, raw);')
    assert 'payload.parse().ok()?' not in bridge.read_text()
    assert 'request_id: payload.parse()' not in bridge.read_text()
    # egui IdTypeMap::remove_temp<T> requires Default. ImeResetId is
    # deliberately opaque, non-default; an Option<Id> is Default + Clone.
    # This keeps the exact editor-owned request and discards stale completions.
    assert 'data.insert_temp(key, Some(request_id));' in upstream_ime.read_text()
    assert 'remove_temp::<Option<egui::ImeResetId>>(key)' in upstream_ime.read_text()
    assert 'get_temp::<Option<egui::ImeResetId>>(key).flatten()' in bridge.read_text()
    assert 'remove_temp::<Option<egui::ImeResetId>>(key)' in bridge.read_text()
    assert 'remove_temp::<egui::ImeResetId>' not in upstream_ime.read_text()
    assert 'remove_temp::<egui::ImeResetId>' not in bridge.read_text()
    print('PASS: IME generation isolation and real reset completion staged')

def vendor(root):
    lib=root/'vendor/android-activity/src/lib.rs'
    native=root/'vendor/android-activity/src/native_activity/mod.rs'
    winit=root/'vendor/winit/src/platform_impl/android/mod.rs'
    once(lib,'    pub fn show_soft_input(&self, show_implicit: bool) {', '''    #[cfg(feature = "native-activity")]
    pub fn vc_reset_ime(&self, request_id: u64) {
        self.inner.read().unwrap().vc_reset_ime(request_id);
    }
    pub fn show_soft_input(&self, show_implicit: bool) {''')
    once(native,'    pub fn show_soft_input(&self, show_implicit: bool) {', '''    pub fn vc_reset_ime(&self, request_id: u64) {
        let result = self.jvm.attach_current_thread(|env| -> jni::errors::Result<()> {
            env.call_method(self.activity.as_ref(), jni::jni_str!("vcResetIme"),
                jni::jni_sig!("(J)V"), &[jni::objects::JValue::Long(request_id as i64)])?;
            Ok(())
        });
        if let Err(error) = result { log::warn!("VectorCraft IME reset not completed: {error:?}"); }
    }
    pub fn show_soft_input(&self, show_implicit: bool) {''')
    once(winit,'''    pub fn reset_ime_with_request(&self, _request_id: u64) {
        // On NativeActivity the IME is driven by the system input method framework; asking the
        // IME to reset its state is done by toggling `set_ime_allowed` off and on again.
        self.set_ime_allowed(false);
        self.set_ime_allowed(true);
    }''','''    pub fn reset_ime_with_request(&self, request_id: u64) {
        // Java clears the old composition, invalidates old InputConnections,
        // restarts the IME, then queues this exact ID for the adapter to deliver.
        self.app.vc_reset_ime(request_id);
    }''')
    print('PASS: native reset request forwarded with its ID; no synthetic success')

if __name__=='__main__':
    (vendor if '--vendor' in sys.argv else patch)(Path(sys.argv[1]))
