"""VectorCraft Android.13: one smooth-scroll owner and full-speed hovered menu wheel.

VectorCraft Android.12 attenuated wheel input twice: the popup scroll area
multiplied by 0.78 while its own frame-easer sent only 32% of the delta.
Keep a stable popup scroll state and 60Hz cadence, but remove double damping.
Only wheel input while a popup is open; canvas, touch, stylus unchanged.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    widget=root/"source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
    s=widget.read_text()
    s=once(s,'.wheel_scroll_multiplier(egui::vec2(1.0, 0.78))',
        '.wheel_scroll_multiplier(egui::vec2(1.0, 1.0))')
    widget.write_text(s)
    mods=root/"adapters/vectorcraft/src/android_modifiers.rs"
    s=mods.read_text()
    s=once(s,'''        let hovered_menu = egui::Popup::is_any_open(ctx)
            && ctx.pointer_hover_pos().and_then(|pos| ctx.layer_id_at(pos))
                .is_some_and(|layer| layer.order >= egui::Order::Foreground);''',
        '''        // Popup navigation owns wheel input while open. The last frame's
        // hover layer can disappear as egui tears down/rebuilds a submenu;
        // requiring it discards gestures and causes visible scroll stutter.
        let hovered_menu = egui::Popup::is_any_open(ctx);''')
    s=once(s,'(self.remainder.x * 0.32).clamp(-34.0, 34.0)',
             '(self.remainder.x * 0.48).clamp(-50.0, 50.0)')
    s=once(s,'(self.remainder.y * 0.32).clamp(-34.0, 34.0)',
             '(self.remainder.y * 0.48).clamp(-50.0, 50.0)')
    s=once(s,'ctx.request_repaint_after(std::time::Duration::from_millis(16));',
        'ctx.request_repaint_after(std::time::Duration::from_millis(12));')
    mods.write_text(s)
    print("PASS: single pop-up wheel multiplier, steady menu frame pacing, canvas untouched")

if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
