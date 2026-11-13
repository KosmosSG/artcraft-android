//! DeckCraft Android-only PhotoCraft-style stylus wheel (test candidate).
//! Source/command integration is scoped to the Android build. No document actions
//! are fired while previewing; pointer events over the live wheel are consumed
//! before the editor's egui RawInput hook.
use egui::{Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, pos2, vec2};
use crate::SlideApp;

const SIZE: f32 = 304.0;
const R: f32 = 128.0;
const HUB: f32 = 46.0;
const PINK: Color32 = Color32::from_rgb(239, 69, 105);
const BURGUNDY: Color32 = Color32::from_rgb(61, 5, 28);
const DEFAULT: [usize; 8] = [0, 1, 2, 3, 4, 5, 6, 7];
const LABELS: [&str; 10] = [
    "Select", "Text", "Pen", "Eraser", "Shapes", "Undo", "Redo", "Hand",
    "Highlighter", "New Slide",
];
const ICONS: [&str; 10] = ["↖", "T", "✎", "◇", "□", "↶", "↷", "✋", "▱", "+"];
const STATE: &str = "deckcraft.stylus.wheel.v1";

#[derive(Clone)]
struct Wheel {
    enabled: bool, settings: bool, open: bool,
    slots: [usize; 8], size: f32, opacity: f32,
    center: Option<Pos2>, hover: Option<Pos2>,
    hover_isolated: bool, pending: Option<usize>,
    // Tracks whether the Java side generated a side-button signal.
    signal_seen: u8,
}
impl Wheel {
    fn new() -> Self {
        let mut w = Self {
            enabled: false, settings: false, open: false,
            slots: DEFAULT, size: 100.0, opacity: 85.0,
            center: None, hover: None, hover_isolated: false,
            pending: None, signal_seen: 0,
        };
        if let Some(text) = settings_path().and_then(|p| std::fs::read_to_string(p).ok()) {
            let bits: Vec<_> = text.trim().split('|').collect();
            if bits.len() == 5 && bits[0] == "v1" {
                w.enabled = bits[1] == "1";
                if let Ok(n) = bits[2].parse::<f32>() {
                    if n.is_finite() { w.size = n.clamp(75.0, 125.0); }
                }
                if let Ok(n) = bits[3].parse::<f32>() {
                    if n.is_finite() { w.opacity = n.clamp(60.0, 100.0); }
                }
                let parsed: Vec<_> = bits[4].split(',').filter_map(|v| v.parse::<usize>().ok()).collect();
                if parsed.len() == 8 && parsed.iter().all(|n| *n < LABELS.len())
                    && parsed.iter().enumerate().all(|(i,n)| !parsed[..i].contains(n)) {
                    w.slots.copy_from_slice(&parsed);
                }
            }
        }
        w
    }
    fn scale(&self) -> f32 { self.size / 100.0 }
    fn save(&self) {
        if let Some(path) = settings_path() {
            let s = format!("v1|{}|{:.0}|{:.0}|{}", u8::from(self.enabled),
                self.size, self.opacity, self.slots.iter()
                    .map(usize::to_string).collect::<Vec<_>>().join(","));
            if let Err(e) = std::fs::write(path,s) {
                log::warn!("DeckCraft wheel preferences could not be saved: {e}");
            }
        }
    }
}
fn settings_path() -> Option<std::path::PathBuf> {
    std::env::var_os("XDG_CONFIG_HOME").map(std::path::PathBuf::from)
        .map(|dir| dir.join("deckcraft-stylus-wheel.v1"))
}
fn get(ctx: &Context) -> Wheel {
    let id = Id::new(STATE);
    ctx.data_mut(|d| {
        let existing = d.get_temp::<Wheel>(id);
        if let Some(s) = existing { s } else {
            let s = Wheel::new();
            d.insert_temp(id, s.clone());
            s
        }
    })
}
fn set(ctx: &Context, wheel: Wheel) {
    ctx.data_mut(|d| d.insert_temp(Id::new(STATE), wheel));
}
pub(crate) fn enabled(ctx: &Context) -> bool { get(ctx).enabled }
pub(crate) fn toggle(ctx: &Context) {
    let mut w = get(ctx);
    w.enabled = !w.enabled;
    w.open = false;
    w.pending = None;
    w.hover_isolated = false;
    w.save();
    set(ctx, w);
    ctx.request_repaint();
}
pub(crate) fn open_settings(ctx: &Context) {
    let mut w = get(ctx);
    w.settings = true;
    w.open = false;
    set(ctx, w);
    ctx.request_repaint();
}
pub(crate) fn capture(ctx: &Context, raw: &mut RawInput) {
    let mut w = get(ctx);
    if !w.enabled || w.settings {
        w.open = false;
        w.hover_isolated = false;
        set(ctx,w);
        return;
    }
    // The Android GameActivity side button is accepted only from the physical
    // Magic-Pencil device. Avoid broad key capture that breaks D/C/S or typing.
    let signal = ctx.data_mut(|d| d.remove_temp::<u8>(Id::new("deckcraft.wheel.button")));
    match signal {
        Some(2) => { w.open=false; w.pending=Some(3); },
        Some(1) => {
            if w.open { w.open = false; }
            else {
                let screen=ctx.content_rect();
                let pointer=w.hover.or_else(||ctx.input(|i| i.pointer.hover_pos()))
                    .unwrap_or(screen.center());
                let half=(SIZE*w.scale()/2.0)+8.0;
                let center=pos2(
                    pointer.x.clamp(screen.left()+half, (screen.right()-half).max(screen.left()+half)),
                    pointer.y.clamp(screen.top()+half, (screen.bottom()-half).max(screen.top()+half)),
                );
                w.center=Some(center);
                w.open=true;
                w.hover_isolated=false;
            }
        },
        _ => (),
    }
    let mut retained=Vec::with_capacity(raw.events.len()+1);
    for event in raw.events.drain(..) {
        match event {
            egui::Event::PointerMoved(p) => {
                w.hover=Some(p);
                let inside=w.open && w.center.is_some_and(|c| (p-c).length() < (R+12.0)*w.scale());
                if inside {
                    if !w.hover_isolated {
                        retained.push(egui::Event::PointerGone);
                        w.hover_isolated=true;
                    }
                } else {
                    w.hover_isolated=false;
                    retained.push(egui::Event::PointerMoved(p));
                }
            }
            egui::Event::PointerGone => {
                w.hover_isolated=false;
                retained.push(egui::Event::PointerGone);
            }
            egui::Event::PointerButton {pos, pressed: true, ..} if w.open => {
                if let Some(center)=w.center {
                    let delta=pos-center;
                    let distance=delta.length();
                    if distance > HUB*w.scale() && distance < (R+12.0)*w.scale() {
                        let ix=(((delta.y.atan2(delta.x).to_degrees()+112.5).rem_euclid(360.0)/45.0).floor() as usize).min(7);
                        w.pending=Some(w.slots[ix]);
                    }
                }
                w.open=false;
                w.hover_isolated=false;
                // Do not click, select, or highlight slide shapes underneath.
                retained.push(egui::Event::PointerGone);
            }
            egui::Event::PointerButton {..} if w.open => {}
            egui::Event::Touch {pos, ..} if w.open && w.center.is_some_and(|c| (pos-c).length() <= (R+12.0)*w.scale()) => {}
            egui::Event::Key {key: egui::Key::Escape, pressed: true, ..} if w.open => {
                w.open=false;
                w.hover_isolated=false;
            }
            other => retained.push(other),
        }
    }
    raw.events=retained;
    if w.open {
        // Short idle repaint cadence only while the wheel is actually visible.
        ctx.request_repaint_after(std::time::Duration::from_millis(70));
    }
    set(ctx,w);
}
pub(crate) fn overlay(app: &mut SlideApp, ctx: &Context) {
    let mut w=get(ctx);
    if w.settings {
        let mut show=true;
        let mut changed=false;
        let win=egui::Window::new("Stylus Wheel — Default")
            .id(Id::new("deckcraft-wheel-settings"))
            .default_width(330.0)
            .open(&mut show)
            .resizable(false)
            .collapsible(false)
            .show(ctx, |ui| {
                ui.label("8 segments · PhotoCraft-style wheel");
                ui.label("Choose a shortcut in each position. Existing selections swap.");
                ui.separator();
                for slot in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", slot+1));
                        let mut selected=w.slots[slot];
                        egui::ComboBox::from_id_salt(("deck-wheel-slot",slot))
                            .selected_text(LABELS[selected])
                            .width(190.0)
                            .show_ui(ui, |ui| {
                                for (i,label) in LABELS.iter().enumerate() {
                                    ui.selectable_value(&mut selected,i,*label);
                                }
                            });
                        if selected!=w.slots[slot] {
                            if let Some(old)=w.slots.iter().position(|i| *i==selected) {
                                w.slots[old]=w.slots[slot];
                            }
                            w.slots[slot]=selected;
                            changed=true;
                        }
                    });
                }
                ui.separator();
                changed|=ui.add(egui::Slider::new(&mut w.size,75.0..=125.0)
                    .text("Wheel size").suffix("%")).changed();
                changed|=ui.add(egui::Slider::new(&mut w.opacity,60.0..=100.0)
                    .text("Opacity").suffix("%")).changed();
                if ui.button("Restore Default").clicked() {
                    w.slots=DEFAULT;
                    w.size=100.0;
                    w.opacity=85.0;
                    changed=true;
                }
                ui.label("Preview is drawn at actual wheel size and opacity.");
            });
        w.settings=show;
        if changed {w.save();ctx.request_repaint();}
        if let Some(response)=win {
            let dialog=response.response.rect;
            let screen=ctx.content_rect();
            let size=SIZE*w.scale();
            let left=dialog.left()-screen.left();
            let right=screen.right()-dialog.right();
            let x=if right>=size+24.0 {
                (dialog.right()+screen.right())*0.5
            } else if left>=size+24.0 {
                (screen.left()+dialog.left())*0.5
            } else { screen.center().x };
            let p=pos2(x.clamp(screen.left()+size*0.5,(screen.right()-size*0.5).max(screen.left()+size*0.5)),
                dialog.center().y.clamp(screen.top()+size*0.5,(screen.bottom()-size*0.5).max(screen.top()+size*0.5)));
            paint(ctx,&w,p,None,"deckcraft-wheel-actual-size-preview");
        }
    } else if w.enabled && w.open {
        if let Some(center)=w.center {
            let hovered=w.hover.and_then(|p| {
                let delta=p-center;
                let distance=delta.length();
                if distance>=HUB*w.scale() && distance<=(R+12.0)*w.scale() {
                    Some((((delta.y.atan2(delta.x).to_degrees()+112.5).rem_euclid(360.0)/45.0).floor() as usize).min(7))
                } else { None }
            });
            paint(ctx,&w,center,hovered,"deckcraft-wheel-live");
        }
    }
    let pending=w.pending.take();
    set(ctx,w);
    if let Some(command)=pending {
        if app.session.active().is_some() {
            match command {
                0 => app.session.set_tool(deckcraft_engine::ToolKind::Select),
                1 => app.session.set_tool(deckcraft_engine::ToolKind::TextBox),
                2 | 3 | 4 | 8 => {
                    let name=match command {2=>"pen",3=>"eraser",4=>"shape",_=>"highlighter"};
                    if let Some(tool)=crate::control::tool_kind(name,Some("rect")) {
                        app.session.set_tool(tool);
                    }
                },
                5 => { let _=app.run("edit.undo",serde_json::json!({})); },
                6 => { let _=app.run("edit.redo",serde_json::json!({})); },
                7 => { app.set_status("Pan: use two fingers on the slide canvas"); },
                9 => { let _=app.run("slide.new",serde_json::json!({})); },
                _ => (),
            }
            ctx.request_repaint();
        }
    }
}
fn paint(ctx:&Context,w:&Wheel,center:Pos2,highlight:Option<usize>,id:&'static str) {
    let scale=w.scale();
    let size=SIZE*scale;
    egui::Area::new(Id::new(id)).order(Order::Foreground)
        .fixed_pos(center-vec2(size*0.5,size*0.5))
        .interactable(false)
        .show(ctx,|ui|{
            let (rect,_)=ui.allocate_exact_size(vec2(size,size),Sense::hover());
            draw(ui,rect,w,highlight);
        });
}
fn draw(ui:&Ui,rect:egui::Rect,w:&Wheel,highlight:Option<usize>) {
    let scale=w.scale();
    let c=rect.center();
    let painter=ui.painter_at(rect);
    let alpha=w.opacity/100.0;
    // Tight feathered shadow: avoid PhotoCraft's former hard halo.
    for layer in 0..12 {
        let spread=(12.0-layer as f32*0.82)*scale;
        painter.circle_filled(c+vec2(0.8,2.0)*scale,R*scale+spread,
            Color32::from_black_alpha((3.0+layer as f32*0.33) as u8));
    }
    painter.circle_filled(c,R*scale,Color32::from_gray(57).gamma_multiply(alpha));
    for slot in 0..8 {
        let degrees=-90.0+slot as f32*45.0;
        let start=(degrees-22.5).to_radians();
        let end=(degrees+22.5).to_radians();
        let mut vertices=vec![c];
        for step in 0..=18 {
            let angle=start+(end-start)*step as f32/18.0;
            vertices.push(c+vec2(angle.cos(),angle.sin())*R*scale);
        }
        let selected=highlight==Some(slot);
        let base=if selected {PINK} else if slot%2==0 {
            Color32::from_rgb(65,65,67)
        } else {Color32::from_rgb(75,75,77)};
        painter.add(Shape::convex_polygon(vertices,base.gamma_multiply(alpha),
            Stroke::new(if selected {1.3}else{0.6},
                if selected {PINK} else {Color32::from_gray(102).gamma_multiply(alpha)})));
        let theta=degrees.to_radians();
        let icon_pos=c+vec2(theta.cos(),theta.sin())*86.0*scale;
        painter.text(icon_pos-vec2(0.0,11.0)*scale,egui::Align2::CENTER_CENTER,
            ICONS[w.slots[slot]],FontId::proportional(22.0*scale),Color32::WHITE);
        painter.text(icon_pos+vec2(0.0,17.0)*scale,egui::Align2::CENTER_CENTER,
            LABELS[w.slots[slot]],FontId::proportional(11.0*scale),Color32::WHITE);
    }
    painter.circle_stroke(c,R*scale,Stroke::new(1.1,PINK.gamma_multiply(alpha)));
    painter.circle_filled(c,HUB*scale,BURGUNDY);
    painter.circle_stroke(c,HUB*scale,Stroke::new(1.3,PINK));
    // Native DeckCraft mark, not a copied PhotoCraft logo or a white tile.
    painter.text(c-vec2(0.0,8.0)*scale,egui::Align2::CENTER_CENTER,
        "Dk",FontId::proportional(34.0*scale),PINK);
    painter.text(c+vec2(0.0,23.0)*scale,egui::Align2::CENTER_CENTER,
        highlight.map(|i| LABELS[w.slots[i]]).unwrap_or("Default"),
        FontId::proportional(10.0*scale),Color32::WHITE);
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn default_slots_are_unique_and_valid() {
        assert!(DEFAULT.iter().all(|i| *i<LABELS.len()));
        assert!(DEFAULT.iter().enumerate().all(|(i,n)| !DEFAULT[..i].contains(n)));
    }
}
