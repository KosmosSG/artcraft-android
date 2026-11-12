from pathlib import Path
import re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
class WheelIntegration(unittest.TestCase):
 def test_exact_pc_source_and_ten_percent_reduction(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'mark.rgba'
   subprocess.run(['python3',str(ROOT/'tools/pdfcraft/wheel_brand.py'),str(out)],check=True)
   self.assertEqual(out.stat().st_size,192*120*4)
  s=(ROOT/'templates/android/pdfcraft_stylus_wheel.rs').read_text()
  self.assertIn('vec2(36.0, 22.5) * scale',s)
  self.assertIn('Color32::from_rgb(251, 14, 0)',s)
 def test_hover_and_button_paths_are_passive_and_device_scoped(self):
  java=(ROOT/'templates/android/pdfcraft_stylus_java.txt').read_text()
  for part in ['TOOL_TYPE_STYLUS','TOOL_TYPE_ERASER','ACTION_HOVER_MOVE','pdfPenHover = ""','Magic-Pencil 4s','return false;','layout.length() <= 128']:
   self.assertIn(part,java)
  self.assertNotIn('ACCESSIBILITY',java)
 def test_command_allowlist_and_customizer(self):
  s=(ROOT/'templates/android/pdfcraft_stylus_wheel.rs').read_text()
  self.assertIn('75.0..=150.0',s); self.assertIn('40.0..=100.0',s)
  self.assertIn('size.is_finite() && opacity.is_finite()',s)
  self.assertIn('Reset to Default',s)
  self.assertIn('self.opacity_percent / 100.0',s)
 def test_native_hover_is_last_passive_egui_event(self):
  mobile=(ROOT/'templates/android/pdfcraft_mobile.rs').read_text()
  wheel=(ROOT/'templates/android/pdfcraft_stylus_wheel.rs').read_text()
  native=(ROOT/'tools/pdfcraft/stylus_native.rs').read_text()
  self.assertIn('android_activity::pdf_stylus_native_hover()',mobile)
  self.assertIn('ctx.pixels_per_point()',mobile)
  self.assertIn('raw.events.push(egui::Event::PointerMoved(pos))',mobile)
  self.assertIn('raw.events.push(egui::Event::PointerGone)',mobile)
  self.assertIn('ctx.data_mut(|d| d.insert_temp(hover_id, false))',mobile)
  self.assertIn('if self.pen_hover.is_none() { self.hover = Some(pos); }',wheel)
  self.assertIn('self.hover.and_then(|p| Self::hit(center, p, scale))',wheel)
  self.assertIn('action == 7 || action == 9',native)
  # Hover must never synthesize a button press or touch selection.
  passive=mobile.split('// NativeActivity receives stylus HOVER_MOVE')[1].split('pub fn take_wheel_action')[0]
  self.assertNotIn('raw.events.push(egui::Event::PointerButton',passive)
  self.assertNotIn('raw.events.push(egui::Event::Touch',passive)
 def test_staged_native_patch_idempotent(self):
  import shutil
  with tempfile.TemporaryDirectory() as d:
   dst=Path(d)/'activity';shutil.copytree(ROOT/'vendor/android-activity',dst)
   script=ROOT/'tools/pdfcraft/stylus_native_patch.py'
   subprocess.run(['python3',str(script),str(dst)],check=True)
   before=(dst/'src/native_activity/mod.rs').read_text()
   subprocess.run(['python3',str(script),str(dst)],check=True)
   self.assertEqual(before,(dst/'src/native_activity/mod.rs').read_text())
if __name__=='__main__':unittest.main()
