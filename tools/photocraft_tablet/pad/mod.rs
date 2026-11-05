//! Tablet shortcut controls adapted from morte2437/photocraft-android (MIT / Apache-2.0).
pub(crate) mod config;
mod layout;
mod wheel;
use layout::{Control, Layout, PadTouch};
use photocraft_ui_egui::menus;
use config::{Chord, MAX_KEYS, MIN_KEYS, PadConfig, SENSITIVITY_RANGE, Side, WHEEL_SIZE_RANGE, WheelMode};
use egui::{Align2, Event, FontId, Key, Modifiers, Stroke};
use photocraft_ui_egui::PhotocraftApp;


use photocraft_ui_egui::theme::Tokens;

use serde_json::Value;
use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use std::rc::Rc;

/// The settings and whether their window is open: shared with the menu rows.
pub struct Shared {
    pub config: PadConfig,
    pub settings_open: bool,
    path: PathBuf,
}

impl Shared {
    fn save(&self) {
        if let Err(e) = self.config.save(&self.path) {
            log::error!("couldn't save the Shortcut Pad settings: {e}");
        }
    }
}

pub struct ShortcutPad {
    shared: Rc<RefCell<Shared>>,
    contacts: HashMap<egui::TouchId, Control>,
    reserved: Option<egui::Rect>,
    layer: Option<egui::LayerId>,
    mouse: Option<Control>,
    /// Where the pad was drawn last frame (`None`: hidden).
    layout: Option<Layout>,
    /// The wheel function in use (an index into the configured list).
    mode: usize,
    turn: wheel::Turn,
    /// The ring is being turned.
    turning: bool,
    /// Keys being held, with the chord they pressed (released with the same one even if the
    /// settings change meanwhile).
    held: HashMap<usize, Chord>,
    /// Keys locked down by a double tap: kept in `held` after the finger lifts, until a tap.
    locked: HashSet<usize>,
    /// Keys whose touch unlocked them: their lift does nothing.
    unlocking: HashSet<usize>,
    /// When each held key was touched, and the last short tap (key, when it lifted), to spot a
    /// double tap.
    down_at: HashMap<usize, f64>,
    last_tap: Option<(usize, f64)>,
    /// The time of the frame being routed (`Env::now`).
    now: f64,
    /// Wheel changes waiting for the frame (they need the app and the egui context).
    pending: Vec<wheel::Action>,
    /// The large ring shown while the wheel is pressed.
    big: Option<BigRing>,
    /// Where the finger turning the wheel is.
    finger: Option<egui::Pos2>,
    /// What the wheel press started on, and where; whether the finger has slid since (a tap on
    /// the centre switches function, a slide turns).
    press: Option<(Control, egui::Pos2)>,
    slid: bool,
    /// The keyboard key was tapped (the shell opens or closes the on-screen keyboard).
    keyboard_tapped: bool,
    /// The shell has the on-screen keyboard open for the pad (the key is lit).
    pub keyboard_on: bool,
    /// The full screen key was tapped (the screen mode switches in `run_pending`).
    screen_tapped: bool,
    /// The screen mode last frame, for the full screen key's icon.
    screen_step: ScreenStep,
    /// The window's content area last frame (keeps the large ring on screen).
    screen: egui::Rect,

    /// Brush size and hardness as the turn has set them, unrounded, so slow turns add up.
    size_target: Option<f32>,
    hardness_target: Option<f32>,

}

/// The large ring: where it is and how big.
#[derive(Clone, Copy, Debug, PartialEq)]
struct BigRing {
    center: egui::Pos2,
    radius: f32,
}

/// The large ring for a press on the wheel at `wheel`: as near the wheel as it fits on screen
/// (it slides in from the pad's edge onto the canvas).
fn big_ring(wheel: egui::Pos2, radius: f32, screen: egui::Rect, side: Side) -> BigRing {
    let m = radius + 8.0;
    let x = match side {
        Side::Right => wheel.x.min(screen.right() - m),
        Side::Left => wheel.x.max(screen.left() + m),
    };
    let y = if screen.height() > 2.0 * m { wheel.y.clamp(screen.top() + m, screen.bottom() - m) } else { screen.center().y };
    BigRing { center: egui::pos2(x, y), radius }
}

/// Brush sizes the engine accepts (`photocraft_paint::MAX_BRUSH_SIZE`).
const MAX_BRUSH_SIZE: f32 = 5000.0;

/// Seconds for a double tap: the first touch's length, and the gap before the second.
const DOUBLE_TAP: f64 = 0.35;

impl ShortcutPad {
    pub fn new(files_dir: PathBuf) -> Self {
        let path = files_dir.join("shortcut-pad.json");
        let mut config = PadConfig::load(&path);
        if !path.exists() {
            config.enabled = files_dir.join("shortcut-pad-visible").exists();
            if files_dir.join("shortcut-pad-left").exists() { config.side = Side::Left; }
        }
        menus::artcraft_pad_set_visible(config.enabled);
        menus::artcraft_pad_set_left(config.side == Side::Left);
        Self {
            shared: Rc::new(RefCell::new(Shared { config, settings_open: false, path })),
            contacts: HashMap::new(), reserved: None, layer: None, mouse: None,
            layout: None,
            mode: 0,
            turn: wheel::Turn::default(),
            turning: false,
            held: HashMap::new(),
            locked: HashSet::new(),
            unlocking: HashSet::new(),
            down_at: HashMap::new(),
            last_tap: None,
            now: 0.0,
            pending: Vec::new(),
            big: None,
            finger: None,
            press: None,
            slid: false,
            keyboard_tapped: false,
            keyboard_on: false,
            screen_tapped: false,
            screen_step: ScreenStep::Normal,
            screen: egui::Rect::NOTHING,

            size_target: None,
            hardness_target: None,

        }
    }

    pub fn finger_mode(&self) -> config::FingerMode { self.shared.borrow().config.finger_mode }
    pub fn open_settings(&mut self) { self.shared.borrow_mut().settings_open = true; }

    fn mode(&self) -> WheelMode {
        let s = self.shared.borrow();
        let modes = &s.config.wheel_modes;
        modes.get(self.mode % modes.len().max(1)).copied().unwrap_or(WheelMode::Zoom)
    }

    pub fn input(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        self.now = ctx.input(|i| i.time);
        let mut out = Vec::new();
        if !menus::artcraft_pad_visible() || !raw.focused {
            self.release_all(&mut out);
            self.contacts.clear();
            self.mouse = None;
            out.append(&mut raw.events);
            raw.events = out;
            return;
        }
        let Some(l) = self.layout.clone() else { return };
        let hit = |pos| l.panel.contains(pos) && ctx.layer_id_at(pos) == self.layer;
        let touch_frame = !self.contacts.is_empty() || raw.events.iter().any(|e|
            matches!(e, Event::Touch { pos, .. } if hit(*pos)));
        for event in raw.events.drain(..) {
            match event {
                Event::Touch { id, phase, pos, .. } => {
                    let control = match phase {
                        egui::TouchPhase::Start if hit(pos) => {
                            let c = l.hit(pos); self.contacts.insert(id, c); Some(PadTouch::Down(c, pos))
                        }
                        egui::TouchPhase::Move => self.contacts.get(&id).map(|&c| PadTouch::Move(c,pos)),
                        egui::TouchPhase::End | egui::TouchPhase::Cancel => self.contacts.remove(&id).map(PadTouch::Up),
                        _ => None,
                    };
                    if let Some(t) = control { self.touch(t, &mut out); } else {out.push(event);}
                }
                Event::PointerButton { pos, button: egui::PointerButton::Primary, pressed, .. }
                    if self.mouse.is_some() || hit(pos) => {
                    if !touch_frame {
                        if pressed { let c=l.hit(pos); self.mouse=Some(c); self.touch(PadTouch::Down(c,pos), &mut out); }
                        else if let Some(c)=self.mouse.take() { self.touch(PadTouch::Up(c), &mut out); }
                    }
                }
                Event::PointerMoved(pos) if self.mouse.is_some() => {
                    if let Some(c)=self.mouse { self.touch(PadTouch::Move(c,pos), &mut out); }
                }
                _ => out.push(event),
            }
        }
        raw.events = out;
    }
    fn touch(&mut self, t: PadTouch, out: &mut Vec<Event>) {
        match t {
            // A tap on a locked key unlocks it, and its lift is ignored.
            PadTouch::Down(Control::Key(i), _) if self.locked.remove(&i) => {
                if let Some(chord) = self.held.remove(&i) {
                    out.extend(release(chord));
                }
                self.unlocking.insert(i);
                self.last_tap = None;
            }
            PadTouch::Down(Control::Key(i), _) => {
                // The second touch of a double tap locks the key down.
                if self.last_tap.take().is_some_and(|(k, at)| k == i && self.now - at <= DOUBLE_TAP) {
                    self.locked.insert(i);
                }
                self.down_at.insert(i, self.now);
                let shortcut = self.shared.borrow().config.keys.get(i).map(|k| k.shortcut.clone()).unwrap_or_default();
                match config::parse(&shortcut) {
                    Ok(chord) if !chord.is_empty() => {
                        out.extend(press(chord));
                        if let Some(old) = self.held.insert(i, chord) {
                            out.extend(release(old));
                        }
                    }
                    Ok(_) => {}
                    Err(e) => log::warn!("Shortcut Pad key {}: {e}", i + 1),
                }
            }
            PadTouch::Up(Control::Key(i)) => {
                let since = self.down_at.remove(&i);
                if self.unlocking.remove(&i) || self.locked.contains(&i) {
                    return;
                }
                if let Some(chord) = self.held.remove(&i) {
                    out.extend(release(chord));
                }
                // A short touch can be the first half of a double tap.
                if since.is_some_and(|at| self.now - at <= DOUBLE_TAP) {
                    self.last_tap = Some((i, self.now));
                }
            }
            PadTouch::Down(Control::Keyboard, _) => self.keyboard_tapped = true,
            PadTouch::Down(Control::ScreenMode, _) => self.screen_tapped = true,
            // The centre is a button: a tap that doesn't slide switches function when lifted,
            // and it neither opens the large ring nor turns.
            PadTouch::Down(Control::Center, p) => {
                self.press = Some((Control::Center, p));
                self.slid = false;
            }
            PadTouch::Move(Control::Center, p) => {
                if self.press.is_some_and(|(_, start)| start.distance(p) > 12.0) {
                    self.slid = true;
                }
            }
            // The ring opens the large ring and turns.
            PadTouch::Down(Control::Ring, p) | PadTouch::Move(Control::Ring, p) => {
                let Some((center, small_r)) = self.layout.as_ref().map(|l| (l.center, l.ring_outer)) else { return };
                if let PadTouch::Down(control, _) = t {
                    self.press = Some((control, p));
                    self.slid = false;
                    self.turn = wheel::Turn::default();
                    self.turning = true;
                    self.size_target = None;
                    self.hardness_target = None;
                    let c = &self.shared.borrow().config;
                    self.big = c.enlarge.then(|| big_ring(center, c.wheel_size / 2.0, self.screen, c.side));
                }
                self.finger = Some(p);
                let (c, r) = self.big.map_or((center, small_r), |b| (b.center, b.radius));
                // Too near the centre for a steady angle: wait for the finger to come out.
                let angle = (p.distance(c) >= r * 0.2).then(|| wheel::angle(c, p));
                let (mode, sensitivity) = (self.mode(), self.shared.borrow().config.sensitivity);
                self.pending.extend(self.turn.moved(mode, angle, sensitivity));
            }
            PadTouch::Up(Control::Ring | Control::Center) => {
                if matches!(self.press, Some((Control::Center, _))) && !self.slid {
                    let n = self.shared.borrow().config.wheel_modes.len().max(1);
                    self.mode = (self.mode + 1) % n;
                }
                self.press = None;
                self.turning = false;
                self.big = None;
                self.finger = None;
            }
            _ => {}
        }
    }

    fn release_all(&mut self, out: &mut Vec<Event>) {
        for (_, chord) in self.held.drain() {
            out.extend(release(chord));
        }
        self.locked.clear();
        self.unlocking.clear();
        self.down_at.clear();
        self.last_tap = None;
        self.turning = false;
        self.big = None;
        self.finger = None;
    }

    /// Apply the wheel's changes (from `logic`, before the app's). A frame's movements are
    /// merged: one zoom, one rotation, one brush change, however many touch events came in.
    pub fn run_pending(&mut self, app: &mut PhotocraftApp, ctx: &egui::Context) {
        if self.take_screen_tap() {
            let _ = menus::invoke(app, ctx, "view.screenMode.cycle", serde_json::json!({}));
        }
        let actions = std::mem::take(&mut self.pending);
        if actions.is_empty() {
            return;
        }
        let (mut zoom, mut rotate, mut size, mut hardness) = (1.0f32, 0.0f32, 1.0f32, 0.0f32);
        let run = |app: &mut PhotocraftApp, id: &str, params: Value| {
            if let Err(e) = photocraft_ui_egui::menus::invoke(app, ctx, id, params) {
                // No document to zoom, nothing to redo…: not worth an error for a wheel turn.
                log::debug!("Shortcut Pad wheel: {id}: {e}");
            }
        };
        for a in actions {
            match a {
                wheel::Action::Zoom(f) => zoom *= f,
                wheel::Action::Rotate(d) => rotate += d,
                wheel::Action::BrushSize(f) => size *= f,
                wheel::Action::Hardness(d) => hardness += d,
                wheel::Action::Command(id) => run(app, id, serde_json::json!({})),
            }
        }
        if zoom != 1.0 {
            app.sync_views();
            if let Some(v) = app.session.active_index().and_then(|i| app.ui.views.get_mut(i)) {
                v.fit_pending = false;
                v.fill_pending = false;
                v.zoom = (v.zoom * zoom).clamp(0.01, 32.0);
            }
        }
        if rotate != 0.0 {
            run(app, "view.rotateView", serde_json::json!({ "delta": rotate }));
        }
        if size != 1.0 {
            let target = (self.size_target.unwrap_or(app.session.tools.brush.size) * size).clamp(1.0, MAX_BRUSH_SIZE);
            self.size_target = Some(target);
            if target.round() != app.session.tools.brush.size {
                run(app, "tools.setBrush", serde_json::json!({ "brush": { "size": target.round() } }));
            }
        }
        if hardness != 0.0 {
            let target = (self.hardness_target.unwrap_or(app.session.tools.brush.hardness) + hardness).clamp(0.0, 1.0);
            self.hardness_target = Some(target);
            let rounded = (target * 100.0).round() / 100.0;
            if rounded != app.session.tools.brush.hardness {
                run(app, "tools.setBrush", serde_json::json!({ "brush": { "hardness": rounded } }));
            }
        }
        ctx.request_repaint();
    }

    /// What the large ring shows for the current function.
    fn readout(app: &PhotocraftApp, mode: WheelMode) -> String {
        let view = app.session.active_index().and_then(|i| app.ui.views.get(i));
        let brush = &app.session.tools.brush;
        match mode {
            WheelMode::Zoom => view.map(|v| format!("{:.0}%", v.zoom * 100.0)).unwrap_or_default(),
            WheelMode::Rotate => view.map(|v| format!("{:.0}°", v.rotation)).unwrap_or_default(),
            WheelMode::BrushSize => format!("{:.0} px", brush.size),
            WheelMode::BrushHardness => format!("{:.0}%", brush.hardness * 100.0),
            WheelMode::History => "Undo ◀ ▶ Redo".into(),
        }
    }

    fn paint_big(&self, p: &egui::Painter, b: BigRing, mode: WheelMode, readout: &str, tk: &Tokens) {
        let (c, r) = (b.center, b.radius);
        let band = r * 0.32;
        let mid = r - band / 2.0;
        p.circle_filled(c, r + 2.0, tk.shadow);
        p.circle_filled(c, r, tk.card);
        p.circle_stroke(c, mid, Stroke::new(band, tk.field));
        p.circle_stroke(c, r, Stroke::new(2.0, tk.accent));
        for k in 0..24 {
            let a = (k as f32 * wheel::TICK).to_radians();
            p.circle_filled(c + egui::vec2(a.cos(), a.sin()) * mid, 1.6, tk.text_faint);
        }
        if let Some(f) = self.finger
            && f.distance(c) > 1.0
        {
            let dir = (f - c).normalized();
            p.circle_filled(c + dir * mid, band * 0.38, tk.accent);
        }
        p.text(c - egui::vec2(0.0, 10.0), Align2::CENTER_CENTER, mode.short(), FontId::proportional(15.0), tk.text_dim);
        p.text(c + egui::vec2(0.0, 12.0), Align2::CENTER_CENTER, readout, FontId::proportional(18.0), tk.text);
    }

    /// Before the app lays out: asks it for the pad's strip along its side edge, below the top
    /// bars (none while the pad is off).
    pub fn reserve(&mut self, ui: &mut egui::Ui) {
        self.reserved = None;
        android_activity::pc_pen::pad(None);
        let mut shared = self.shared.borrow_mut();
        android_activity::pc_pen::reject_palms(shared.config.palm_rejection);
        let enabled = menus::artcraft_pad_visible();
        let side = if menus::artcraft_pad_left() {Side::Left} else {Side::Right};
        if (enabled,side) != (shared.config.enabled,shared.config.side) {
            shared.config.enabled=enabled; shared.config.side=side; shared.save();
        }
        if !enabled {return}
        let panel = if side==Side::Left { egui::Panel::left("artcraft_android_edge_pad_left") }
            else {egui::Panel::right("artcraft_android_edge_pad")};
        panel.exact_size(layout::WIDTH).show(ui, |ui| {
            let r = ui.max_rect();
            let scale = ui.ctx().pixels_per_point();
            android_activity::pc_pen::pad(Some([r.left()*scale, r.top()*scale, r.right()*scale, r.bottom()*scale]));
            self.reserved=Some(r); self.layer=Some(ui.layer_id());
        });
    }
    pub fn show(&mut self, ctx: &egui::Context, app: &PhotocraftApp) {
        let tk = &Tokens::get(ctx);
        self.settings(ctx,tk);
        self.screen = ctx.content_rect();
        self.screen_step = ScreenStep::of(app);
        let config = self.shared.borrow().config.clone();
        let Some(full) = self.reserved else { self.layout=None; return; };
        let mode = self.mode();
        let painter = egui::Painter::new(ctx.clone(), self.layer.unwrap_or(egui::LayerId::background()), full);
        painter.rect_filled(full, 0.0, tk.chrome);
        let layout = Layout::new(full, config.keys.len());
        self.paint(&painter, &layout, &config, mode, tk);
        self.layout = Some(layout);
        if let Some(b) = self.big {
            let painter = ctx.layer_painter(egui::LayerId::new(egui::Order::Foreground, egui::Id::unique("shortcut_pad_ring")));
            self.paint_big(&painter, b, mode, &Self::readout(app, mode), tk);
        }
    }

    fn paint(&self, p: &egui::Painter, l: &Layout, config: &PadConfig, mode: WheelMode, tk: &Tokens) {
        // Labels a size smaller on keys shrunk to fit a short screen.
        let font = FontId::proportional(if l.key_height() < 36.0 { 11.0 } else { 12.0 });
        for (i, rect) in l.keys.iter().enumerate() {
            let down = self.held.contains_key(&i);
            let key_color = config.keys.get(i).and_then(|k| k.color).map(|[r, g, b]| egui::Color32::from_rgb(r, g, b));
            let (fill, color) = match key_color {
                // A coloured key lightens while held; its label is dark or light, whichever reads.
                Some(c) => {
                    let fill = if down { c.lerp_to_gamma(egui::Color32::WHITE, 0.35) } else { c };
                    (fill, contrasting_text(fill))
                }
                None if down => (tk.accent, tk.primary_text),
                None => (tk.field, tk.text),
            };
            p.rect(*rect, tk.radius, fill, Stroke::new(if down { 2.0 } else { 1.0 }, tk.field_border), egui::StrokeKind::Inside);
            // A locked key: a bar along its foot, so it reads as latched, not just touched.
            if self.locked.contains(&i) {
                let bar = egui::Rect::from_min_max(egui::pos2(rect.left() + 5.0, rect.bottom() - 5.0), egui::pos2(rect.right() - 5.0, rect.bottom() - 3.0));
                p.rect_filled(bar, 1.0, color);
            }
            let label = config.keys.get(i).map(|k| k.label.as_str()).unwrap_or("");
            let label = label.to_string();
            // The largest size that fits the key's width (typed labels can be wide), clipped
            // to the key at the smallest.
            let room = rect.width() - 6.0;
            let galley = [font.size, font.size - 1.0, font.size - 2.0, 9.0]
                .into_iter()
                .map(|size| p.layout_no_wrap(label.clone(), FontId::proportional(size), color))
                .find(|g| g.size().x <= room)
                .unwrap_or_else(|| p.layout_no_wrap(label.clone(), FontId::proportional(9.0), color));
            p.with_clip_rect(rect.shrink(2.0)).galley(rect.center() - galley.size() / 2.0, galley, color);
        }
        // The ring, with click-stop marks, and the centre button naming the function.
        let ring = if self.turning { tk.accent } else { tk.field_border };
        p.circle(l.center, l.ring_outer, tk.field, Stroke::new(1.5, ring));
        let mid = (l.ring_outer + l.ring_inner) / 2.0;
        for k in 0..24 {
            let a = (k as f32 * wheel::TICK).to_radians();
            p.circle_filled(l.center + egui::vec2(a.cos(), a.sin()) * mid, 1.2, tk.text_faint);
        }
        p.circle(l.center, l.ring_inner, tk.card, Stroke::new(1.0, tk.field_border));
        let n = config.wheel_modes.len();
        let current = self.mode % n.max(1);
        // One light per function, the current one lit (like a tablet's ring LEDs).
        for k in 0..n {
            let a = (-90.0 + (k as f32 - (n as f32 - 1.0) / 2.0) * 16.0f32).to_radians();
            let at = l.center + egui::vec2(a.cos(), a.sin()) * (l.ring_outer - 5.0);
            p.circle_filled(at, 2.2, if k == current { tk.accent } else { tk.text_faint });
        }
        p.text(l.center, Align2::CENTER_CENTER, mode.short(), FontId::proportional(9.0), tk.text_dim);
        self.paint_keyboard_key(p, l.keyboard, tk);
        self.paint_screen_key(p, l.screen_mode, tk);
    }

    /// The full screen key, drawn like a video player's, showing what a tap does: four corners
    /// pointing out to go (further) full screen, pointing in to come back. Lit in full screen;
    /// with the tool bar kept, a bar along its left edge.
    fn paint_screen_key(&self, p: &egui::Painter, rect: egui::Rect, tk: &Tokens) {
        let step = self.screen_step;
        let lit = step != ScreenStep::Normal;
        p.rect(rect, tk.radius, if lit { tk.accent } else { tk.field }, Stroke::new(1.0, tk.field_border), egui::StrokeKind::Inside);
        let ink = Stroke::new(2.0, if lit { tk.primary_text } else { tk.text });
        let on = step.next() == ScreenStep::Normal;
        if step == ScreenStep::WithToolbar {
            let x = rect.left() + 5.0;
            p.line_segment([egui::pos2(x, rect.top() + 6.0), egui::pos2(x, rect.bottom() - 6.0)], Stroke::new(3.0, ink.color));
        }
        let half = (rect.height() * 0.28).min(rect.width() * 0.3);
        let arm = half * 0.55;
        let c = rect.center();
        for (sx, sy) in [(-1.0f32, -1.0f32), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)] {
            // The corner's point, and its arms going back along both edges.
            let (corner, back) = if on {
                // Inward: the corner sits nearer the middle, its arms reaching out.
                (c + egui::vec2(sx, sy) * (half - arm), egui::vec2(sx, sy) * arm)
            } else {
                (c + egui::vec2(sx, sy) * half, -egui::vec2(sx, sy) * arm)
            };
            p.line_segment([corner, corner + egui::vec2(back.x, 0.0)], ink);
            p.line_segment([corner, corner + egui::vec2(0.0, back.y)], ink);
        }
    }

    /// The keyboard key: a small keyboard drawn in it (keys and a space bar), lit while open.
    fn paint_keyboard_key(&self, p: &egui::Painter, rect: egui::Rect, tk: &Tokens) {
        let on = self.keyboard_on;
        p.rect(rect, tk.radius, if on { tk.accent } else { tk.field }, Stroke::new(1.0, tk.field_border), egui::StrokeKind::Inside);
        let ink = if on { tk.primary_text } else { tk.text };
        let body = egui::Rect::from_center_size(rect.center(), egui::vec2(30.0, 18.0).min(rect.size() - egui::vec2(6.0, 6.0)));
        p.rect_stroke(body, 2.0, Stroke::new(1.2, ink), egui::StrokeKind::Inside);
        let (cols, key) = (5, body.width() / 7.0);
        for row in 0..2 {
            for col in 0..cols {
                let x = body.left() + key * (1.0 + col as f32 * 1.0) + key / 2.0;
                let y = body.top() + body.height() * (0.3 + row as f32 * 0.22);
                p.circle_filled(egui::pos2(x, y), 1.2, ink);
            }
        }
        let bar = body.bottom() - body.height() * 0.24;
        p.line_segment([egui::pos2(body.center().x - key * 1.5, bar), egui::pos2(body.center().x + key * 1.5, bar)], Stroke::new(1.5, ink));
    }

    /// The settings window, when open (after the app, so it sits on top).
    pub fn settings(&mut self, ctx: &egui::Context, tk: &Tokens) {
        let mut open = self.shared.borrow().settings_open;
        if !open {
            return;
        }
        let before = self.shared.borrow().config.clone();
        let mut c = before.clone();
        egui::Window::new("Shortcut Pad")
            .open(&mut open)
            .collapsible(false)
            .resizable(true)
            .vscroll(true)
            .pivot(Align2::CENTER_CENTER)
            .default_pos(ctx.content_rect().center())
            .show(ctx, |ui| {
                ui.checkbox(&mut c.palm_rejection, "Ignore palm touches near the pen");
                ui.horizontal(|ui| {
                    ui.label("One finger on canvas");
                    ui.radio_value(&mut c.finger_mode,config::FingerMode::Draw,"Draw");
                    ui.radio_value(&mut c.finger_mode,config::FingerMode::Pan,"Pan");
                    ui.radio_value(&mut c.finger_mode,config::FingerMode::Ignore,"Ignore");
                });
                ui.checkbox(&mut c.enabled, "Show the Shortcut Pad");
                ui.horizontal(|ui| {
                    ui.label("Side:");
                    ui.radio_value(&mut c.side, Side::Left, "Left");
                    ui.radio_value(&mut c.side, Side::Right, "Right");
                });
                ui.separator();
                ui.horizontal(|ui| {
                    ui.label("Number of keys:");
                    let mut n = c.keys.len();
                    if ui.add(egui::Slider::new(&mut n, MIN_KEYS..=MAX_KEYS)).changed() {
                        c.set_key_count(n);
                    }
                    ui.label(format!("{} above the wheel, {} below", n.div_ceil(2), n / 2));
                });
                ui.label("Keys (top to bottom). A modifier on its own, such as Alt, is held while the key is touched. Double-tap a key to lock it down; tap it again to let go.");
                let above = c.keys.len().div_ceil(2);
                egui::ScrollArea::vertical().max_height(320.0).show(ui, |ui| {
                    egui::Grid::new("pad_keys").num_columns(5).spacing([8.0, 6.0]).show(ui, |ui| {
                        ui.label("");
                        ui.label("Label");
                        ui.label("Color");
                        ui.label("Preset");
                        ui.label("Shortcut");
                        ui.end_row();
                        for (i, key) in c.keys.iter_mut().enumerate() {
                            ui.label(format!("Key {}", i + 1)).on_hover_text(if i < above { "Above the wheel" } else { "Below the wheel" });
                            ui.add_sized([84.0, 24.0], egui::TextEdit::singleline(&mut key.label).char_limit(8));
                            color_choice(ui, tk, i, &mut key.color);
                            craft_ui::ComboBox::from_id_salt(("pad_preset", i)).selected_text("Choose…").width(110.0).show_ui(ui, |ui| {
                                for (name, label, shortcut) in config::PRESETS {
                                    if ui.selectable_label(key.shortcut == *shortcut, format!("{name}  ({shortcut})")).clicked() {
                                        key.label = (*label).into();
                                        key.shortcut = (*shortcut).into();
                                    }
                                }
                                if ui.selectable_label(key.shortcut.is_empty(), "Nothing").clicked() {
                                    key.label.clear();
                                    key.shortcut.clear();
                                }
                            });
                            ui.vertical(|ui| {
                                ui.add_sized([130.0, 24.0], egui::TextEdit::singleline(&mut key.shortcut).hint_text("e.g. Ctrl+Z"));
                                if let Err(e) = config::parse(&key.shortcut) {
                                    ui.colored_label(tk.danger, e);
                                }
                            });
                            ui.end_row();
                        }
                    });
                });
                ui.separator();
                ui.label("Wheel: tapping its centre switches between");
                for m in WheelMode::ALL {
                    let mut on = c.wheel_modes.contains(&m);
                    let last = on && c.wheel_modes.len() == 1;
                    if ui.add_enabled(!last, egui::Checkbox::new(&mut on, m.label())).changed() {
                        if on {
                            // Keep the configured order: the order of ALL.
                            c.wheel_modes.push(m);
                            c.wheel_modes.sort_by_key(|x| WheelMode::ALL.iter().position(|a| a == x));
                        } else {
                            c.wheel_modes.retain(|x| *x != m);
                        }
                    }
                }
                ui.checkbox(&mut c.enlarge, "Open a large ring when the wheel is pressed");
                ui.add_enabled(c.enlarge, egui::Slider::new(&mut c.wheel_size, WHEEL_SIZE_RANGE).text("Ring size").suffix(" pt").integer());
                ui.add(egui::Slider::new(&mut c.sensitivity, SENSITIVITY_RANGE).logarithmic(true).text("Sensitivity").suffix("×"))
                    .on_hover_text("At 1×, a quarter turn doubles the zoom, a third of a turn doubles the brush size");
                ui.separator();
                if ui.button("Restore Defaults").clicked() {
                    c = PadConfig::default();
                }
            });
        let mut s = self.shared.borrow_mut();
        s.settings_open = open;
        if c != before {
            menus::artcraft_pad_set_visible(c.enabled);
            menus::artcraft_pad_set_left(c.side == Side::Left);
            s.config = c.sanitized();
            s.save();
        }
    }

    pub fn take_screen_tap(&mut self) -> bool { std::mem::take(&mut self.screen_tapped) }
    pub fn take_keyboard_tap(&mut self) -> bool { std::mem::take(&mut self.keyboard_tapped) }
}

fn key_event(key: Key, pressed: bool) -> Event {
    Event::Key { key, physical_key: Some(key), pressed, repeat: false, modifiers: Modifiers::NONE }
}

/// Where the full screen key is in its cycle.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ScreenStep {
    Normal,
    /// Full screen with the tool and options bars kept (the first step).
    WithToolbar,
    Full,
}

impl ScreenStep {
    fn of(app: &PhotocraftApp) -> Self {
        match app.ui.view.screen_mode.as_str() {
            "standard" => ScreenStep::Normal,
            "fullScreenWithMenuBar" => ScreenStep::WithToolbar,
            _ => ScreenStep::Full,
        }
    }

    /// What a tap goes to.
    fn next(self) -> Self {
        match self {
            ScreenStep::Normal => ScreenStep::WithToolbar,
            ScreenStep::WithToolbar => ScreenStep::Full,
            ScreenStep::Full => ScreenStep::Normal,
        }
    }
}

/// Dark or light text, whichever reads on `fill`.
fn contrasting_text(fill: egui::Color32) -> egui::Color32 {
    let luma = 0.299 * fill.r() as f32 + 0.587 * fill.g() as f32 + 0.114 * fill.b() as f32;
    if luma > 150.0 { egui::Color32::from_rgb(20, 20, 20) } else { egui::Color32::WHITE }
}

/// A swatch for painting a colour choice (the theme's key colour when `None`).
fn swatch(ui: &mut egui::Ui, tk: &Tokens, color: Option<[u8; 3]>) {
    let (rect, _) = ui.allocate_exact_size(egui::vec2(14.0, 14.0), egui::Sense::hover());
    let fill = color.map_or(tk.field, |[r, g, b]| egui::Color32::from_rgb(r, g, b));
    ui.painter().rect(rect, 3.0, fill, Stroke::new(1.0, tk.field_border), egui::StrokeKind::Inside);
}

/// A key's colour: the theme's, one of [`config::KEY_COLORS`], or any other picked.
fn color_choice(ui: &mut egui::Ui, tk: &Tokens, i: usize, color: &mut Option<[u8; 3]>) {
    ui.horizontal(|ui| {
        let name = match color {
            None => "Default",
            Some(c) => config::KEY_COLORS.iter().find(|(_, k)| k == c).map_or("Custom", |(n, _)| *n),
        };
        craft_ui::ComboBox::from_id_salt(("pad_color", i)).selected_text(name).width(84.0).show_ui(ui, |ui| {
            let mut row = |ui: &mut egui::Ui, label: &str, value: Option<[u8; 3]>| {
                let r = ui.horizontal(|ui| {
                    swatch(ui, tk, value);
                    ui.selectable_label(*color == value, label)
                });
                if r.inner.clicked() {
                    *color = value;
                }
            };
            row(ui, "Default", None);
            for (n, c) in config::KEY_COLORS {
                row(ui, n, Some(*c));
            }
        });
        // Any other colour: the swatch opens a picker.
        let mut rgb = color.unwrap_or([128, 128, 128]);
        if egui::widgets::color_picker::color_edit_button_srgb(ui, &mut rgb).changed() {
            *color = Some(rgb);
        }
    });
}

fn modifier_keys(c: Chord) -> Vec<Key> {
    [(c.ctrl, Key::ControlLeft), (c.alt, Key::AltLeft), (c.shift, Key::ShiftLeft)].into_iter().filter(|(on, _)| *on).map(|(_, k)| k).collect()
}

/// The key events of pressing a chord: its modifiers, then its key.
pub fn press(c: Chord) -> Vec<Event> {
    let mut v: Vec<Event> = modifier_keys(c).into_iter().map(|k| key_event(k, true)).collect();
    v.extend(c.key.map(|k| key_event(k, true)));
    v
}

/// The key events of releasing a chord: its key, then its modifiers.
pub fn release(c: Chord) -> Vec<Event> {
    let mut v: Vec<Event> = c.key.map(|k| key_event(k, false)).into_iter().collect();
    v.extend(modifier_keys(c).into_iter().rev().map(|k| key_event(k, false)));
    v
}
