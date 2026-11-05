"""PhotoCraft candidate: physical typing, document close, and same-process activity relaunch."""
import argparse
from pathlib import Path
from photocraft_v0201_keyboard_diagnostics_overlay import patch

p = argparse.ArgumentParser()
for name in ('adapter', 'upstream', 'vendor'):
    p.add_argument('--'+name, type=Path, required=True)
a = p.parse_args()
host = a.adapter/'src/lib.rs'
act = a.adapter/'java/com/artcraft/photocraft/PhotoCraftActivity.java'
loop = a.vendor/'winit/src/event_loop.rs'
patch(a.adapter/'Cargo.toml','version = "0.20.1-android.5"','version = "0.20.1-android.6"')
patch(act, '    public void imeShow() {', '''    private boolean pcHardwareKeyboard() {
        android.content.res.Configuration config = getResources().getConfiguration();
        if (config.keyboard == android.content.res.Configuration.KEYBOARD_QWERTY
                && config.hardKeyboardHidden != android.content.res.Configuration.HARDKEYBOARDHIDDEN_YES) {
            return true;
        }
        for (int id : android.view.InputDevice.getDeviceIds()) {
            android.view.InputDevice device = android.view.InputDevice.getDevice(id);
            if (device != null && !device.isVirtual()
                    && android.os.Build.VERSION.SDK_INT >= 29 && device.isExternal()
                    && device.getKeyboardType() == android.view.InputDevice.KEYBOARD_TYPE_ALPHABETIC) {
                return true;
            }
        }
        return false;
    }

    private volatile boolean pcKeyboardRequested;
    public void imeShow() {
        pcKeyboardRequested = true;
        if (!pcHardwareKeyboard()) pcShowSoftwareKeyboard();
    }

    @Override public void onConfigurationChanged(android.content.res.Configuration config) {
        super.onConfigurationChanged(config);
        if (pcKeyboardRequested) {
            if (pcHardwareKeyboard()) pcReleaseIme();
            else pcShowSoftwareKeyboard();
        }
    }

    public void pcShowSoftwareKeyboard() {
        pcKeyboardRequested = true;''')
patch(act, '    public void imeHide() {','''    public void imeHide() {
        pcKeyboardRequested = false;
        pcReleaseIme();
    }

    private void pcReleaseIme() {''')
patch(host, 'jni_str!("imeShow"),', 'jni_str!("pcShowSoftwareKeyboard"),')
patch(a.upstream/'crates/ui-egui/src/dialogs/discard_ui.rs',
      '    let (target, docs) = discarded(app, id, params);',
      '''    // End the canvas Type session while its document is still alive. The
    // normal prompt then computes dirty state and owns each subsequent key.
    let active_target = params.get("document").and_then(Value::as_u64)
        .is_none_or(|i| Some(i as usize) == app.session.active_index());
    if app.discard.is_none() && app.ui.text_edit.is_some()
        && (id == EXIT || (id == "file.close" && active_target))
    {
        crate::type_tool::commit(app);
    }
    let (target, docs) = discarded(app, id, params);''')
# Hold the guard inside the platform loop itself, so it also follows any move
# out of the public wrapper. Field destruction follows declaration order.
android_loop = a.vendor/'winit/src/platform_impl/android/mod.rs'
patch(loop,'static EVENT_LOOP_CREATED: AtomicBool = AtomicBool::new(false);','''static EVENT_LOOP_CREATED: AtomicBool = AtomicBool::new(false);

#[cfg(android_platform)]
pub(crate) struct AndroidLoopLease;
#[cfg(android_platform)]
impl Drop for AndroidLoopLease {
    fn drop(&mut self) { EVENT_LOOP_CREATED.store(false, Ordering::Release); }
}''')
patch(loop,'EVENT_LOOP_CREATED.swap(true, Ordering::Relaxed)', 'EVENT_LOOP_CREATED.swap(true, Ordering::AcqRel)')
patch(android_loop,'    combining_accent: Option<char>,','''    combining_accent: Option<char>,
    _creation_lease: crate::event_loop::AndroidLoopLease,''')
patch(android_loop,'        let (user_events_sender, user_events_receiver) = mpsc::channel();','''        let lease = crate::event_loop::AndroidLoopLease;
        let (user_events_sender, user_events_receiver) = mpsc::channel();''')
patch(android_loop,'            combining_accent: None,','''            combining_accent: None,
            _creation_lease: lease,''')
