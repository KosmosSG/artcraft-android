#!/usr/bin/env python3
"""Port fork v0.2.0 Adaptive Cursor to staged PDFCraft egui-winit only."""
from pathlib import Path
import sys
def apply(vendor: Path, source: Path):
    lib=vendor/"src/lib.rs"
    dst=vendor/"src/pdfcraft_adaptive_cursor.rs"
    text=lib.read_text()
    marker="PDFCRAFT_ANDROID_ADAPTIVE_CURSOR"
    if marker in text:
        if dst.read_text()!=source.read_text(): raise ValueError("Cursor port changed between patch runs")
        return
    a="mod dropped_file;\n"
    b="""        } else {
            window.set_cursor_visible(false);
        }
    }
}

fn to_egui_touch_phase"""
    for anchor in (a,b):
        if text.count(anchor)!=1:raise ValueError("PDFCraft vendor cursor API changed: "+anchor[:65])
    text=text.replace(a,a+'#[cfg(target_os = "android")]\npub mod pdfcraft_adaptive_cursor;\n',1)
    text=text.replace(b,"""        } else {
            window.set_cursor_visible(false);
        }
        // PDFCRAFT_ANDROID_ADAPTIVE_CURSOR: native hover icons, fork v0.2.0.
        #[cfg(target_os = "android")]
        crate::pdfcraft_adaptive_cursor::apply(cursor_icon);
    }
}

fn to_egui_touch_phase""",1)
    dst.write_text(source.read_text())
    lib.write_text(text)
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: adaptive_cursor_patch.py STAGED_EGUI_WINIT")
    root=Path(__file__).resolve().parents[2]
    apply(Path(sys.argv[1]),root/"templates/android/pdfcraft_adaptive_cursor.rs")
    print("PASS: PDFCraft isolated Adaptive Cursor enabled")
