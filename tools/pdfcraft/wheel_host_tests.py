"""Compile the actual wheel against egui; stub only upstream theme/icon rendering."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'src').mkdir()
 (p/'Cargo.toml').write_text('[package]\nname="pdf-wheel-tests"\nversion="0.1.0"\nedition="2024"\n[dependencies]\negui="=0.37.0"\nlog="0.4"\n[features]\ndefault=["native-activity"]\nnative-activity=[]\n')
 (p/'src/native.rs').write_text((root/'tools/pdfcraft/stylus_native.rs').read_text())
 (p/'src/wheel.rs').write_text((root/'templates/android/pdfcraft_stylus_wheel.rs').read_text())
 subprocess.run(['python3',str(root/'tools/pdfcraft/wheel_brand.py'),str(p/'src/stylus_wheel_pc.rgba')],check=True)
 (p/'src/lib.rs').write_text('''extern crate self as pdfcraft_ui_egui;
 pub mod theme {
  pub struct Tokens {pub panel:egui::Color32,pub border:egui::Color32,pub field:egui::Color32,pub text:egui::Color32,pub text_muted:egui::Color32}
  impl Tokens {pub fn get(_: &egui::Context)->Self {Self {panel:egui::Color32::GRAY,border:egui::Color32::GRAY,field:egui::Color32::GRAY,text:egui::Color32::WHITE,text_muted:egui::Color32::GRAY}}}
 }
 pub mod icons {pub fn paint(_: &egui::Ui,_:egui::Rect,_:&str,_:f32,_:egui::Color32){}}
 mod wheel;
 mod native;
''')
 subprocess.run(['cargo','test','--manifest-path',str(p/'Cargo.toml')],check=True)
