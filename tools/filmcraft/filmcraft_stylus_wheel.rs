//! FilmCraft Android stylus wheel — DeckCraft layout, approved Fc navy/lavender.
//! The pen side-button alone opens/closes the wheel; never show on application launch.
//! Real Magic-Pencil hover is read via the GameActivity bridge. While visible,
//! pointer/hover events are isolated before the underlying editor's input pass.
use android_activity::AndroidApp;
use egui::{Color32, FontId, Pos2, Sense, Stroke, pos2, vec2};
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JValue}};
use std::f32::consts::{PI, TAU};
use std::path::PathBuf;
use std::time::{Instant, Duration};

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
// FilmCraft command equivalents in the same eight-position PhotoCraft arrangement.
const DEFAULT_SLOTS: [usize; 8] = [0, 1, 6, 2, 5, 7, 4, 3];
const DEFAULT_SIZE: f32 = 1.0;
const DEFAULT_OPACITY: f32 = 0.85;
const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);
const FEEDBACK_FADE: Duration = Duration::from_millis(500);
const NAVY: Color32 = Color32::from_rgb(0x00, 0x04, 0x7a);
const LAVENDER: Color32 = Color32::from_rgb(0x9a, 0x9c, 0xd9);
const ACCENT: Color32 = Color32::from_rgb(0x36, 0x4c, 0xd9);
const HUB: f32 = 0.36;
const DEFAULT_RADIUS: f32 = 128.0;
const PLATE_SIZE: f32 = 312.0;

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
    feedback_message: &'static str,
    feedback_at: Instant,
}
impl Wheel {
    pub fn new(dir: Option<PathBuf>, app: &AndroidApp) -> Self {
        let path = dir.map(|d| d.join("filmcraft-stylus-wheel.json"));
        let mut out = Self {
            app: app.clone(), path, enabled: true, size: DEFAULT_SIZE, opacity: DEFAULT_OPACITY,
            slots: DEFAULT_SLOTS, last_slot: 1, settings_open: false,
            open: false, center: None, pen_hover: None,
            hovered_segment: None, just_isolated: false, pending: None,
            feedback_message: "Hover + press stylus button to open wheel",
            feedback_at: Instant::now(),
        };
        if let Some(path) = &out.path {
            if let Ok(raw) = std::fs::read_to_string(path) {
                if let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) {
                    if let Some(b) = v["enabled"].as_bool() { out.enabled = b; }
                    if let Some(f) = v["size"].as_f64() { out.size = (f as f32).clamp(0.75, 1.25); }
                    if let Some(f) = v["opacity"].as_f64() { out.opacity = (f as f32).clamp(0.60, 1.0); }
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
    fn notify(&mut self, message: &'static str, ctx: &egui::Context) {
        self.feedback_message = message;
        self.feedback_at = Instant::now();
        ctx.request_repaint();
    }
    /// Identical bottom-centred 350×31 notification timing and placement to
    /// the approved PhotoCraft wheel; always noninteractive.
    fn paint_feedback(&self, ctx: &egui::Context) {
        let elapsed=self.feedback_at.elapsed();
        if elapsed >= FEEDBACK_HOLD + FEEDBACK_FADE { return; }
        let alpha=if elapsed <= FEEDBACK_HOLD {1.0}
            else {1.0 - (elapsed-FEEDBACK_HOLD).as_secs_f32()/FEEDBACK_FADE.as_secs_f32()};
        let alpha=alpha.clamp(0.0,1.0);
        let screen=ctx.content_rect();
        egui::Area::new(egui::Id::new("filmcraft-wheel-bottom-message"))
            .order(egui::Order::Foreground)
            .fixed_pos(pos2((screen.center().x-175.0).max(screen.left()),screen.bottom()-43.0))
            .interactable(false)
            .show(ctx,|ui|{
                let (rect,_)=ui.allocate_exact_size(vec2(350.0,31.0),Sense::hover());
                let p=ui.painter_at(rect);
                p.rect_filled(rect,13.0,Color32::from_rgba_unmultiplied(54,54,57,(238.0*alpha) as u8));
                p.rect_stroke(rect,13.0,Stroke::new(1.0,
                    Color32::from_gray(90).gamma_multiply(alpha)),egui::StrokeKind::Inside);
                p.text(rect.center(),egui::Align2::CENTER_CENTER,self.feedback_message,
                    FontId::proportional(11.0),Color32::from_gray(230).gamma_multiply(alpha));
            });
        ctx.request_repaint_after(Duration::from_millis(50));
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
        let theta = (v.y.atan2(v.x) + PI / 2.0 + TAU / 16.0).rem_euclid(TAU);
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
                    self.notify("Hover to highlight • tap tip to select",ctx);
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
                        self.notify(COMMANDS[self.slots[slot]].0,ctx);
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
    fn draw(&self, ui: &egui::Ui, center: Pos2, radius: f32, hover: Option<usize>) {
        let painter=ui.painter();
        let scale=radius/DEFAULT_RADIUS;
        // PhotoCraft: twelve close-spaced feathered layers; no hard halo.
        for step in 0..12 {
            let spread=(12.0-step as f32*0.82)*scale;
            let softness=0.008+step as f32*0.0017;
            painter.circle_filled(center+vec2(0.8,2.0)*scale,
                radius+spread,Color32::BLACK.gamma_multiply(softness*self.opacity));
        }
        painter.circle_filled(center,radius,
            Color32::from_gray(53).gamma_multiply(self.opacity));
        const ICONS:[filmcraft_ui_egui::icons::Icon;8]=[
            filmcraft_ui_egui::icons::Icon::Razor,
            filmcraft_ui_egui::icons::Icon::Selection,
            filmcraft_ui_egui::icons::Icon::Hand,
            filmcraft_ui_egui::icons::Icon::Undo,
            filmcraft_ui_egui::icons::Icon::Redo,
            filmcraft_ui_egui::icons::Icon::Play,
            filmcraft_ui_egui::icons::Icon::Zoom,
            filmcraft_ui_egui::icons::Icon::Zoom,
        ];
        for slot in 0..8 {
            let degrees=-90.0+slot as f32*45.0;
            let first=(degrees-21.5).to_radians();
            let last=(degrees+21.5).to_radians();
            let mut pts=Vec::with_capacity(18);
            pts.push(center);
            for j in 0..=16 {
                let a=first+(last-first)*j as f32/16.0;
                pts.push(center+vec2(a.cos(),a.sin())*radius);
            }
            let active=hover==Some(slot);
            let base=if slot%2==0 { Color32::from_rgb(51,52,56) }
                else { Color32::from_rgb(65,66,70) };
            let fill=if active { ACCENT } else { base };
            painter.add(egui::Shape::convex_polygon(pts,
                fill.gamma_multiply(self.opacity),
                Stroke::new(if active {1.6}else{0.65},
                    if active {LAVENDER} else {Color32::from_gray(87)}.gamma_multiply(self.opacity))));
            let a=degrees.to_radians();
            let icon_pos=center+vec2(a.cos(),a.sin())*(87.0*scale);
            let rect=egui::Rect::from_center_size(icon_pos-vec2(0.0,10.0)*scale,
                vec2(24.0,24.0)*scale);
            let cmd=self.slots[slot];
            filmcraft_ui_egui::icons::paint(painter,rect,ICONS[cmd],
                Color32::WHITE.gamma_multiply(self.opacity));
            // Distinguish native Zoom In / Zoom Out while retaining the native
            // toolbar magnifier path as the base icon.
            if cmd==6 || cmd==7 {
                painter.text(rect.center()+vec2(1.0,-1.5)*scale,
                    egui::Align2::CENTER_CENTER,if cmd==6 {"+"}else{"−"},
                    FontId::proportional(12.0*scale),Color32::WHITE);
            }
            painter.text(icon_pos+vec2(0.0,13.0)*scale,
                egui::Align2::CENTER_CENTER,COMMANDS[cmd].0,
                FontId::proportional(11.0*scale),
                Color32::from_gray(220).gamma_multiply(self.opacity));
        }
        painter.circle_stroke(center,radius,
            Stroke::new(0.8,Color32::from_gray(103).gamma_multiply(self.opacity)));
        // Exact FilmCraft navy/lavender launch colours, circular hub with logo.
        painter.circle_filled(center,48.0*scale,NAVY);
        painter.circle_stroke(center,48.0*scale,Stroke::new(1.4,LAVENDER));
        painter.text(center-vec2(0.0,8.0)*scale,egui::Align2::CENTER_CENTER,"Fc",
            FontId::proportional(35.0*scale),LAVENDER);
        painter.text(center+vec2(0.0,22.0)*scale,egui::Align2::CENTER_CENTER,
            if self.open { COMMANDS[self.slots[self.last_slot]].0 } else {"Default"},
            FontId::proportional(11.0*scale),Color32::WHITE);
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
                    let next=((min+(max-min)*((p.x-left)/(right-left)).clamp(0.0,1.0))*100.0).round()/100.0;
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
        let mut open=self.settings_open;
        let mut changed=false;
        let result=egui::Window::new("Stylus Wheel — Default")
            .id(egui::Id::new("filmcraft.stylus.settings"))
            .open(&mut open).collapsible(false).resizable(false)
            .default_width(338.0)
            .show(ctx,|ui|{
                ui.label("Style: Default  •  8 segments");
                ui.label("Choose a tool for each position. Existing selections swap positions.");
                ui.separator();
                for slot in 0..8 {
                    ui.horizontal(|ui|{
                        ui.label(format!("Slot {}",slot+1));
                        let mut selected=self.slots[slot];
                        egui::ComboBox::from_id_salt(("fc_wheel_slot",slot))
                            .selected_text(COMMANDS[selected].0).width(180.0)
                            .show_ui(ui,|ui|{
                                for (j,(name,_)) in COMMANDS.iter().enumerate() {
                                    ui.selectable_value(&mut selected,j,*name);
                                }
                            });
                        if selected!=self.slots[slot] {
                            if let Some(old)=self.slots.iter().position(|n| *n==selected) {
                                self.slots[old]=self.slots[slot];
                            }
                            self.slots[slot]=selected;
                            changed=true;
                        }
                    });
                }
                ui.separator();
                changed|=ui.checkbox(&mut self.enabled,"Enable Stylus Wheel").changed();
                changed|=Self::slider(ui,"Wheel size",&mut self.size,0.75,1.25);
                changed|=Self::slider(ui,"Opacity",&mut self.opacity,0.60,1.0);
                if ui.button("Restore Default").clicked() {
                    self.slots=DEFAULT_SLOTS;
                    self.size=DEFAULT_SIZE;
                    self.opacity=DEFAULT_OPACITY;
                    changed=true;
                }
                ui.separator();
                ui.label("Actual-size preview appears beside this window.");
                ui.label("Size: 75–125%  •  Opacity: 60–100%");
                ui.label("Hover + pen-button: open wheel  •  Tap a segment: select.");
            });
        self.settings_open=open;
        if changed {
            self.save();
            self.notify("Wheel settings saved • live preview",ctx);
        }
        // PhotoCraft's true-scale preview lives beside the dialog. No preview
        // inside this window and no unintended editor interaction underneath.
        if self.settings_open {
            if let Some(response)=result {
                let screen=ctx.content_rect();
                let dialog=response.response.rect;
                let size=PLATE_SIZE*self.size;
                let margin=16.0;
                let right_room=screen.right()-dialog.right();
                let left_room=dialog.left()-screen.left();
                let center_x=if right_room>=size+margin*2.0 {
                    (dialog.right()+screen.right())*0.5
                } else if left_room>=size+margin*2.0 {
                    (screen.left()+dialog.left())*0.5
                } else { screen.center().x };
                let center=pos2(
                    center_x.clamp(screen.left()+size*0.5,
                        (screen.right()-size*0.5).max(screen.left()+size*0.5)),
                    dialog.center().y.clamp(screen.top()+size*0.5,
                        (screen.bottom()-size*0.5).max(screen.top()+size*0.5))
                );
                egui::Area::new(egui::Id::new("filmcraft.wheel.preview"))
                    .order(egui::Order::Foreground)
                    .fixed_pos(center-vec2(size*0.5,size*0.5)).interactable(false)
                    .show(ctx,|ui|{
                        let (rect,_)=ui.allocate_exact_size(vec2(size,size),Sense::hover());
                        self.draw(ui,rect.center(),DEFAULT_RADIUS*self.size,None);
                    });
            }
        }
    }
    pub fn show(&mut self, ctx: &egui::Context) -> Option<&'static str> {
        if let Some(enabled) = ctx.data_mut(|d| d.remove_temp::<bool>(
            egui::Id::new("filmcraft.stylus.menu.enabled"))) {
            if self.enabled != enabled {
                self.enabled = enabled;
                self.open = false;
                self.center = None;
                self.save();
                self.notify(if enabled {"Stylus Wheel enabled"}
                    else {"Stylus Wheel disabled"},ctx);
            }
        }
        ctx.data_mut(|d| d.insert_temp(
            egui::Id::new("filmcraft.stylus.enabled"),self.enabled));
        if ctx.data_mut(|d| d.remove_temp::<bool>(
            egui::Id::new("filmcraft.stylus.settings.open"))).unwrap_or(false) {
            self.settings_open = true;
            self.open = false;
            self.center = None;
            self.notify("Wheel settings • live preview",ctx);
        }
        self.settings(ctx);
        self.paint_feedback(ctx);
        if self.open && !self.settings_open {
            if let Some(center)=self.center {
                let radius=DEFAULT_RADIUS*self.size;
                let size=PLATE_SIZE*self.size;
                egui::Area::new(egui::Id::new("filmcraft.wheel.active"))
                    .order(egui::Order::Foreground)
                    .fixed_pos(center-vec2(size*0.5,size*0.5)).interactable(false)
                    .show(ctx,|ui|{
                        let (rect,_)=ui.allocate_exact_size(vec2(size,size),Sense::hover());
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
