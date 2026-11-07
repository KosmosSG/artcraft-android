"""Android-only PDFCraft: keep trackpad wheel scrolling out of the tools sidebar.
Touch drag and the visible scrollbar still work. Fail closed on upstream drift.
"""
from pathlib import Path
import sys

HELPER = """fn pdfcraft_tools_scroll_area() -> egui::ScrollArea {
    let area = egui::ScrollArea::vertical();
    #[cfg(target_os = "android")]
    let area = area.scroll_source(egui::containers::scroll_area::ScrollSource {
        scroll_bar: true,
        drag: egui::containers::scroll_area::DragScroll::OnTouch,
        mouse_wheel: false,
    });
    area
}

"""

def apply(src: Path):
    targets = {
        "crates/ui-egui/src/panels/tools.rs": 2,
        "crates/ui-egui/src/panels/all_tools_ui.rs": 1,
    }
    for relative, expected in targets.items():
        path = src / relative
        content = path.read_text()
        marker = "fn pdfcraft_tools_scroll_area()"
        if marker in content:
            assert content.count("pdfcraft_tools_scroll_area().auto_shrink(") == expected
            continue
        old = "egui::ScrollArea::vertical().auto_shrink([false, false])"
        assert content.count(old) == expected, f"{relative}: upstream sidebar changed"
        content = content.replace(old, "pdfcraft_tools_scroll_area().auto_shrink([false, false])") + "\n" + HELPER
        path.write_text(content)

if __name__ == "__main__":
    assert len(sys.argv) == 2
    apply(Path(sys.argv[1]))
