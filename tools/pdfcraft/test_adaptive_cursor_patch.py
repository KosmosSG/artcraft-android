"""PDFCraft-only NativeActivity Adaptive Cursor source regression tests."""
from pathlib import Path
import tempfile,unittest
from adaptive_cursor_patch import apply
ROOT=Path(__file__).resolve().parents[2]
class CursorPortTests(unittest.TestCase):
    def test_staged_vendor_only(self):
        base=(ROOT/"vendor/egui-winit/src/lib.rs").read_text()
        template=ROOT/"templates/android/pdfcraft_adaptive_cursor.rs"
        with tempfile.TemporaryDirectory() as d:
            v=Path(d);(v/"src").mkdir()
            (v/"src/lib.rs").write_text(base)
            apply(v,template);saved=(v/"src/lib.rs").read_text()
            self.assertIn("PDFCRAFT_ANDROID_ADAPTIVE_CURSOR",saved)
            self.assertIn("WindowEvent::ImeResetCompleted { .. } => EventResponse",saved)
            self.assertIn("pdfcraft_adaptive_cursor::apply(cursor_icon)",saved)
            apply(v,template)
            self.assertEqual(saved,(v/"src/lib.rs").read_text())
        self.assertNotIn("PDFCRAFT_ANDROID_ADAPTIVE_CURSOR",base)
    def test_native_pointer_mapping_and_ui_thread(self):
        code=(ROOT/"templates/android/pdfcraft_adaptive_cursor.rs").read_text()
        self.assertIn("#[expect(unsafe_code)]",code)
        java=(ROOT/"templates/android/pdfcraft_mobile_java.txt").read_text()
        for v in ('C::Text | C::VerticalText => 1008','C::PointingHand => 1002',
                  'C::Crosshair => 1007','C::ResizeHorizontal',
                  'C::Progress | C::Wait | C::None => return None','jni_str!("pdfApplyAdaptiveCursor")'):
            self.assertIn(v,code)
        for v in ('PDFCRAFT_ANDROID_ADAPTIVE_CURSOR_JAVA',
                  'PDFCRAFT_ANDROID_CURSOR_FEEDBACK',
                  'pdfCursorRequests.incrementAndGet()',
                  'pdfCursorApplied.incrementAndGet()',
                  'public void pdfApplyAdaptiveCursor(int type)',
                  'runOnUiThread(', 'findPdfAdaptiveSurface', 'setPointerIcon',
                  'android.view.SurfaceView'):
            self.assertIn(v,java)
if __name__=="__main__":unittest.main()
