"""VectorCraft Android.4: persist concise quit-stage breadcrumbs for next relaunch.

No new shutdown mechanism is introduced. This only instruments the
Android.2 native-loop-first quit path to locate intermittent Ctrl+Q ANRs
without reading private user documents, IME content or file paths.
The existing Diagnostic Session's prior_process_stage shows the last
persisted milestone on next launch. Logcat has the same milestones.
"""
from pathlib import Path
import sys

def once(s, old, new):
    n=s.count(old)
    if n != 1:
        raise ValueError(f"Android.4 quit-trace anchor drift ({n}): {old[:95]}")
    return s.replace(old,new,1)

def patch(root: Path):
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    s=once(s,'''    public void vcFinishAfterQuit() {''', '''    // Fixed, non-sensitive lifecycle stage names only. The next launch's
    // diagnostic snapshot exposes last_stage as prior_process_stage.
    public void vcMarkNativeQuitStage(String stage) {
        if (!("native_close_requested".equals(stage)
             || "native_loop_returned".equals(stage)
             || "java_finish_requested".equals(stage)
             || "java_finish_enter".equals(stage)
             || "java_already_finishing".equals(stage)
             || "on_destroy_enter".equals(stage)
             || "on_destroy_return".equals(stage))) return;
        getSharedPreferences("vc_diagnostics", MODE_PRIVATE).edit()
            .putString("last_stage", "VC_QUIT4:" + stage).apply();
        Log.i(TAG, "VC_QUIT4 stage=" + stage);
    }

    public void vcFinishAfterQuit() {
        vcMarkNativeQuitStage("java_finish_requested");''')
    // Android.13 and Android.14 already switched this native Activity to
    // finish() (not finishAndRemoveTask), with a legacy finish_requested
    // diagnostic write. Preserve that tested lifecycle behavior.
    s=once(s,'''            if (isFinishing() || isDestroyed()) return;
            Log.i(TAG, "VC_QUIT_ANDROID2 stage=java_finish_after_native_return");''',
    '''            if (isFinishing() || isDestroyed()) {
                vcMarkNativeQuitStage("java_already_finishing");
                return;
            }
            vcMarkNativeQuitStage("java_finish_enter");
            Log.i(TAG, "VC_QUIT_ANDROID2 stage=java_finish_after_native_return");''')
    s=once(s,'''            // Keep a persisted stage marker for diagnosing cold relaunch.
            getSharedPreferences("vc_diagnostics", MODE_PRIVATE).edit()
                .putString("last_stage", "finish_requested").apply();
            finish();''',
    '''            // VC_QUIT4 already saved a more specific lifecycle stage.
            // Avoid overwriting it with the old generic finish_requested.
            finish();''')
    s=once(s,'''    protected void onDestroy() {
        imeWanted=false;''',
    '''    protected void onDestroy() {
        vcMarkNativeQuitStage("on_destroy_enter");
        imeWanted=false;''')
    s=once(s,'''        io.shutdown();
        super.onDestroy();
    }''',
    '''        io.shutdown();
        super.onDestroy();
        vcMarkNativeQuitStage("on_destroy_return");
    }''')
    java.write_text(s)

    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    s=once(s,'''    fn finish_android_after_quit(&self) -> Result<(), String> {''',
    '''    fn mark_quit_stage(&self, stage: &str) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value=JObject::from(env.new_string(stage)?);
            env.call_method(&*activity, jni_str!("vcMarkNativeQuitStage"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&value)])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn finish_android_after_quit(&self) -> Result<(), String> {''')
    s=once(s,'''            self.vc_quit_after_native.store(true, Ordering::Release);
            log::info!("VC_QUIT_ANDROID2 stage=native_close_requested");''',
    '''            self.vc_quit_after_native.store(true, Ordering::Release);
            if let Err(error)=self.bridge.mark_quit_stage("native_close_requested") {
                log::warn!("VC_QUIT4 stage marker unavailable: {error}");
            }
            log::info!("VC_QUIT_ANDROID2 stage=native_close_requested");''')
    s=once(s,'''        log::info!("VC_QUIT_ANDROID2 stage=native_loop_returned");
        match bridge.finish_android_after_quit() {''',
    '''        log::info!("VC_QUIT_ANDROID2 stage=native_loop_returned");
        if let Err(error)=bridge.mark_quit_stage("native_loop_returned") {
            log::warn!("VC_QUIT4 stage marker unavailable: {error}");
        }
        match bridge.finish_android_after_quit() {''')
    rust.write_text(s)
    print("PASS: Android.4 no-data quit stage breadcrumbs before and after native event-loop return; D/S/C unchanged")

if __name__=="__main__":
    patch(Path(sys.argv[1]))
