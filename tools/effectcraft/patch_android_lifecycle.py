"""EffectCraft-only disposable winit checkout: allow sequential Android Activities.

The global desktop one-loop-ever rule must not apply to Android Activity recreation.
Never patch the committed shared vendor tree; the workflow stages a private copy.
"""
from pathlib import Path
import sys


def once(source, before, after):
    if source.count(before) != 1:
        raise RuntimeError('STOP: pinned winit lifecycle hook drift: ' + before[:70])
    return source.replace(before, after, 1)


def apply(root):
    root = Path(root)
    event_path = root / 'src/event_loop.rs'
    android_path = root / 'src/platform_impl/android/mod.rs'
    source = event_path.read_text()
    source = once(source, 'static EVENT_LOOP_CREATED: AtomicBool = AtomicBool::new(false);',
        '''#[cfg(not(android_platform))]
static EVENT_LOOP_CREATED: AtomicBool = AtomicBool::new(false);
#[cfg(android_platform)]
#[path = "android_event_loop_lifetime.rs"]
mod android_event_loop_lifetime;''')
    source = once(source, '        if EVENT_LOOP_CREATED.swap(true, Ordering::Relaxed) {',
        '''        #[cfg(android_platform)]
        let android_lifetime = android_event_loop_lifetime::AndroidEventLoopLifetime::acquire()
            .ok_or(EventLoopError::RecreationAttempt)?;
        #[cfg(not(android_platform))]
        if EVENT_LOOP_CREATED.swap(true, Ordering::Relaxed) {''')
    source = once(source, '    pub(crate) event_loop: platform_impl::EventLoop<T>,\n    pub(crate) _marker: PhantomData<*mut ()>, // Not Send nor Sync',
        '''    pub(crate) event_loop: platform_impl::EventLoop<T>,
    pub(crate) _marker: PhantomData<*mut ()>, // Not Send nor Sync
    // Last field: release only AFTER the platform event loop and Android handles drop.
    #[cfg(android_platform)]
    _android_lifetime: android_event_loop_lifetime::AndroidEventLoopLifetime,''')
    source = once(source, '            event_loop: platform_impl::EventLoop::new(&mut self.platform_specific)?,',
        '''            event_loop: platform_impl::EventLoop::new(&mut self.platform_specific)?,
            #[cfg(android_platform)]
            _android_lifetime: android_lifetime,''')
    android = once(android_path.read_text(), '''                MainEvent::Destroy => {
                    // XXX: maybe exit mainloop to drop things before being
                    // killed by the OS?
                    warn!("TODO: forward onDestroy notification to application");
                },''', '''                MainEvent::Destroy => {
                    // Destroy is final for this Activity: let eframe run on_exit and
                    // return from android_main instead of leaving the Java teardown waiting.
                    tracing::info!("EffectCraft Activity destroyed; exiting native event loop");
                    self.window_target.p.exit();
                },''')
    # Validate everything before writing anything.
    guard = Path(__file__).with_name('android_event_loop_lifetime.rs').read_text()
    event_path.write_text(source)
    android_path.write_text(android)
    (root / 'src/android_event_loop_lifetime.rs').write_text(guard)


if __name__ == '__main__':
    apply(Path(sys.argv[1]))
