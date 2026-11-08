"""VectorCraft Android.14 diagnostics-only overlay.

One disposable build to identify runtime failure layers before more behavioural
fixes. Captures bounded shortcut classes, focus/mode transitions, startup and
quit stage codes. NEVER records typed text, paths, filenames, clipboard data,
document contents, or network requests. Clipboard export is user-initiated.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    java = root / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s = java.read_text()
    s = once(s, '    private volatile boolean nativeEditorReady;', '''    private volatile boolean nativeEditorReady;
    // Small privacy-safe counters and stage names; no character streams.
    private final java.util.concurrent.atomic.AtomicLong vcDiagKeyDowns =
        new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcDiagShortcutDowns =
        new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcDiagCopyRequests =
        new java.util.concurrent.atomic.AtomicLong();
    private volatile String vcDiagLastShortcut = "none";
    private volatile String vcDiagStartupStage = "activity_constructed";
    private volatile String vcDiagPreviousStage = "unknown";
    private volatile String vcDiagPixel = "not sampled";
    private volatile int vcDiagPixelsChecked = 0;

    public String vcDiagnosticSnapshot() {
        return "java_stage=" + vcDiagStartupStage
            + "\\nprior_process_stage=" + vcDiagPreviousStage
            + "\\npixelcopy=" + vcDiagPixel
            + "; samples=" + vcDiagPixelsChecked
            + "; verified_frames=" + verifiedNativeFrames
            + "\\nnative_editor_ready=" + nativeEditorReady
            + "; startup_cover=" + (startupCover != null)
            + "\\nime_requested=" + imeWanted
            + "; ime_shortcut_mode=" + hardwareShortcutMode
            + "; pending_physical=" + physicalShortcutKeys.size()
            + "; pending_ctrl_quit=" + hiddenImeCloseKeys.size()
            + "\\njava_key_downs=" + vcDiagKeyDowns.get()
            + "; shortcut_downs=" + vcDiagShortcutDowns.get()
            + "; last_shortcut=" + vcDiagLastShortcut;
    }

    public void vcCopyDiagnosticReport(String report) {
        // Copy only after the user's button press, no auto-sharing/uploading.
        if (report == null || report.length() > 12000) return;
        runOnUiThread(() -> {
            android.content.ClipboardManager clipboard =
                (android.content.ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard != null) {
                clipboard.setPrimaryClip(android.content.ClipData.newPlainText(
                    "VectorCraft Diagnostic Report", report));
                vcDiagCopyRequests.incrementAndGet();
            }
        });
    }
''')
    s = once(s, '''        Log.i(TAG, "VC_STARTUP " + stage + "=" + ((android.os.SystemClock.elapsedRealtimeNanos()-activityStartNs)/1000000L) + "ms");''',
    '''        vcDiagStartupStage = stage + "@" +
            ((android.os.SystemClock.elapsedRealtimeNanos()-activityStartNs)/1000000L) + "ms";
        // Keep only stage names/timing for the next cold relaunch; no user data.
        getSharedPreferences("vc_diagnostics", MODE_PRIVATE).edit()
            .putString("last_stage", vcDiagStartupStage).apply();
        Log.i(TAG, "VC_STARTUP " + vcDiagStartupStage);''')
    s = once(s, '''        super.onCreate(savedInstanceState);
        showStartupCover();''', '''        super.onCreate(savedInstanceState);
        vcDiagPreviousStage = getSharedPreferences("vc_diagnostics", MODE_PRIVATE)
            .getString("last_stage", "unknown");
        showStartupCover();''')
    s = once(s, '''            verifiedNativeFrames = painted ? verifiedNativeFrames + 1 : 0;''',
    '''            vcDiagPixelsChecked++;
            vcDiagPixel = "result=" + result + "; varied=" + varied
                + "; contrast=" + (max-min) + "; painted=" + painted;
            verifiedNativeFrames = painted ? verifiedNativeFrames + 1 : 0;''')
    # Native key source instrumentation, no text, no passwords.
    s = once(s, '''        final int key = event.getKeyCode();
        final boolean close = key == KeyEvent.KEYCODE_W || key == KeyEvent.KEYCODE_Q;''',
    '''        final int key = event.getKeyCode();
        if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
            vcDiagKeyDowns.incrementAndGet();
            String shortcut = null;
            switch (key) {
                case KeyEvent.KEYCODE_V: shortcut = "V"; break;
                case KeyEvent.KEYCODE_T: shortcut = "T"; break;
                case KeyEvent.KEYCODE_S: shortcut = "S"; break;
                case KeyEvent.KEYCODE_D: shortcut = "D"; break;
                case KeyEvent.KEYCODE_C: shortcut = "C"; break;
                case KeyEvent.KEYCODE_ESCAPE: shortcut = "ESC"; break;
                case KeyEvent.KEYCODE_W: if (event.isCtrlPressed()) shortcut = "CTRL_W"; break;
                case KeyEvent.KEYCODE_Q: if (event.isCtrlPressed()) shortcut = "CTRL_Q"; break;
                default: break;
            }
            if (shortcut != null) {
                vcDiagShortcutDowns.incrementAndGet();
                // Do not record character identity while the Type tool owns
                // text input. Only the physical-key route class is reported.
                vcDiagLastShortcut = (hardwareShortcutMode == 0
                    ? "typing_or_unknown" : shortcut)
                    + "/mode=" + hardwareShortcutMode
                    + "/ime=" + imeWanted;
            }
        }
        final boolean close = key == KeyEvent.KEYCODE_W || key == KeyEvent.KEYCODE_Q;''')
    s = once(s, '''            // finish() permits normal onPause/onStop/onDestroy teardown and
            // avoids task-removal races when user immediately reopens the app.
            finish();''',
    '''            // Keep a persisted stage marker for diagnosing cold relaunch.
            getSharedPreferences("vc_diagnostics", MODE_PRIVATE).edit()
                .putString("last_stage", "finish_requested").apply();
            finish();''')
    java.write_text(s)

    rust = root / "adapters/vectorcraft/src/lib.rs"
    s = rust.read_text()
    s = once(s, '''    fn keyboard_focus(&self) -> Result<String,String> {''',
    '''    fn diagnostic_snapshot(&self) -> Result<String, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let object = env.call_method(&*activity, jni_str!("vcDiagnosticSnapshot"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            let string = JString::cast_local(env, object)?;
            string.try_to_string(env)
        }).map_err(|error| error.to_string())
    }

    fn copy_diagnostic_report(&self, report: &str) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let string = env.new_string(report)?;
            let object = JObject::from(string);
            env.call_method(&*activity, jni_str!("vcCopyDiagnosticReport"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&object)])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn keyboard_focus(&self) -> Result<String,String> {''')
    s = once(s, '''    keyboard_diagnostics_open: bool,''',
    '''    keyboard_diagnostics_open: bool,
    vc_diag_recording: bool,
    vc_diag_started: Option<std::time::Instant>,
    vc_diag_last_state: String,
    vc_diag_history: std::collections::VecDeque<String>,
    vc_diag_snapshot: String,
    vc_diag_note: String,
    vc_diag_egui_shortcuts: u64,''')
    s = once(s, '''                keyboard_diagnostics_open: false,''',
    '''                keyboard_diagnostics_open: false,
                vc_diag_recording: false,
                vc_diag_started: None,
                vc_diag_last_state: String::new(),
                vc_diag_history: std::collections::VecDeque::new(),
                vc_diag_snapshot: String::new(),
                vc_diag_note: "Start capture, reproduce, then Copy Report.".into(),
                vc_diag_egui_shortcuts: 0,''')

    s = once(s, '''        let selection_idle = matches!(self.inner.session.tool_id(), "selection" | "directSelection")''',
    '''        // Diagnostic only; never consume, synthesize or change key input.
        // This point is after the direct Save Changes route, and before the
        // direct tool-selection route.
        if self.vc_diag_recording {
            let state = format!(
                "tool={} editing={} field={} composing={} dialog={} mode={} egui_focus={}",
                self.inner.session.tool_id(), editing, field_focused, composing,
                self.inner.ui.dialog.as_ref().map(|d|d.kind.as_str()).unwrap_or("none"),
                self.last_hardware_shortcut_mode, raw.focused);
            if state != self.vc_diag_last_state {
                self.vc_diag_last_state = state.clone();
                let ms = self.vc_diag_started.map_or(0,|t|t.elapsed().as_millis());
                self.vc_diag_history.push_back(format!("+{ms}ms {state}"));
            }
            if !editing && !composing && !field_focused {
                for event in &raw.events {
                    if let egui::Event::Key {
                        key, physical_key, pressed: true, repeat: false, ..
                    } = event {
                        let key=physical_key.unwrap_or(*key);
                        if matches!(key, egui::Key::V | egui::Key::T |
                            egui::Key::S | egui::Key::D | egui::Key::C |
                            egui::Key::W | egui::Key::Q | egui::Key::Escape) {
                            self.vc_diag_egui_shortcuts += 1;
                            self.vc_diag_history.push_back(format!(
                                "+{}ms egui_shortcut={key:?}",
                                self.vc_diag_started.map_or(0,|t|t.elapsed().as_millis())));
                        }
                    }
                }
            }
            while self.vc_diag_history.len() > 60 {
                self.vc_diag_history.pop_front();
            }
        }
        let selection_idle = matches!(self.inner.session.tool_id(), "selection" | "directSelection")''')
    s = once(s, '''        if menu & 128 != 0 {self.keyboard_diagnostics_open=true;}''',
    '''        if menu & 128 != 0 {self.keyboard_diagnostics_open=true;}''')
    s = once(s, '''            egui::Window::new("Keyboard Diagnostics").open(&mut self.keyboard_diagnostics_open)''',
    '''            let mut vc_diag_start = false;
            let mut vc_diag_stop = false;
            let mut vc_diag_copy = false;
            let mut vc_diag_refresh = false;
            let diagnostic_history = self.vc_diag_history.iter()
                .cloned().collect::<Vec<_>>().join("\\n");
            let diagnostic_state = if self.vc_diag_recording {"Recording"} else {"Stopped"};
            let diagnostic_java = self.vc_diag_snapshot.clone();
            let diagnostic_note = self.vc_diag_note.clone();
            egui::Window::new("Keyboard Diagnostics").open(&mut self.keyboard_diagnostics_open)''')
    s = once(s, '''                    ui.small("Includes idle intervals. GPU execution time is not measured.");''',
    '''                    ui.small("Includes idle intervals. GPU execution time is not measured.");
                    ui.separator();
                    ui.heading("Diagnostic Session");
                    ui.label("Records only shortcut classes, focus/mode transitions, startup and quit stages.");
                    ui.label("No typed text, document content, filenames, passwords or URLs.");
                    ui.horizontal(|ui| {
                        if ui.button("Start / Reset").clicked(){vc_diag_start=true;}
                        if ui.button("Stop").clicked(){vc_diag_stop=true;}
                        if ui.button("Refresh Snapshot").clicked(){vc_diag_refresh=true;}
                        if ui.button("Copy Report").clicked(){vc_diag_copy=true;}
                    });
                    ui.label(format!("Status: {diagnostic_state}"));
                    ui.label(diagnostic_note);
                    egui::ScrollArea::vertical().max_height(190.0).show(ui, |ui| {
                        ui.monospace(&diagnostic_java);
                        ui.monospace(&diagnostic_history);
                    });''')
    s = once(s, '''        } else {winit::platform::android::vc_keyboard_diagnostics(false);}''',
    '''            if vc_diag_start {
                self.vc_diag_recording=true;
                self.vc_diag_started=Some(std::time::Instant::now());
                self.vc_diag_history.clear();
                self.vc_diag_last_state.clear();
                self.vc_diag_egui_shortcuts=0;
                self.vc_diag_note="Capture started. Reproduce failure, Stop, then Copy Report.".into();
            }
            if vc_diag_stop {
                self.vc_diag_recording=false;
                self.vc_diag_note="Capture stopped. Press Copy Report and paste in ChatGPT.".into();
            }
            if vc_diag_refresh || vc_diag_start || vc_diag_copy {
                self.vc_diag_snapshot=self.bridge.diagnostic_snapshot()
                    .unwrap_or_else(|error|format!("Java snapshot error: {error}"));
            }
            if vc_diag_copy {
                let elapsed=self.vc_diag_started.map_or(0,|t|t.elapsed().as_millis());
                let report=format!(
                    "VectorCraft Android.14 Diagnostic Session\\n\
                     elapsed_ms={elapsed}\\n\
                     egui_shortcut_receipts={}\\n\
                     tool={} editing={} composing={} dialog={}\\n\
                     last_keyboard_gate={}\\n\
                     last_keyboard_command={}\\n\
                     java_snapshot:\\n{}\\n\
                     transition_log:\\n{}\\n",
                    self.vc_diag_egui_shortcuts,
                    self.inner.session.tool_id(),
                    self.inner.session.tool_wants_text(),
                    self.inner.session.tool_composing(),
                    self.inner.ui.dialog.as_ref().map(|d|d.kind.as_str()).unwrap_or("none"),
                    self.keyboard_gate,
                    ctx.data(|d|d.get_temp::<String>(egui::Id::new("vc.keyboard.command")))
                        .unwrap_or_else(||"none".into()),
                    self.vc_diag_snapshot,
                    self.vc_diag_history.iter().cloned().collect::<Vec<_>>().join("\\n"));
                match self.bridge.copy_diagnostic_report(&report) {
                    Ok(()) => self.vc_diag_note="Report copied. Paste it into ChatGPT.".into(),
                    Err(error) => self.vc_diag_note=format!("Copy unavailable: {error}"),
                }
            }
        } else {winit::platform::android::vc_keyboard_diagnostics(false);}''')

    rust.write_text(s)
    print("PASS: VectorCraft Android.14 session diagnostics, manual clipboard export, no text capture")

if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
