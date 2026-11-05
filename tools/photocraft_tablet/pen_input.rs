//! Feed the document engine every pen sample, including Android's batched positions.
//! Finger gestures have already been processed when pen pointer events are inserted.
use android_activity::pc_pen::{self, Phase};
use egui::{Event, PointerButton, RawInput};
use photocraft_ui_egui::{PhotocraftApp, stylus::PenSample};

#[derive(Default)]
pub struct PenInput {
    down: bool,
    clear_after_lift: bool,
    hover: Option<egui::Pos2>,
}
impl PenInput {
    pub fn paint_hover(&self, ctx: &egui::Context) {
        let Some(pos) = self.hover else { return };
        if ctx.pointer_hover_pos() != Some(pos) { return; }
        let painter = ctx.layer_painter(egui::LayerId::new(
            egui::Order::Tooltip, egui::Id::new("photocraft_stylus_hover"),
        ));
        // A hollow, two-tone ring stays visible over both light and dark artwork.
        painter.circle_stroke(pos, 6.0, egui::Stroke::new(3.0, egui::Color32::BLACK));
        painter.circle_stroke(pos, 6.0, egui::Stroke::new(1.3, egui::Color32::WHITE));
    }

    pub fn apply(&mut self, app: &mut PhotocraftApp, ctx: &egui::Context, raw: &mut RawInput, modifiers: egui::Modifiers) {
        if std::mem::take(&mut self.clear_after_lift) { app.stylus.feed.set(None); }
        if !raw.focused || raw.events.iter().any(|event| matches!(event,
            Event::PointerGone | Event::PointerButton { .. } | Event::PointerMoved(_)
            | Event::Touch { .. } | Event::WindowFocused(false))) {
            self.hover = None;
        }
        let ppp=ctx.pixels_per_point();
        for sample in pc_pen::drain() {
            let pos=egui::pos2(sample.x/ppp,sample.y/ppp);
            self.hover = (raw.focused && !self.down && sample.phase == Phase::Hover && pos.is_finite()).then_some(pos);
            if !pos.is_finite() {continue}
            app.stylus.feed.set(Some(PenSample {pressure:sample.pressure, tilt_x:sample.tilt_x,
                tilt_y:sample.tilt_y, rotation:0.0, eraser:sample.eraser}));
            self.clear_after_lift=matches!(sample.phase,Phase::Up|Phase::Leave|Phase::Cancel);
            match sample.phase {
                Phase::Down|Phase::Up|Phase::Cancel => {
                    let pressed=sample.phase==Phase::Down;
                    if self.down!=pressed {
                        raw.events.push(Event::PointerMoved(pos));
                        raw.events.push(Event::PointerButton {pos,button:PointerButton::Primary,pressed,modifiers});
                        self.down=pressed;
                    }
                }
                Phase::Move|Phase::Hover=>raw.events.push(Event::PointerMoved(pos)),
                Phase::Leave=>if !self.down {raw.events.push(Event::PointerGone);},
            }
        }
    }
}
