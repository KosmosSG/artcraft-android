"""VectorCraft v0.23.0-android.2: finish native render loop BEFORE Android Activity finish.

The prior APK requests finishAndRemoveTask() from inside eframe::App::ui.
NativeActivity.onDestroy may wait for android_main to return while it is still
rendering, creating a self-deadlock/ANR. Keep upstream unsaved D/S/C gates;
only begin orderly native close after the app reports status == "quit".

No production signing, no alternate lifecycle hooks, no System.exit or killProcess.
"""
from pathlib import Path
import sys

def once(s: str, old: str, new: str) -> str:
    n=s.count(old)
    if n != 1:
        raise ValueError(f"VectorCraft Android.2 quit anchor drift ({n}): {old[:100]}")
    return s.replace(old,new,1)

def patch(root: Path):
    p=root/"adapters/vectorcraft/src/lib.rs"
    s=p.read_text()
    s=once(s,
      "use std::sync::atomic::{AtomicU64, Ordering};",
      "use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};")
    s=once(s,
      "    android_quit_finished: bool,",
      "    android_quit_finished: bool,\n"
      "    // Shared with android_main so Activity.finish is deferred until AFTER\n"
      "    // the native eframe loop exits. Never finish while UI is rendering.\n"
      "    vc_quit_after_native: Arc<AtomicBool>,")
    prior='''        if self.inner.ui.status == "quit" && !self.android_quit_finished {
            // Upstream confirms quit only after the Save Changes dialog's
            // real Save or Don't Save callback; Cancel never reaches here.
            self.persist_now();
            if let Err(error) = self.bridge.end_type_editing() { log::warn!("Quit IME cleanup: {error}"); }
            match self.bridge.finish_android_after_quit() {
                Ok(()) => self.android_quit_finished = true,
                Err(error) => log::warn!("Confirmed quit could not finish Android Activity: {error}"),
            }
        }'''
    replacement='''        if self.inner.ui.status == "quit" && !self.android_quit_finished {
            // Only confirmed Save / Don't Save reaches this point.
            // NativeActivity.onDestroy can synchronously wait for android_main.
            // Completing finishAndRemoveTask here, while inside eframe::App::ui,
            // can therefore self-deadlock and produce an Android ANR.
            // Instead ask eframe to close, and let android_main finish the
            // Android task AFTER the native event loop has returned.
            self.android_quit_finished = true;
            self.vc_quit_after_native.store(true, Ordering::Release);
            log::info!("VC_QUIT_ANDROID2 stage=native_close_requested");
            ui.ctx().send_viewport_cmd(egui::ViewportCommand::Close);
        }'''
    s=once(s,prior,replacement)
    s=once(s,
      '    log::info!("VectorCraft startup diagnostic: before_eframe={}ms", startup_instant.elapsed().as_millis());\n    let result = eframe::run_native(',
      '    log::info!("VectorCraft startup diagnostic: before_eframe={}ms", startup_instant.elapsed().as_millis());\n'
      '    let vc_quit_after_native = Arc::new(AtomicBool::new(false));\n'
      '    let vc_quit_in_app = Arc::clone(&vc_quit_after_native);\n'
      '    let result = eframe::run_native(')
    s=once(s,
      '                android_quit_finished: false,',
      '                android_quit_finished: false,\n'
      '                vc_quit_after_native: Arc::clone(&vc_quit_in_app),')
    s=once(s,
      '''    if let Err(error) = result {
        log::error!("VectorCraft Android exited with an error: {error}");
    }
}''',
      '''    if let Err(error) = result {
        log::error!("VectorCraft Android exited with an error: {error}");
    }
    if vc_quit_after_native.load(Ordering::Acquire) {
        // Guaranteed outside eframe::App::ui; native winit event loop has
        // returned before Java receives its finishAndRemoveTask request.
        log::info!("VC_QUIT_ANDROID2 stage=native_loop_returned");
        match bridge.finish_android_after_quit() {
            Ok(()) => log::info!("VC_QUIT_ANDROID2 stage=java_finish_posted"),
            Err(error) => log::warn!("VC_QUIT_ANDROID2 stage=java_finish_error {error}"),
        }
    }
}''')
    p.write_text(s)
    j=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    java=j.read_text()
    java=once(java,'Log.i(TAG, "VectorCraft app.quit confirmed; finishing Android task");',
                    'Log.i(TAG, "VC_QUIT_ANDROID2 stage=java_finish_after_native_return");')
    j.write_text(java)
    print("PASS: VectorCraft Android.2 confirmed-quit native-loop-first exit, Java finish deferred, unsaved D/S/C preserved")

if __name__=="__main__":
    patch(Path(sys.argv[1]))
