"""Android-only menu scrolling improvements for official VectorCraft v0.21.0.

Keep wgpu/Vulkan renderer, keyboard shortcuts, and mouse/touch inputs unchanged.
On Android only, use a stable per-popup scroll ID, reduce chunky trackpad
wheel increments, and request a 60Hz follow-up repaint while egui smooths input.
Do not pretend this creates native compositor/GPU acceleration.
"""
from pathlib import Path
import argparse


ORIGINAL = '''        egui::ScrollArea::vertical().scroll_source(egui::containers::scroll_area::ScrollSource::ALL).max_height(room).min_scrolled_height(room).show(ui, add_contents).inner'''
REPLACEMENT = '''        let area = egui::ScrollArea::vertical().scroll_source(egui::containers::scroll_area::ScrollSource::ALL).max_height(room).min_scrolled_height(room);
        #[cfg(target_os = "android")]
        let area = area
            // IDs are scoped by each popup UI so Effect/Window/Submenu states
            // never collide, and the offset persists across repaints.
            .id_salt("vectorcraft-android-smooth-menu")
            // The Android physical trackpad often emits chunky wheel batches.
            // Keep speed useful but reduce visible jumps in long menus.
            .wheel_scroll_multiplier(egui::vec2(1.0, 0.78));
        #[cfg(target_os = "android")]
        if ui.input(|input| input.is_scrolling()) {
            // The Vulkan renderer already draws menu quads on the GPU. The
            // missing part is a steady repaint cadence while egui's own
            // wheel smoothing / inertia is settling.
            ui.ctx().request_repaint_after(std::time::Duration::from_millis(16));
        }
        area.show(ui, add_contents).inner'''


# The official v0.24.1 menu_scroll now positions popups above/below their
# anchor, retains popup width and lays out the scroll body separately.
# Add the tablet-specific tuning in place; never revert that upstream layout.
V0241_ORIGINAL = '''        let area = egui::ScrollArea::vertical().scroll_source(egui::containers::scroll_area::ScrollSource::ALL).max_height(room).min_scrolled_height(room);'''
V0241_REPLACEMENT = '''        let area = egui::ScrollArea::vertical().scroll_source(egui::containers::scroll_area::ScrollSource::ALL).max_height(room).min_scrolled_height(room);
        #[cfg(target_os = "android")]
        let area = area
            .id_salt("vectorcraft-android-smooth-menu")
            .wheel_scroll_multiplier(egui::vec2(1.0, 0.78));
        #[cfg(target_os = "android")]
        if ui.input(|input| input.is_scrolling()) {
            ui.ctx().request_repaint_after(std::time::Duration::from_millis(16));
        }'''


def patch_source(source: str) -> str:
    if 'vectorcraft-android-smooth-menu' in source:
        raise ValueError("Android menu scroll already patched; refusing duplicate")
    legacy, current = source.count(ORIGINAL), source.count(V0241_ORIGINAL)
    if legacy == 1 and current == 0:
        return source.replace(ORIGINAL, REPLACEMENT, 1)
    if current == 1 and legacy == 0:
        return source.replace(V0241_ORIGINAL, V0241_REPLACEMENT, 1)
    raise ValueError("Unreviewed upstream VectorCraft menu_scroll; refusing change")


def patch(builder: Path) -> None:
    target=builder/"source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
    source=target.read_text()
    target.write_text(patch_source(source))
    print("PASS: Android menu trackpad wheel clamped, per-popup stable scroll ID, 60Hz repaint while scrolling")


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("builder",type=Path)
    patch(ap.parse_args().builder)
