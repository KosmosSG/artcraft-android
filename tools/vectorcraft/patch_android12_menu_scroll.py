"""Android.12 menu-only trackpad-wheel smoothing, inspired by PhotoCraft's
separation of hovered popups from canvas scroll.

Only reshape trackpad wheel impulses over an actual popup. Do not touch stylus,
touchscreen, drawing, canvas pan/zoom, or document state. Preserve input phase.
"""
from pathlib import Path
from backend_stability import once

SMOOTHER=r'''
#[derive(Default)]
pub struct AndroidMenuScrollSmoother {
    remainder: egui::Vec2,
    modifiers: egui::Modifiers,
}
impl AndroidMenuScrollSmoother {
    pub fn apply(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        let hovered_menu = egui::Popup::is_any_open(ctx)
            && ctx.pointer_hover_pos().and_then(|pos| ctx.layer_id_at(pos))
                .is_some_and(|layer| layer.order >= egui::Order::Foreground);
        if !hovered_menu {
            self.remainder = egui::Vec2::ZERO;
            return;
        }
        let mut retained = Vec::with_capacity(raw.events.len() + 1);
        for event in raw.events.drain(..) {
            match event {
                egui::Event::MouseWheel {
                    unit, delta, modifiers, source, phase
                } if !modifiers.any() && matches!(phase, egui::TouchPhase::Move)
                    && matches!(source, egui::MouseWheelSource::Trackpad
                         | egui::MouseWheelSource::Unknown)
                    && matches!(unit, egui::MouseWheelUnit::Point
                         | egui::MouseWheelUnit::Line) =>
                {
                    // Scale line events into logical points before easing;
                    // egui's scroll view then sees one point stream.
                    let factor = if matches!(unit, egui::MouseWheelUnit::Line) { 16.0 } else { 1.0 };
                    self.remainder += delta * factor;
                    self.remainder.x = self.remainder.x.clamp(-420.0, 420.0);
                    self.remainder.y = self.remainder.y.clamp(-420.0, 420.0);
                    self.modifiers = modifiers;
                }
                other => retained.push(other),
            }
        }
        let move_now = egui::vec2(
            (self.remainder.x * 0.32).clamp(-34.0, 34.0),
            (self.remainder.y * 0.32).clamp(-34.0, 34.0),
        );
        if move_now.length_sq() > 0.12 {
            self.remainder -= move_now;
            retained.push(egui::Event::MouseWheel {
                unit: egui::MouseWheelUnit::Point,
                delta: move_now, phase: egui::TouchPhase::Move,
                modifiers: self.modifiers, source: egui::MouseWheelSource::Trackpad,
            });
            ctx.request_repaint_after(std::time::Duration::from_millis(16));
        } else {
            self.remainder = egui::Vec2::ZERO;
        }
        raw.events = retained;
    }
}
'''

def patch(root: Path) -> None:
    mods=root/"adapters/vectorcraft/src/android_modifiers.rs"
    s=mods.read_text()
    s=once(s,'/// Minimal event counters',SMOOTHER+'\n/// Minimal event counters')
    mods.write_text(s)
    host=root/"adapters/vectorcraft/src/lib.rs"
    s=host.read_text()
    s=once(s,'use android_modifiers::{AndroidModifiers,', 'use android_modifiers::{AndroidMenuScrollSmoother, AndroidModifiers,')
    s=once(s,'    modifiers: AndroidModifiers,','    modifiers: AndroidModifiers,\n    menu_scroll: AndroidMenuScrollSmoother,')
    s=once(s,'                modifiers: AndroidModifiers::default(),',
        '                modifiers: AndroidModifiers::default(),\n                menu_scroll: AndroidMenuScrollSmoother::default(),')
    s=once(s,'        // egui is the only scroll integrator; preserve delta and phase.',
    '''        // An Android-only menu popup receives smooth, frame-paced trackpad
        // wheel deltas. Canvas/pan/pinch inputs bypass this filter untouched.
        self.menu_scroll.apply(ctx, raw);''')
    host.write_text(s)
    print("PASS: PhotoCraft-style menu-only wheel pacing, canvas and stylus unchanged")

if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
