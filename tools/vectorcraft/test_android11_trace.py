"""Source preflight for the Android.11 investigation overlays, not device proof."""
from pathlib import Path
import os
import tempfile
import unittest
from patch_android11_typing_trace import replace

class TraceOverlayTests(unittest.TestCase):
    def test_unknown_anchor_is_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source'; p.write_text('unreviewed source')
            with self.assertRaises(ValueError): replace(p,'reviewed anchor','replacement')
            self.assertEqual(p.read_text(),'unreviewed source')

    def test_duplicate_anchor_is_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source'; p.write_text('anchor anchor')
            with self.assertRaises(ValueError): replace(p,'anchor','replacement')
            self.assertEqual(p.read_text(),'anchor anchor')

    @unittest.skipUnless(os.environ.get('VC_ANDROID11_STAGED'), 'set VC_ANDROID11_STAGED to validate generated sources')
    def test_generated_routes_and_privacy(self):
        root=Path(os.environ['VC_ANDROID11_STAGED'])
        e=root/'source/vectorcraft/crates/engine/src'
        u=root/'source/vectorcraft/crates/ui-egui/src'
        a=root/'adapters/vectorcraft'
        trace=(e/'android_typing_trace.rs').read_text()
        for key in ['RAW_TEXT','RAW_IME','TOOL_TEXT_CALLS','EDIT_GENERATED','EDIT_ACCEPTED','EDIT_REJECTED','EDIT_DEFERRED','DOCUMENT_CHANGES','TARGET_CHANGES','RESET_MATCHED','RESET_UNMATCHED']:
            self.assertIn(key,trace)
        for payload in ['CharSequence','filename','password','plain_text','text.to_string','id.0']:
            self.assertNotIn(payload,trace)
        host=(a/'src/lib.rs').read_text()
        self.assertIn('VectorCraft {runtime_version} Diagnostic Session',host)
        self.assertNotIn('VectorCraft v0.23.0-android.4 Diagnostic Session',host)
        self.assertIn('capture_started={}',host)
        self.assertIn('self.inner.raw_input_hook(ctx, raw);',host)
        self.assertIn('STALE_IME_REJECTED',(u/'shortcuts/typing.rs').read_text())
        java=(a/'java/com/artcraft/vectorcraft/VectorCraftActivity.java').read_text()
        self.assertEqual(java.count('vcTraceRejected.incrementAndGet();'),6)
        self.assertIn('stale_connection_generation',java)
        self.assertIn('reset_in_progress',java)

    @unittest.skipUnless(os.environ.get('VC_ANDROID11_STAGED'), 'set VC_ANDROID11_STAGED to validate generated sources')
    def test_cursor_backend_and_surface_retry(self):
        root=Path(os.environ['VC_ANDROID11_STAGED'])
        a=root/'adapters/vectorcraft'
        c=(root/'source/vectorcraft/crates/ui-egui/src/cursors.rs').read_text()
        self.assertIn('pub const OS_CURSORS: bool = !cfg!(any(target_os = "macos", target_os = "android", target_arch = "wasm32"));',c)
        self.assertIn('C::None => 0', (a/'src/adaptive_cursor.rs').read_text())
        host=(a/'src/lib.rs').read_text()
        self.assertIn('t.elapsed() >= std::time::Duration::from_millis(500)',host)
        java=(a/'java/com/artcraft/vectorcraft/VectorCraftActivity.java').read_text()
        start=java.index('    public void vcSetAdaptivePointerIcon(')
        end=java.index('    private SurfaceView findNativeSurface(',start)
        method=java[start:end]
        self.assertLess(method.index('setPointerIcon('),method.index('nativePointerIconType = pointerType;'))
        self.assertIn('nativeSurface == vcPointerAppliedSurface',method)
        self.assertIn('vcInstallPenHoverListener();',method)

if __name__=='__main__': unittest.main()
