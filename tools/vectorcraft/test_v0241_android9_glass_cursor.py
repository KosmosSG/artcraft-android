"""Regression guard: the native two-finger pan must not show a mouse cursor.

Static source checks alone do not prove HONOR MagicPad 4 device behavior.
This intentionally does not alter gestures, the typing/IME stack or Android.10.
"""
from pathlib import Path
import sys

MARKER = "vectorcraft-android-glass-pan-hide-cursor"

def source(root: Path) -> None:
    code=(root/"tools/vectorcraft/patch_v0241_android9_glass_pan_source.py").read_text()
    assert "vc_glass_pan_packets == 0" in code
    assert 'egui::Event::PointerMoved(_)' in code
    assert "egui::CursorIcon::None" in code
    assert "no system pointer icon" in code
    assert "canvas/input.rs" in code and "canvas.rs" in code
    assert "let gain = if vc_glass_canvas_pan { 1.15 } else { -1.15 };" in code
    assert "vc_glass_canvas_applied_note();" in code
    assert "vc_glass_pan_note();" in code
    assert "if ui.ctx().data(" in code
    assert "return false;" in code
    assert "return; // No painted tool glyph" in code
    print("PASS: source tags native glass pan, suppresses synthetic cursor/hover, preserves pan gain")

def staged(root: Path) -> None:
    adapter=(root/"adapters/vectorcraft/src/lib.rs").read_text()
    canvas=(root/"source/vectorcraft/crates/ui-egui/src/canvas.rs").read_text()
    input_=(root/"source/vectorcraft/crates/ui-egui/src/canvas/input.rs").read_text()
    assert adapter.count(f'egui::Id::new("{MARKER}")') == 1
    assert adapter.count("vc_glass_pan_packets == 0") == 1
    assert adapter.count("egui::Event::PointerMoved(_)") >= 1
    assert adapter.count("data.insert_temp(vc_glass_cursor_id, true)") == 1
    assert adapter.count("data.insert_temp(vc_glass_cursor_id, false)") == 1
    assert adapter.count("let gain = if vc_glass_canvas_pan { 1.15 } else { -1.15 };") == 1
    assert adapter.count("delta.x *= gain;") == 1
    assert adapter.count("delta.y *= gain;") == 1
    assert f'egui::Id::new("{MARKER}")' in canvas
    assert f'egui::Id::new("{MARKER}")' in input_
    assert "egui::CursorIcon::None" in canvas
    assert "return; // No painted tool glyph and no system pointer icon." in canvas
    assert "return false;" in input_
    assert '#[cfg(target_os = "android")]' in canvas
    assert '#[cfg(target_os = "android")]' in input_
    # Keep the proven canvas wheel semantics and native source tagging.
    # Native glass pan is delivered as a tagged wheel event, not early_pan or native_canvas_touch.
    assert "let gain = if vc_glass_canvas_pan { 1.15 } else { -1.15 };" in adapter
    assert "vc_glass_pan_packets > 0" in adapter
    print("PASS: staged Android.9 glass-pan cursor suppression, wheel direction and real-pointer recovery")

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("usage: test_v0241_android9_glass_cursor.py --source|--staged ROOT")
    if sys.argv[1]=="--source": source(Path(sys.argv[2]))
    elif sys.argv[1]=="--staged": staged(Path(sys.argv[2]))
    else: raise SystemExit("unknown mode")
