"""Fail-closed staging checks; Rust exercises actual lifetime code in CI."""
from pathlib import Path
import tempfile
import unittest
from patch_android_lifecycle import apply

TOOLS = Path(__file__).parent


class AndroidLifecycle(unittest.TestCase):
    def fixture(self, root):
        event = root / 'src/event_loop.rs'
        android = root / 'src/platform_impl/android/mod.rs'
        android.parent.mkdir(parents=True)
        event.write_text('''static EVENT_LOOP_CREATED: AtomicBool = AtomicBool::new(false);
    pub(crate) event_loop: platform_impl::EventLoop<T>,
    pub(crate) _marker: PhantomData<*mut ()>, // Not Send nor Sync
        if EVENT_LOOP_CREATED.swap(true, Ordering::Relaxed) {
            event_loop: platform_impl::EventLoop::new(&mut self.platform_specific)?,
''')
        android.write_text('''                MainEvent::Destroy => {
                    // XXX: maybe exit mainloop to drop things before being
                    // killed by the OS?
                    warn!("TODO: forward onDestroy notification to application");
                },''')
        return event, android

    def test_sequential_activity_support_is_android_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            event, android = self.fixture(root)
            apply(root)
            text = event.read_text()
            self.assertIn('#[cfg(not(android_platform))]\n        if EVENT_LOOP_CREATED.swap', text)
            self.assertIn('AndroidEventLoopLifetime::acquire()', text)
            self.assertIn('_android_lifetime: android_lifetime', text)
            self.assertLess(text.index('event_loop: platform_impl::EventLoop<T>'), text.index('_android_lifetime:'))
            self.assertIn('self.window_target.p.exit();', android.read_text())
            self.assertEqual((root / 'src/android_event_loop_lifetime.rs').read_text(),
                             (TOOLS / 'android_event_loop_lifetime.rs').read_text())
            with self.assertRaisesRegex(RuntimeError, 'STOP'):
                apply(root)

    def test_drift_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            event, android = self.fixture(root)
            before = event.read_text()
            android.write_text('upstream lifecycle changed')
            with self.assertRaisesRegex(RuntimeError, 'STOP'):
                apply(root)
            self.assertEqual(event.read_text(), before)
            self.assertFalse((root / 'src/android_event_loop_lifetime.rs').exists())

    def test_text_commit_precedes_quit_and_escape_is_dialog_cancel(self):
        native = (TOOLS / 'android_updater.rs').read_text()
        method = native[native.index('pub fn keyboard_shortcuts'):native.index('pub fn unsaved_dialog')]
        self.assertLess(method.index('execute("text.endEdit"'), method.index('menus::invoke'))
        java = (TOOLS / 'integrate_updater.py').read_text()
        self.assertIn('(code == android.view.KeyEvent.KEYCODE_C || code == android.view.KeyEvent.KEYCODE_ESCAPE) ? 2', java)
        patch = (TOOLS / 'patch_android_lifecycle.py').read_text()
        self.assertNotIn('process::exit', patch)
        self.assertNotIn('remove_dir', patch)

    def test_cancel_resumes_selection_with_fresh_editor_command(self):
        native = (TOOLS / 'android_updater.rs').read_text()
        self.assertIn('"layer": edit.layer.0, "select": [edit.anchor, edit.caret]', native)
        self.assertIn('else if !seen_dialog', native)
        self.assertIn('!inner.dialog_state.unsaved.quitting && inner.dialog.is_none()', native)
        self.assertIn('inner.session.execute("text.edit", params)', native)
        launcher = (TOOLS / 'integrate_updater.py').read_text()
        self.assertIn('self.updates.restore_cancelled_quit_edit(&mut self.inner, ui.ctx());', launcher)
