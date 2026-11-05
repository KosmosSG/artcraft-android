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
    cursor_texture: Option<(egui::CustomCursorImage, egui::TextureHandle)>,
}
impl PenInput {
    pub fn paint_hover(&mut self, ctx: &egui::Context) {
        let Some(pos) = ctx.pointer_hover_pos() else { return };
        let (icon, image) = ctx.output(|o| (o.cursor_icon, o.cursor_image.clone()));
        let painter = ctx.layer_painter(egui::LayerId::new(
            egui::Order::Tooltip, egui::Id::new("photocraft_adaptive_pointer"),
        ));
        // PhotoCraft supplies a custom bitmap for brush outlines, selection crosshairs
        // and pen tools. The Android bridge handles named icons only.
        if icon == egui::CursorIcon::None && let Some(image) = image {
            let [w, h] = image.size;
            let cached = self.cursor_texture.as_ref().is_some_and(|(old, _)| {
                old.size == image.size && std::sync::Arc::ptr_eq(&old.rgba, &image.rgba)
            });
            if !cached {
                let rgba = egui::ColorImage::from_rgba_unmultiplied([w as usize, h as usize], &image.rgba);
                let texture = ctx.load_texture("photocraft tool cursor", rgba, egui::TextureOptions::NEAREST);
                self.cursor_texture = Some((image.clone(), texture));
            }
            if let Some((_, texture)) = &self.cursor_texture {
                let scale = ctx.pixels_per_point();
                let origin = pos - egui::vec2(image.hotspot[0] as f32, image.hotspot[1] as f32) / scale;
                let rect = egui::Rect::from_min_size(origin, egui::vec2(w as f32, h as f32) / scale);
                painter.image(texture.id(), rect, egui::Rect::from_min_max(egui::Pos2::ZERO, egui::pos2(1.0,1.0)), egui::Color32::WHITE);
            }
            return;
        }
        if self.hover != Some(pos) { return; }
        for (width, color) in [(3.0, egui::Color32::BLACK), (1.3, egui::Color32::WHITE)] {
            let stroke = egui::Stroke::new(width, color);
            let line = |x1,y1,x2,y2| painter.line_segment([pos + egui::vec2(x1,y1), pos + egui::vec2(x2,y2)], stroke);
            match icon {
                egui::CursorIcon::Text => {
                    line(0.0,-7.0,0.0,7.0); line(-3.0,-7.0,3.0,-7.0); line(-3.0,7.0,3.0,7.0);
                }
                egui::CursorIcon::ZoomIn | egui::CursorIcon::ZoomOut => {
                    painter.circle_stroke(pos,5.5,stroke); line(4.0,4.0,9.0,9.0);
                    line(-2.5,0.0,2.5,0.0);
                    if icon == egui::CursorIcon::ZoomIn { line(0.0,-2.5,0.0,2.5); }
                }
                _ => { painter.circle_stroke(pos,6.0,stroke); }
            }
        }
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
