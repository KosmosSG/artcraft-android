"""Patch the FINAL vendored winit, after builder copies, for VectorCraft only."""
from pathlib import Path
import sys


def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError(f'Unreviewed anchor ({s.count(old)}): {old[:100]}')
    return s.replace(old, new, 1)


def patch(root):
    p=root/'src/platform_impl/android/mod.rs';s=p.read_text()
    s=once(s,'''                    // XXX: maybe exit mainloop to drop things before being
                    // killed by the OS?
                    warn!("TODO: forward onDestroy notification to application");''','''                    // NativeActivity.onDestroy waits for android_main to return.
                    self.running = false;
                    self.window_target.p.exit();''')
    s=once(s,"pub struct EventLoopProxy<T: 'static> {",'''impl<T: 'static> Drop for EventLoop<T> {
    fn drop(&mut self) {
        // Only permit recreation after the old Android loop is dropped.
        crate::event_loop::EventLoopBuilder::<()>::allow_event_loop_recreation();
    }
}

pub struct EventLoopProxy<T: 'static> {''')
    s=once(s,'                        let key_char = keycodes::character_map_and_combine_key(','''                        // Android snapshots remain valid after a missing modifier transition.
                        let meta = key.meta_state();
                        let mut mods = crate::keyboard::ModifiersState::empty();
                        mods.set(crate::keyboard::ModifiersState::SHIFT, meta.shift_on());
                        mods.set(crate::keyboard::ModifiersState::CONTROL, meta.ctrl_on());
                        mods.set(crate::keyboard::ModifiersState::ALT, meta.alt_on());
                        mods.set(crate::keyboard::ModifiersState::SUPER, meta.meta_on());
                        crate::platform::android::vc_note_key(u32::from(keycode),
                            state == event::ElementState::Pressed, meta.0);
                        callback(event::Event::WindowEvent {
                            window_id: window::WindowId(WindowId),
                            event: event::WindowEvent::ModifiersChanged(mods.into()),
                        }, self.window_target());
                        let key_char = keycodes::character_map_and_combine_key(''')
    p.write_text(s)
    p=root/'src/event_loop.rs';p.write_text(once(p.read_text(),
        '#[cfg(web_platform)]\n    pub(crate) fn allow_event_loop_recreation()',
        '#[cfg(any(web_platform, android_platform))]\n    pub(crate) fn allow_event_loop_recreation()'))
    p=root/'src/platform/android.rs';s=p.read_text()
    if 'VC_KEY_ENABLED' in s: raise ValueError('diagnostics already applied')
    p.write_text(s+'''
// Opt-in latest snapshot only. Disabled and cleared during text/composition.
static VC_KEY_ENABLED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
static VC_KEY_PACKET: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static VC_KEY_COUNT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
pub fn vc_keyboard_diagnostics(enabled: bool) -> (u64, u64) {
    use std::sync::atomic::Ordering::Relaxed;
    VC_KEY_ENABLED.store(enabled, Relaxed);
    if !enabled { VC_KEY_PACKET.store(0, Relaxed); }
    (VC_KEY_COUNT.load(Relaxed), VC_KEY_PACKET.load(Relaxed))
}
pub(crate) fn vc_note_key(code: u32, down: bool, meta: u32) {
    use std::sync::atomic::Ordering::Relaxed;
    if VC_KEY_ENABLED.load(Relaxed) {
        VC_KEY_COUNT.fetch_add(1, Relaxed);
        VC_KEY_PACKET.store((u64::from(meta)<<32) | (u64::from(down)<<31) | u64::from(code), Relaxed);
    }
}
''')


if __name__=='__main__': patch(Path(sys.argv[1]))
