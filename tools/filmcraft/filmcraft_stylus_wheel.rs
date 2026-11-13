//! FilmCraft Android stylus wheel — DeckCraft layout, approved Fc navy/lavender.
//! The pen side-button alone opens/closes the wheel; never show on application launch.
//! Real Magic-Pencil hover is read via the GameActivity bridge. While visible,
//! pointer/hover events are isolated before the underlying editor's input pass.
use android_activity::AndroidApp;
use egui::{Color32, FontId, Pos2, Sense, Stroke, pos2, vec2};
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JValue}};
use std::f32::consts::{PI, TAU};
use std::path::PathBuf;

const COMMANDS: [(&str, &str); 8] = [
    ("Razor", "tool.razor"),
    ("Select", "tool.selection"),
    ("Hand", "tool.hand"),
    ("Undo", "edit.undo"),
    ("Redo", "edit.redo"),
    ("Play/Pause", "playback.toggle"),
    ("Zoom +", "view.zoomIn"),
    ("Zoom -", "view.zoomOut"),
];
const DEFAULT_SLOTS: [usize; 8] = [3, 0, 1, 2, 6, 5, 7, 4];
const NAVY: Color32 = Color32::from_rgb(0x00, 0x04, 0x7a);
const LAVENDER: Color32 = Color32::from_rgb(0x9a, 0x9c, 0xd9);
const ACCENT: Color32 = Color32::from_rgb(0x36, 0x4c, 0xd9);
const HUB: f32 = 0.36;
const DEFAULT_RADIUS: f32 = 143.0;

pub struct Wheel {
    app: AndroidApp,
    path: Option<PathBuf>,
    enabled: bool,
    size: f32,
    opacity: f32,
    slots: [usize; 8],
    last_slot: usize,
    settings_open: bool,
    open: bool,
    center: Option<Pos2>,
    pen_hover: Option<Pos2>,
    hovered_segment: Option<usize>,
    just_isolated: bool,
    pending: Option<&'static str>,
}
impl Wheel {
    pub fn new(dir: Option<PathBuf>, app: &AndroidApp) -> Self {
        let path = dir.map(|d| d.join("filmcraft-stylus-wheel.json"));
        let mut out = Self {
            app: app.clone(), path, enabled: true, size: 1.0, opacity: 0.90,
            slots: DEFAULT_SLOTS, last_slot: 1, settings_open: false,
            open: false, center: None, pen_hover: None,
            hovered_segment: None, just_isolated: false, pending: None,
        };
        if let Some(path) = &out.path {
            if let Ok(raw) = std::fs::read_to_string(path) {
                if let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) {
                    if let Some(b) = v["enabled"].as_bool() { out.enabled = b; }
                    if let Some(f) = v["size"].as_f64() { out.size = (f as f32).clamp(0.75, 1.5); }
                    if let Some(f) = v["opacity"].as_f64() { out.opacity = (f as f32).clamp(0.4, 1.0); }
                    if let Some(a) = v["slots"].as_array() {
                        if a.len() == 8 {
                            for (i, n) in a.iter().enumerate() {
                                if let Some(n) = n.as_u64().filter(|n| *n < 8) {
                                    out.slots[i] = n as usize;
                                }
                            }
                        }
                    }
                }
            }
        }
        out // Never restore the open state.
    }
    fn save(&self) {
        if let Some(path) = &self.path {
            if let Some(parent) = path.parent() { let _ = std::fs::create_dir_all(parent); }
            let cfg = serde_json::json!({
                "schema": 2, "enabled": self.enabled, "size": self.size,
                "opacity": self.opacity, "slots": self.slots
            });
            if let Ok(bytes) = serde_json::to_vec_pretty(&cfg) {
                let tmp = path.with_extension("json.tmp");
                if std::fs::write(&tmp, bytes).is_ok() { let _ = std::fs::rename(tmp, path); }
            }
        }
    }
    fn poll_java(&self) -> Option<(i32, i64)> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<(i32, i64)> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("fcWheelSetEnabled"), jni_sig!("(Z)V"),
                &[JValue::Bool(self.enabled.into())])?;
            let signal = env.call_method(&*activity, jni_str!("fcWheelTakeSignal"),
                jni_sig!("()I"), &[])?.i()?;
            let hover = env.call_method(&*activity, jni_str!("fcWheelTakeHover"),
                jni_sig!("()J"), &[])?.j()?;
            Ok((signal,hover))
        }).ok()
    }
    fn radial_index(center: Pos2, pointer: Pos2, radius: f32) -> Option<usize> {
        let v = pointer - center;
        if v.length() < radius * HUB || v.length() > radius { return None; }
        let theta = (v.y.atan2(v.x) + PI / 2.0).rem_euclid(TAU);
        Some(((theta / (TAU / 8.0)).floor() as usize).min(7))
    }
    pub fn capture(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        if let Some((button, hover)) = self.poll_java() {
            if hover == -1 { self.pen_hover = None; }
            else if hover != 0 {
                let bits = hover as u64;
                let x = f32::from_bits((bits >> 32) as u32);
                let y = f32::from_bits(bits as u32);
                let ppp = ctx.pixels_per_point();
                let pos = pos2(x / ppp, y / ppp);
                if pos.is_finite() && ctx.content_rect().contains(pos) {
                    self.pen_hover = Some(pos);
                    // Show real pen hover when wheel is closed (do not invent
                    // touch or trackpad movement).
                    if !self.open && !self.settings_open {
                        raw.events.push(egui::Event::PointerMoved(pos));
                    }
                }
            }
            if button == 1 && self.enabled && !self.settings_open {
                if self.open {
                    self.open = false;
                    self.center = None;
                } else if let Some(pointer) = self.pen_hover {
                    let half = DEFAULT_RADIUS * self.size + 8.0;
                    let screen = ctx.content_rect();
                    self.center = Some(pos2(
                        pointer.x.clamp(screen.left() + half, (screen.right()-half).max(screen.left()+half)),
                        pointer.y.clamp(screen.top() + half, (screen.bottom()-half).max(screen.top()+half)),
                    ));
                    self.open = true;
                    self.just_isolated = false;
                }
                ctx.request_repaint();
            }
        }
        if !self.enabled || self.settings_open {
            self.open = false;
            self.center = None;
        }
        if !self.open { self.just_isolated = false; return; }
        let center = match self.center { Some(c) => c, None => return };
        let r = DEFAULT_RADIUS * self.size;
        let mut filtered = Vec::with_capacity(raw.events.len()+1);
        if !self.just_isolated {
            filtered.push(egui::Event::PointerGone);
            self.just_isolated = true;
        }
        for event in std::mem::take(&mut raw.events) {
            match event {
                egui::Event::PointerMoved(p) => {
                    self.pen_hover = Some(p);
                    self.hovered_segment = Self::radial_index(center, p, r);
                },
                egui::Event::PointerButton {pos, pressed: true, ..} => {
                    if let Some(slot) = Self::radial_index(center,pos,r) {
                        self.last_slot = slot;
                        self.pending = Some(COMMANDS[self.slots[slot]].1);
                    }
                    self.open = false; self.center = None;
                    self.hovered_segment = None;
                    ctx.request_repaint();
                },
                egui::Event::PointerButton { .. } | egui::Event::Touch { .. } => {},
                egui::Event::Key { key: egui::Key::Escape, pressed: true, .. } => {
                    self.open = false; self.center = None;
                    self.hovered_segment = None;
                },
                e => filtered.push(e),
            }
        }
        raw.events = filtered;
        if let Some(p) = self.pen_hover {
            self.hovered_segment = Self::radial_index(center,p,r);
        }
        if self.open { ctx.request_repaint_after(std::time::Duration::from_millis(60)); }
    }
    fn icon(p: &egui::Painter, id: usize, c: Pos2, s: f32, color: Color32) {
        let stroke = Stroke::new(2.2*s, color);
        let l = |x:f32,y:f32| c + vec2(x*s,y*s);
        match id {
            0 => { // Razor: slanted blade
                p.line_segment([l(-10.0,-7.0),l(8.0,10.0)],stroke);
                p.line_segment([l(-4.0,-12.0),l(12.0,4.0)],stroke);
                p.line_segment([l(-8.0,7.0),l(7.0,-8.0)],stroke);
            },
            1 => { // Select cursor
                p.add(egui::Shape::line(vec![
                    l(-8.0,-13.0),l(-7.0,12.0),l(-1.0,5.0),l(5.0,14.0),
                    l(10.0,11.0),l(4.0,3.0),l(13.0,1.0),l(-8.0,-13.0)
                ],stroke));
            },
            2 => { // Hand
                p.line_segment([l(-8.0,0.0),l(-6.0,11.0)],stroke);
                p.line_segment([l(-6.0,11.0),l(3.0,15.0)],stroke);
                p.line_segment([l(3.0,15.0),l(11.0,8.0)],stroke);
                for x in [-3.0,2.0,7.0] {
                    p.line_segment([l(x,-7.0),l(x,5.0)],stroke);
                    p.circle_stroke(l(x,-7.0),1.8*s,stroke);
                }
            },
            3 | 4 => { // White classic hook arrows, not Unicode glyphs
                let dir = if id == 3 { -1.0 } else { 1.0 };
                p.add(egui::Shape::line(vec![
                    l(-dir*6.0,-7.0),l(dir*4.0,-7.0),
                    l(dir*10.0,-2.0),l(dir*10.0,6.0),
                    l(dir*5.0,11.0)
                ],stroke));
                p.line_segment([l(-dir*6.0,-7.0),l(0.0,-13.0)],stroke);
                p.line_segment([l(-dir*6.0,-7.0),l(0.0,-1.0)],stroke);
            },
            5 => { // Play/Pause
                p.add(egui::Shape::convex_polygon(vec![l(-11.0,-11.0),l(-11.0,11.0),l(0.0,0.0)],color,Stroke::NONE));
                p.line_segment([l(5.0,-10.0),l(5.0,10.0)],Stroke::new(3.2*s,color));
                p.line_segment([l(11.0,-10.0),l(11.0,10.0)],Stroke::new(3.2*s,color));
            },
            6 | 7 => { // Zoom glass
                p.circle_stroke(l(-3.0,-4.0),8.0*s,stroke);
                p.line_segment([l(3.0,2.0),l(12.0,12.0)],stroke);
                p.line_segment([l(-8.0,-4.0),l(2.0,-4.0)],stroke);
                if id == 6 { p.line_segment([l(-3.0,-9.0),l(-3.0,1.0)],stroke); }
            },
            _ => {}
        }
    }
    fn draw(&self, ui: &egui::Ui, center: Pos2, radius: f32, hover: Option<usize>) {
        let p=ui.painter();
        // Soft diffuse shadow, thin FilmCraft-lavender outer stroke.
        for i in (1..=5).rev() {
            p.circle_filled(center + vec2(0.0,4.0),radius+(i as f32)*2.8,
                Color32::from_black_alpha(7).gamma_multiply(self.opacity));
        }
        let width=TAU/8.0;
        for slot in 0..8 {
            let a=-PI/2.0 + width*slot as f32;
            let mut pts=Vec::with_capacity(24);
            for j in 0..=10 {
                let t=a+width*(j as f32/10.0);
                pts.push(center+vec2(t.cos(),t.sin())*radius);
            }
            for j in (0..=10).rev() {
                let t=a+width*(j as f32/10.0);
                pts.push(center+vec2(t.cos(),t.sin())*(radius*HUB));
            }
            let fill=if hover==Some(slot) { ACCENT } else { Color32::from_rgb(48,49,54) };
            p.add(egui::Shape::convex_polygon(pts,
                fill.gamma_multiply(self.opacity),
                Stroke::new(0.85,Color32::from_gray(98).gamma_multiply(self.opacity))));
            let angle=a+width*0.5;
            let icon_center=center+vec2(angle.cos(),angle.sin())*(radius*0.66)-vec2(0.0,10.5);
            Self::icon(p,self.slots[slot],icon_center,radius/145.0,Color32::WHITE.gamma_multiply(self.opacity));
            let label_pos=icon_center+vec2(0.0,27.0);
            p.text(label_pos,egui::Align2::CENTER_CENTER,COMMANDS[self.slots[slot]].0,
                FontId::proportional((12.0*radius/143.0).max(10.0)),Color32::WHITE.gamma_multiply(self.opacity));
        }
        p.circle_stroke(center,radius,Stroke::new(1.5,LAVENDER.gamma_multiply(self.opacity)));
        p.circle_filled(center,radius*HUB,NAVY); // solid launcher roundel, never rectangular
        p.circle_stroke(center,radius*HUB,Stroke::new(2.0,LAVENDER));
        p.text(center+vec2(0.0,-radius*0.065),egui::Align2::CENTER_CENTER,"Fc",
            FontId::proportional(radius*0.29),LAVENDER);
        p.text(center+vec2(0.0,radius*0.19),egui::Align2::CENTER_CENTER,
            if self.open { COMMANDS[self.slots[self.last_slot]].0 } else { "Default" },
            FontId::proportional((radius*0.09).max(10.0)),Color32::WHITE);
    }
    fn slider(ui: &mut egui::Ui, label: &str, value: &mut f32, min:f32, max:f32) -> bool {
        ui.horizontal(|ui| {
            ui.label(label);
            ui.add_space(5.0);
            let (rect,resp)=ui.allocate_exact_size(vec2(170.0,29.0),Sense::click_and_drag());
            let left=rect.left()+9.0;let right=rect.right()-9.0;
            let mut changed=false;
            if resp.clicked() || resp.dragged() {
                if let Some(p)=resp.interact_pointer_pos() {
                    let next=(min+(max-min)*((p.x-left)/(right-left)).clamp(0.0,1.0)*100.0).round()/100.0;
                    if (*value-next).abs() > 0.001 { *value=next; changed=true; }
                }
            }
            let t=((*value-min)/(max-min)).clamp(0.0,1.0);
            let x=left+(right-left)*t;
            let track=egui::Rect::from_min_max(pos2(left,rect.center().y-3.5),pos2(right,rect.center().y+3.5));
            ui.painter().rect_filled(track,3.5,Color32::from_rgb(54,57,100));
            ui.painter().rect_filled(egui::Rect::from_min_max(track.min,pos2(x,track.max.y)),3.5,LAVENDER);
            ui.painter().circle_filled(pos2(x,rect.center().y),8.0,LAVENDER);
            ui.painter().circle_stroke(pos2(x,rect.center().y),8.0,Stroke::new(1.0,Color32::WHITE));
            ui.label(format!("{:.0}%",*value*100.0));
            changed
        }).inner
    }
    fn settings(&mut self, ctx: &egui::Context) {
        if !self.settings_open { return; }
        let mut is_open=true;
        let mut changed=false;
        let viewport=ctx.content_rect();
        egui::Window::new("Fc   Customize Stylus Wheel")
            .id(egui::Id::new("filmcraft.stylus.settings"))
            .open(&mut is_open).collapsible(false).resizable(false)
            .default_width(444.0)
            .default_pos(pos2((viewport.center().x-450.0).max(10.0),55.0))
            .show(ctx, |ui| {
                ui.set_min_width(422.0);
                ui.label("Assign an action to each of the eight wheel segments.");
                ui.separator();
                ui.strong("Wheel slots");
                const POSITIONS:[&str;8]=[
                    "Top","Upper right","Right","Lower right","Bottom",
                    "Lower left","Left","Upper left"];
                for index in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("{:02}  {}",index+1,POSITIONS[index]));
                        ui.add_space(6.0);
                        egui::ComboBox::from_id_salt(("fc_wheel_slot",index))
                            .selected_text(COMMANDS[self.slots[index]].0)
                            .width(160.0)
                            .show_ui(ui,|ui|{
                                for (j,(name,_)) in COMMANDS.iter().enumerate() {
                                    changed |= ui.selectable_value(&mut self.slots[index],j,*name).changed();
                                }
                            });
                    });
                }
                ui.add_space(6.0);
                ui.separator();
                ui.strong("Appearance");
                changed |= ui.checkbox(&mut self.enabled,"Enable Stylus Wheel").changed();
                changed |= Self::slider(ui,"Wheel size",&mut self.size,0.75,1.50);
                changed |= Self::slider(ui,"Opacity",&mut self.opacity,0.40,1.0);
                ui.label("Size: 75–150%   •   Opacity: 40–100%");
                ui.separator();
                ui.label("Live preview updates beside this panel. Changes save automatically.");
                ui.horizontal(|ui| {
                    if ui.button("Reset defaults").clicked() {
                        self.enabled=true;self.size=1.0;self.opacity=0.90;self.slots=DEFAULT_SLOTS;
                        changed=true;
                    }
                    if ui.button("Done").clicked() { self.settings_open=false; }
                });
            });
        self.settings_open &= is_open;
        if changed { self.save(); ctx.request_repaint(); }
        // Exactly one actual-size preview OUTSIDE dialog, matching DeckCraft.
        if self.settings_open {
            let radius=DEFAULT_RADIUS*self.size;
            let d=2.0*radius;
            let center=pos2((viewport.center().x+radius+155.0).min(viewport.right()-radius-8.0),
                (viewport.center().y).clamp(viewport.top()+radius+8.0,viewport.bottom()-radius-8.0));
            egui::Area::new(egui::Id::new("filmcraft.wheel.preview"))
                .order(egui::Order::Foreground)
                .fixed_pos(center-vec2(radius,radius)).interactable(false)
                .show(ctx,|ui|{
                    let (rect,_)=ui.allocate_exact_size(vec2(d,d),Sense::hover());
                    self.draw(ui,rect.center(),radius,Some(1));
                });
        }
    }
    pub fn show(&mut self, ctx: &egui::Context) -> Option<&'static str> {
        if ctx.data_mut(|d| d.remove_temp::<bool>(
            egui::Id::new("filmcraft.stylus.settings.open"))).unwrap_or(false) {
            self.settings_open = true;
            self.open = false;
            self.center = None;
        }
        self.settings(ctx);
        if self.open && !self.settings_open {
            if let Some(center)=self.center {
                let radius=DEFAULT_RADIUS*self.size;
                egui::Area::new(egui::Id::new("filmcraft.wheel.active"))
                    .order(egui::Order::Foreground)
                    .fixed_pos(center-vec2(radius,radius)).interactable(false)
                    .show(ctx,|ui|{
                        let (rect,_)=ui.allocate_exact_size(vec2(radius*2.0,radius*2.0),Sense::hover());
                        self.draw(ui,rect.center(),radius,self.hovered_segment);
                    });
            }
        }
        // Independent real stylus hover indicator, no always-visible shortcut
        // pad or wheel. The native toolbar remains unchanged.
        if !self.open && !self.settings_open {
            if let Some(p)=self.pen_hover {
                let painter=ctx.layer_painter(egui::LayerId::new(
                    egui::Order::Tooltip,egui::Id::new("filmcraft.stylus.hover.marker")));
                painter.circle_stroke(p,5.2,Stroke::new(1.4,LAVENDER));
                painter.circle_stroke(p,3.1,Stroke::new(0.8,Color32::WHITE));
            }
        }
        self.pending.take()
    }
}
