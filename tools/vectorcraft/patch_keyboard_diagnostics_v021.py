"""Latest-event diagnostics only; never collect typed text, paths or command parameters."""
from backend_stability import once


def patch(root):
    p=root/'adapters/vectorcraft/Cargo.toml';p.write_text(once(p.read_text(),'jni = "0.22"','jni = "0.22"\nwinit = { version = "0.30", default-features = false, features = ["android-native-activity"] }'))
    p=root/'adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java'
    p.write_text(once(p.read_text(),'    public String imePoll() {','''    private volatile String diagnosticFocus = "not sampled";
    public String vcKeyboardFocus() {
        runOnUiThread(() -> {
            View focus=getCurrentFocus();
            InputMethodManager imm=(InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
            diagnosticFocus="focus="+(focus==null?"none":focus.getClass().getSimpleName())
                +"; IME requested="+imeWanted+"; active="+(imm!=null && imeView!=null && imm.isActive(imeView));
        });
        return diagnosticFocus;
    }
    public String imePoll() {'''))
    p=root/'adapters/vectorcraft/src/lib.rs';s=p.read_text()
    at='    fn notify_native_ui_ready(&self) -> Result<(), String> {'
    s=once(s,at,'''    fn keyboard_focus(&self) -> Result<String,String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw=self.app.activity_as_ptr() as jni::sys::jobject;
            let activity=unsafe {env.as_cast_raw::<JObject>(&raw)?};
            let result=env.call_method(&*activity,jni_str!("vcKeyboardFocus"),jni_sig!("()Ljava/lang/String;"),&[]);
            if result.is_err() {env.exception_clear();}
            let object=result?.l()?;
            let value=JString::cast_local(env,object)?;
            value.try_to_string(env)
        }).map_err(|e|e.to_string())
    }

'''+at)
    s=once(s,'    android_quit_finished: bool,','''    android_quit_finished: bool,
    keyboard_diagnostics_open: bool,
    keyboard_receipts: u64,
    keyboard_last: String,
    keyboard_gate: String,
    last_frame_at: Option<std::time::Instant>,
    frame_intervals: std::collections::VecDeque<f64>,''')
    s=once(s,'                android_quit_finished: false,','''                android_quit_finished: false,
                keyboard_diagnostics_open: false,
                keyboard_receipts: 0,
                keyboard_last: String::new(),
                keyboard_gate: String::new(),
                last_frame_at: None,
                frame_intervals: std::collections::VecDeque::new(),''')
    at='        let modal = self.inner.ui.dialog.is_some() || self.inner.ui.palette_open;'
    s=once(s,at,at+'''
        let sensitive=editing || field_focused || composing;
        winit::platform::android::vc_keyboard_diagnostics(self.keyboard_diagnostics_open && !sensitive);
        self.keyboard_gate=if sensitive {"text/composition: identity redacted"}
            else if modal {"modal owns keys"} else {"upstream customizable keymap"}.into();
        if sensitive {self.keyboard_last="redacted during typing".into();}
        else if self.keyboard_diagnostics_open {
            for e in &raw.events {
                if let egui::Event::Key {key,physical_key,pressed,modifiers,..}=e {
                    self.keyboard_receipts+=1;
                    self.keyboard_last=format!("egui: {:?}/{:?}; down={}; {:?}",key,physical_key,pressed,modifiers);
                }
            }
        }
''')
    at='        system_fonts::install_system_fonts(ui.ctx());'
    s=once(s,at,'''        let now=std::time::Instant::now();
        if let Some(last)=self.last_frame_at.replace(now) {
            self.frame_intervals.push_back(now.duration_since(last).as_secs_f64()*1000.0);
            if self.frame_intervals.len()>120 {self.frame_intervals.pop_front();}
        }
'''+at)
    at='        if menu & 64 != 0 { self.android_tools_open = true; }'
    s=once(s,at,at+'''
        if menu & 128 != 0 {self.keyboard_diagnostics_open=true;}
        if self.keyboard_diagnostics_open {
            let sensitive=self.inner.session.tool_wants_text() || ctx.text_edit_focused() || self.inner.session.tool_composing();
            let (count,packet)=winit::platform::android::vc_keyboard_diagnostics(!sensitive);
            let focus=self.bridge.keyboard_focus().unwrap_or_else(|_|"focus unavailable".into());
            let command=ctx.data(|d|d.get_temp::<String>(egui::Id::new("vc.keyboard.command"))).unwrap_or_else(||"No command observed".into());
            let mut times:Vec<_>=self.frame_intervals.iter().copied().collect();times.sort_by(f64::total_cmp);
            let median=times.get(times.len()/2).copied().unwrap_or(0.0);
            let p95=times.get(times.len().saturating_sub(1)*95/100).copied().unwrap_or(0.0);
            egui::Window::new("Keyboard Diagnostics").open(&mut self.keyboard_diagnostics_open)
                .default_width(500.0).show(ctx,|ui| {
                    ui.label("Temporary diagnostics. No text, passwords or key history recorded.");
                    ui.monospace(format!("Native receipts: {count}; Android code: {}; down: {}; meta: {:#x}",packet & 0x7fffffff,packet & (1<<31)!=0,packet>>32));
                    ui.monospace(format!("egui receipts: {}",self.keyboard_receipts));
                    ui.monospace(&self.keyboard_last);ui.label(&self.keyboard_gate);ui.label(focus);
                    ui.label(format!("Tool: {}",self.inner.session.tool_id()));ui.label(command);
                    ui.label(format!("UI frame intervals: median {median:.2} ms; p95 {p95:.2} ms"));
                    ui.small("Includes idle intervals. GPU execution time is not measured.");
                });
        } else {winit::platform::android::vc_keyboard_diagnostics(false);}
''');p.write_text(s)
    src=root/'source/vectorcraft/crates/ui-egui/src'
    p=src/'menus/tree.rs';s=p.read_text();old='                c("Graphics Diagnostics…", "android.vectorcraft.diagnostics"),'
    if s.count(old)!=2: raise ValueError('Expected Vc and Help diagnostics entries')
    p.write_text(s.replace(old,old+'\n                c("Keyboard Diagnostics…", "android.vectorcraft.keyboardDiagnostics"),',1))
    p=src/'menus/run.rs';p.write_text(once(p.read_text(),'            "android.vectorcraft.diagnostics" => 64,','            "android.vectorcraft.diagnostics" => 64,\n            "android.vectorcraft.keyboardDiagnostics" => 128,'))
    p=src/'app/commands.rs';s=p.read_text()
    s=once(s,'        placing::settle_swatch_paste(self);','''        #[cfg(target_os="android")]
        if let Some(ctx)=&self.ui_ctx {
            ctx.data_mut(|d|d.insert_temp(egui::Id::new("vc.keyboard.command"),format!("Command {}: {}",id,if result.is_ok(){"accepted"}else{"failed"})));
        }
        placing::settle_swatch_paste(self);''')
    at='    pub fn select_tool(&mut self, id: &str) {'
    s=once(s,at,at+'''
        #[cfg(target_os="android")]
        if let Some(ctx)=&self.ui_ctx {
            ctx.data_mut(|d|d.insert_temp(egui::Id::new("vc.keyboard.command"),format!("Tool selected: {}",id)));
        }
''');p.write_text(s)
