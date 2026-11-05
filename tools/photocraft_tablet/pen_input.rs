//! Feed the document engine every pen sample, including Android's batched positions.
//! Finger gestures have already been processed when pen pointer events are inserted.
use android_activity::pc_pen::{self, Phase};
use egui::{Event, PointerButton, RawInput};
use photocraft_ui_egui::{PhotocraftApp, stylus::PenSample};

#[derive(Default)]
pub struct PenInput { down: bool, clear_after_lift: bool }
impl PenInput {
    pub fn apply(&mut self, app: &mut PhotocraftApp, ctx: &egui::Context, raw: &mut RawInput, modifiers: egui::Modifiers) {
        if std::mem::take(&mut self.clear_after_lift) { app.stylus.feed.set(None); }
        let ppp=ctx.pixels_per_point();
        for sample in pc_pen::drain() {
            let pos=egui::pos2(sample.x/ppp,sample.y/ppp);
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
