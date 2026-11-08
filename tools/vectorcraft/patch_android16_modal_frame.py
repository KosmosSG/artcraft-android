"""VectorCraft Android.16: run Save Changes shortcuts inside the UI frame.

Device evidence: Android.15 recorded D docs=1->0 and S docs=1->1, but
neither transition became visible until ESC. Defer modal command execution
out of eframe::App::raw_input_hook into logic(), then repaint for a short,
bounded interval. Record Android SAF launch/result stage without filenames.
Other keyboard paths, renderer startup, and signing stay unchanged.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    s=once(s, "    vc_diag_last_modal_action: String,",
        """    vc_diag_last_modal_action: String,
    vc_modal_pending_action: Option<(egui::Key, &'static str)>,
    vc_modal_followup_repaints: u8,""")
    s=once(s, '                vc_diag_last_modal_action: "none".into(),',
        '''                vc_diag_last_modal_action: "none".into(),
                vc_modal_pending_action: None,
                vc_modal_followup_repaints: 0,''')
    start=s.index("            if let Some((key,source)) = modal_key {")
    # Preserve the enclosing saveChanges guard; replace its command body only.
    end=s.index("        }\n\n        // The Android shell owns Ctrl+W", start)
    s=s[:start]+'''            if let Some((key, source)) = modal_key {
                if self.vc_modal_pending_action.is_none() {
                    self.vc_modal_pending_action = Some((key, source));
                }
                // The action is run once in logic(), before the same frame's
                // normal document/dialog UI pass. Remove *all* paired
                // modal-only Key/Text events, avoiding stale C/S after D.
                raw.events.retain(|event| !match event {
                    egui::Event::Key {
                        key: logical, physical_key, pressed: true, ..
                    } => matches!(physical_key.unwrap_or(*logical),
                        egui::Key::D | egui::Key::S |
                        egui::Key::C | egui::Key::Escape),
                    egui::Event::Text(text) if text.len()==1 =>
                        matches!(text.as_str(), "d" | "D" | "s" | "S" | "c" | "C"),
                    _ => false,
                });
                ctx.request_repaint();
            }
'''+s[end:]
    anchor='''        // Deliver picker answers before the app's own logic runs, so '''
    replacement='''        // Android.15 accepted physical S/D but applied the action in the
        // pre-egui raw input hook. Do it here instead so the same UI frame
        // observes the updated document/dialog state without another ESC.
        if let Some((key, source)) = self.vc_modal_pending_action.take() {
            let before_docs = self.inner.session.documents().len();
            let before_uid = self.inner.ui.dialog.as_ref()
                .and_then(|d| d.fields.get("uid"))
                .and_then(serde_json::Value::as_u64);
            if self.inner.android_owner_unsaved_key(key) {
                let after_docs = self.inner.session.documents().len();
                let after_dialog = self.inner.ui.dialog.as_ref()
                    .map(|d| d.kind.as_str()).unwrap_or("none");
                self.vc_diag_last_modal_action = format!(
                    "key={key:?} route={source} docs={before_docs}->{after_docs} \
                     prior_uid_present={} dialog_after={after_dialog} phase=logic",
                    before_uid.is_some());
                if self.vc_diag_recording {
                    self.vc_diag_history.push_back(format!(
                        "+{}ms modal_action {}",
                        self.vc_diag_started.map_or(0, |t|t.elapsed().as_millis()),
                        self.vc_diag_last_modal_action));
                }
                // A short bounded series of redraws handles the Android
                // surface/focus transition without continuous 60Hz idling.
                self.vc_modal_followup_repaints = 8;
                ctx.request_repaint();
            }
        }
        if self.vc_modal_followup_repaints > 0 {
            self.vc_modal_followup_repaints -= 1;
            ctx.request_repaint_after(std::time::Duration::from_millis(16));
        }
'''+anchor
    s=once(s,anchor,replacement)
    rust.write_text(s)

    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    s=once(s,'    private volatile String vcDiagPixel = "not sampled";',
        '''    private volatile String vcDiagPixel = "not sampled";
    // Only SAF stage names. Never a picked file's name/path/URI.
    private volatile String vcDiagSavePickerStage = "none";''')
    s=once(s,'            + "\\\\nprior_process_stage=" + vcDiagPreviousStage',
        '''            + "\\\\nprior_process_stage=" + vcDiagPreviousStage
            + "\\\\nsave_picker_stage=" + vcDiagSavePickerStage''')
    # The request is made on Rust's thread; startActivityForResult is
    # executed asynchronously on the Java UI thread.
    s=once(s, '''    public void vcRequestSave(long id, String suggestedName, String mime) {
        runOnUiThread(() -> {
            try {''',
    '''    public void vcRequestSave(long id, String suggestedName, String mime) {
        vcDiagSavePickerStage = "queued_to_ui_thread";
        runOnUiThread(() -> {
            try {
                vcDiagSavePickerStage = "launching";''')
    s=once(s, '''                startActivityForResult(intent, REQ_SAVE);
            } catch (Exception e) {
                enqueueError(id, "save", e.toString());''',
    '''                startActivityForResult(intent, REQ_SAVE);
                vcDiagSavePickerStage = "launch_requested";
            } catch (Exception e) {
                vcDiagSavePickerStage = "launch_failed";
                enqueueError(id, "save", e.toString());''')
    s=once(s, '''        final String kind = requestCode == REQ_OPEN ? "open" : "save";
        if (resultCode != RESULT_OK || data == null) {''',
    '''        final String kind = requestCode == REQ_OPEN ? "open" : "save";
        if (requestCode == REQ_SAVE) {
            vcDiagSavePickerStage =
                resultCode == RESULT_OK && data != null ? "result_ok" : "cancelled";
        }
        if (resultCode != RESULT_OK || data == null) {''')
    s=once(s, '''                enqueuePaths(id, "save", new String[] { stage.getAbsolutePath() });
            } catch (Exception e) {
                enqueueError(id, kind, e.toString());''',
    '''                enqueuePaths(id, "save", new String[] { stage.getAbsolutePath() });
                vcDiagSavePickerStage = "answer_queued";
            } catch (Exception e) {
                vcDiagSavePickerStage = "result_processing_failed";
                enqueueError(id, kind, e.toString());''')
    # Frame probe explains 0 samples, without changing GPU startup behavior.
    s=once(s,'    private volatile String vcDiagSavePickerStage = "none";',
        '''    private volatile String vcDiagSavePickerStage = "none";
    private volatile String vcDiagFrameProbeStage = "not_started";''')
    s=once(s,'            + "\\\\nsave_picker_stage=" + vcDiagSavePickerStage',
        '''            + "\\\\nsave_picker_stage=" + vcDiagSavePickerStage
            + "\\\\nframe_probe_stage=" + vcDiagFrameProbeStage''')
    s=once(s,'''        if (nativeEditorReady || firstFrameProbePending) return;
        if (System.currentTimeMillis() - firstFrameProbeStartMs > 16000L) {''',
    '''        if (nativeEditorReady || firstFrameProbePending) return;
        vcDiagFrameProbeStage = "waiting_surface";
        if (System.currentTimeMillis() - firstFrameProbeStartMs > 16000L) {''')
    s=once(s, '''        firstFrameProbePending = true;
        // Sample enough of the SurfaceView''',
    '''        firstFrameProbePending = true;
        vcDiagFrameProbeStage = "pixelcopy_requested";
        // Sample enough of the SurfaceView''')
    s=once(s, '''            vcDiagPixelsChecked++;
            vcDiagPixel = "result=" + result''',
    '''            vcDiagFrameProbeStage = "pixelcopy_callback";
            vcDiagPixelsChecked++;
            vcDiagPixel = "result=" + result''')
    java.write_text(s)
    print("PASS: Android.16 modal actions deferred to UI logic with bounded repaint and privacy-safe SAF/frame stage diagnostic")

if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
