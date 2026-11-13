//! GridCraft Android wheel: the approved PhotoCraft Default radial layout,
//! with Gc deep-green/lime branding and guarded spreadsheet-only commands.
//! Wheel pointers are captured in raw_input_hook BEFORE the workbook sees them.
//! The preview is deliberately non-interactive and is rendered at exact size.
use eframe::egui::{self, Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, pos2, vec2};
use gridcraft_ui_egui::SheetApp;
use std::{path::PathBuf, time::{Duration, Instant}};

const R: f32 = 128.0;
const INNER: f32 = 47.0;
const SIZE: f32 = 312.0;
const WHEEL_ENLARGEMENT: f32 = 1.12; // ~12% larger than Android.1 at every saved slider setting.
const WAIT: Duration = Duration::from_millis(400);
const LABELS: [&str; 16] = [
    "Select", "Format", "Function", "Fill Down",
    "Copy", "Paste", "Undo", "Redo",
    "Prev Sheet", "Next Sheet", "Zoom +", "Zoom -",
    "Save", "Clear", "Go To", "New Sheet",
];
const DEFAULT: [usize; 8] = [0, 1, 2, 3, 4, 5, 6, 7];
/// DeckCraft-inspired white-outline pictograms, not the previous mixed toolkit
/// icons. Every slot is drawn using one stroke weight and matching dimensions.
// GridCraft Android.5: stable return-arrow geometry, matched exactly for
// Undo/Redo by horizontal mirroring. No self-intersections, extra tail,
// cursor characters or mismatched icon sets.
fn deck_style_curved_arrow(p: &egui::Painter, rect: egui::Rect, redo: bool) {
    let scale = rect.width() / 24.0;
    let c = rect.center();
    let stroke = Stroke::new(2.15 * scale, Color32::WHITE);
    // Mirror the same geometry, so Undo clearly points left and Redo right.
    let mirror = if redo { -1.0 } else { 1.0 };
    let pt = |x: f32, y: f32| c + vec2(x * mirror, y) * scale;
    // A quarter-round return shaft ending in a straight horizontal head.
    let mut path = Vec::with_capacity(17);
    for i in 0..=16 {
        let t = i as f32 / 16.0;
        let u = 1.0-t;
        // Cubic: from right/bottom to left/top, with a rounded bend.
        let x = u*u*u*8.0 + 3.0*u*u*t*8.0 + 3.0*u*t*t*4.0 + t*t*t*(-8.0);
        let y = u*u*u*8.5 + 3.0*u*u*t*(-1.5) + 3.0*u*t*t*(-5.5) + t*t*t*(-5.5);
        path.push(pt(x,y));
    }
    p.add(Shape::line(path, stroke));
    p.add(Shape::line(vec![pt(-3.0,-10.0),pt(-8.0,-5.5),pt(-3.0,-1.0)],stroke));
}
/// No multicolour filled toolbar art or platform-dependent emoji icon glyphs.
fn draw_icon(p: &egui::Painter, rect: egui::Rect, action: usize) {
    let centre = rect.center();
    let scale = rect.width() / 24.0;
    let pt = |x: f32, y: f32| centre + vec2(x, y) * scale;
    let stroke = Stroke::new(2.0 * scale, Color32::WHITE);
    let line = |coords: &[(f32, f32)]| {
        p.add(Shape::line(
            coords.iter().map(|&(x,y)| pt(x,y)).collect::<Vec<_>>(), stroke));
    };
    let seg = |a: (f32,f32), b: (f32,f32)| {
        p.line_segment([pt(a.0,a.1),pt(b.0,b.1)],stroke);
    };
    let box_at = |x1:f32,y1:f32,x2:f32,y2:f32| {
        p.rect_stroke(egui::Rect::from_min_max(pt(x1,y1),pt(x2,y2)),
            2.0*scale,stroke,StrokeKind::Inside);
    };
    match action {
        0 => { // Select: arrow/cursor; same outline weight as other slots.
            line(&[(-7.0,-10.0),(-7.0,7.0),(-2.0,3.0),(2.0,11.0),
                (5.0,9.0),(1.0,1.0),(8.0,1.0),(-7.0,-10.0)]);
        }
        1 => { // Format cells: bordered 2x2 worksheet.
            box_at(-9.0,-9.0,9.0,9.0);
            seg((-9.0,-1.0),(9.0,-1.0));
            seg((0.0,-9.0),(0.0,9.0));
        }
        2 => { // Standard spreadsheet function mark: clean, readable "fx".
            p.text(centre, egui::Align2::CENTER_CENTER, "fx",
                FontId::proportional(19.0 * scale), Color32::WHITE);
        }
        3 => { // Fill Down: two outlined cells and down arrow.
            box_at(-9.0,-9.0,3.0,9.0);
            seg((-9.0,0.0),(3.0,0.0));
            seg((8.0,-7.0),(8.0,7.0));
            line(&[(4.0,3.0),(8.0,7.0),(12.0,3.0)]);
        }
        4 => { // Copy.
            box_at(-8.0,-9.0,4.0,4.0);
            box_at(-3.0,-4.0,9.0,9.0);
        }
        5 => { // Paste: clipboard.
            box_at(-8.0,-7.0,8.0,10.0);
            box_at(-4.0,-10.0,4.0,-5.0);
            seg((-4.0,0.0),(4.0,0.0));
            seg((-4.0,5.0),(3.0,5.0));
        }
        6 => deck_style_curved_arrow(p, rect, false), // Undo: left.
        7 => deck_style_curved_arrow(p, rect, true),  // Redo: right.
        8 => { // Previous sheet.
            box_at(-2.0,-9.0,9.0,9.0);
            line(&[(-3.0,-5.0),(-9.0,0.0),(-3.0,5.0)]);
        }
        9 => { // Next sheet.
            box_at(-9.0,-9.0,2.0,9.0);
            line(&[(3.0,-5.0),(9.0,0.0),(3.0,5.0)]);
        }
        10 | 11 => { // Zoom +/-.
            p.circle_stroke(pt(-2.0,-2.0),6.5*scale,stroke);
            seg((3.0,3.0),(10.0,10.0));
            seg((-5.5,-2.0),(1.5,-2.0));
            if action==10 { seg((-2.0,-5.5),(-2.0,1.5)); }
        }
        12 => { // Save.
            box_at(-9.0,-10.0,9.0,10.0);
            box_at(-5.0,2.0,5.0,10.0);
            seg((-4.0,-6.0),(3.0,-6.0));
        }
        13 => { // Clear contents: eraser outline.
            line(&[(-9.0,2.0),(-1.0,-8.0),(9.0,0.0),(2.0,9.0),
                (-4.0,9.0),(-9.0,2.0)]);
            seg((-3.0,-4.0),(5.0,3.0));
        }
        14 => { // Go To: crosshair.
            p.circle_stroke(centre,7.0*scale,stroke);
            p.circle_stroke(centre,2.0*scale,stroke);
            for (a,b) in [((-11.0,0.0),(-7.0,0.0)),((7.0,0.0),(11.0,0.0)),
                ((0.0,-11.0),(0.0,-7.0)),((0.0,7.0),(0.0,11.0))] { seg(a,b); }
        }
        _ => { // New sheet.
            box_at(-9.0,-9.0,5.0,9.0);
            seg((-9.0,-2.0),(5.0,-2.0));
            seg((-2.0,-9.0),(-2.0,9.0));
            seg((5.0,5.0),(12.0,5.0));
            seg((8.5,1.5),(8.5,8.5));
        }
    }
}
const DARK: Color32 = Color32::from_rgb(0, 104, 24);
const LIME: Color32 = Color32::from_rgb(171, 232, 128);
const BRIGHT: Color32 = Color32::from_rgb(110, 241, 79);

pub struct Wheel {
    pub enabled: bool,
    pub settings_open: bool,
    slots: [usize; 8],
    size_percent: f32,
    opacity_percent: f32,
    settings_path: Option<PathBuf>,
    open: bool,
    center: Option<Pos2>,
    preview_center: Option<Pos2>,
    hover: Option<Pos2>,
    last_stylus_hover: Option<Instant>,
    hover_blocked: bool,
    suppress_release: bool,
    single_wait: Option<(Instant, Option<Pos2>)>,
    pending_action: Option<usize>,
    opened_at: Instant,
}
impl Wheel {
    pub fn new() -> Self {
        // HOME is GridCraft's existing writable Android private directory,
        // also used for the imported-font cache.
        let settings_path = std::env::var_os("HOME")
            .map(PathBuf::from).map(|p| p.join("gridcraft-stylus-wheel-v1"));
        let mut result = Self {
            enabled: false, settings_open: false, slots: DEFAULT,
            size_percent: 100.0, opacity_percent: 85.0, settings_path,
            open: false, center: None, preview_center: None, hover: None,
            last_stylus_hover: None,
            hover_blocked: false,
            suppress_release: false, single_wait: None, pending_action: None,
            opened_at: Instant::now(),
        };
        if let Some(raw) = result.settings_path.as_ref()
            .and_then(|p| std::fs::read_to_string(p).ok())
        {
            let fields: Vec<_> = raw.trim().split('|').collect();
            if fields.len() == 5 && fields[0] == "v1" {
                result.enabled = fields[1] == "1";
                let chosen: Vec<usize> = fields[2].split(',')
                    .filter_map(|s| s.parse().ok()).collect();
                if chosen.len() == 8 && chosen.iter().all(|n| *n < LABELS.len())
                    && chosen.iter().enumerate().all(|(i,n)| !chosen[..i].contains(n)) {
                    result.slots.copy_from_slice(&chosen);
                }
                if let Ok(v) = fields[3].parse::<f32>() {
                    if v.is_finite() { result.size_percent = v.clamp(75.0, 125.0); }
                }
                if let Ok(v) = fields[4].parse::<f32>() {
                    if v.is_finite() { result.opacity_percent = v.clamp(60.0, 100.0); }
                }
            }
        }
        result
    }
    fn persist(&self) {
        let Some(path) = &self.settings_path else { return; };
        let data = format!("v1|{}|{}|{:.0}|{:.0}", u8::from(self.enabled),
            self.slots.iter().map(usize::to_string).collect::<Vec<_>>().join(","),
            self.size_percent, self.opacity_percent);
        if let Err(e) = std::fs::write(path, data) {
            log::warn!("GridCraft wheel settings: {e}");
        }
    }
    fn scale(&self) -> f32 { self.size_percent / 100.0 * WHEEL_ENLARGEMENT }
    fn hit_at(&self, at: Pos2, center: Pos2) -> Option<usize> {
        let delta = at - center;
        let distance = delta.length();
        if distance < INNER*self.scale() || distance > (R+8.0)*self.scale() {
            return None;
        }
        Some((((delta.y.atan2(delta.x).to_degrees()+112.5)
            .rem_euclid(360.0)/45.0).floor() as usize).min(7))
    }
    fn hit(&self, at: Pos2) -> Option<usize> {
        self.hit_at(at, self.center?)
    }
    fn input_center(&self) -> Option<Pos2> {
        if self.settings_open { self.preview_center }
        else if self.open { self.center }
        else { None }
    }
    fn pointer_inside(&self, at: Pos2) -> bool {
        self.input_center().is_some_and(|c|
            (at-c).length() <= (R+8.0)*self.scale())
    }
    fn position(&mut self, ctx: &Context, at: Option<Pos2>) {
        let content = ctx.content_rect();
        let size = SIZE * self.scale();
        let inset = size / 2.0 + 11.0;
        let at = at.unwrap_or(content.center());
        self.center = Some(pos2(
            at.x.clamp(content.min.x + inset, (content.max.x - inset).max(content.min.x + inset)),
            at.y.clamp(content.min.y + inset, (content.max.y - inset).max(content.min.y + inset)),
        ));
        self.open = true;
        self.opened_at = Instant::now();
        ctx.request_repaint();
    }
    pub fn show_at_pointer(&mut self, ctx: &Context) {
        if !self.enabled { return; }
        self.single_wait = None;
        self.position(ctx, self.hover.or_else(|| ctx.input(|i| i.pointer.hover_pos())));
    }
    pub fn signal(&mut self, code: &str, ctx: &Context) {
        if !self.enabled || self.settings_open { return; }
        if code == "S" {
            if self.open { self.open = false; self.single_wait = None; }
            else { self.single_wait = Some((Instant::now(), self.hover)); }
        } else if code == "D" {
            // Double-press opens immediately; avoid destructive spreadsheet actions.
            self.single_wait = None;
            self.position(ctx, self.hover);
        }
        ctx.request_repaint_after(WAIT);
    }
    pub fn capture(&mut self, ctx: &Context, raw: &mut RawInput) {
        if !self.enabled { return; }
        // Guard only the actual wheel area (or canvas-side live preview).
        // GridCraft still receives input outside it, including the dialog.
        let mut keep = Vec::with_capacity(raw.events.len()+1);
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerMoved(p) => {
                    if !self.last_stylus_hover.is_some_and(|t|
                        t.elapsed() < Duration::from_millis(300)) {
                        self.hover = Some(p);
                    }
                    if self.pointer_inside(p) {
                        if !self.hover_blocked {
                            keep.push(egui::Event::PointerGone);
                            self.hover_blocked = true;
                        }
                    } else {
                        self.hover_blocked = false;
                        keep.push(egui::Event::PointerMoved(p));
                    }
                }
                egui::Event::Touch {pos, ..} if self.pointer_inside(pos) => {
                    // Pen/touch on the floating preview must never select a cell.
                }
                egui::Event::PointerButton {pos, pressed: true, ..}
                    if self.pointer_inside(pos) => {
                    if !self.settings_open && self.open {
                        self.pending_action = self.hit(pos).map(|i| self.slots[i]);
                        self.open = false;
                    }
                    self.suppress_release = true;
                    self.hover_blocked = false;
                    ctx.request_repaint();
                }
                egui::Event::PointerButton {pressed: false, ..}
                    if self.suppress_release => {
                    self.suppress_release = false;
                }
                egui::Event::Key {key: egui::Key::Escape, pressed: true, ..}
                    if self.open && !self.settings_open => {
                    self.open = false;
                }
                other => keep.push(other),
            }
        }
        raw.events = keep;
        if let Some((when, at)) = self.single_wait {
            if when.elapsed() >= WAIT {
                self.single_wait = None;
                self.position(ctx, at.or(self.hover));
            } else { ctx.request_repaint_after(WAIT.saturating_sub(when.elapsed())); }
        }
        // Wheel-owned hover is erased *from workbook input*, not from the
        // stylus coordinate used to paint the highlight and cursor overlay.
        if !self.hover_blocked && self.hover.is_some_and(|p| self.pointer_inside(p)) {
            raw.events.push(egui::Event::PointerGone);
            self.hover_blocked = true;
        }
    }
    /// MotionEvent HOVER_ENTER/MOVE/EXIT from the real Android stylus.
    /// Java reports pixel coordinates; egui works in logical points.
    /// Updates only the floating wheel and NEVER injects a workbook click.
    pub fn stylus_hover(&mut self, report: &str, ctx: &Context) {
        if !self.enabled { return; }
        if report == "E" {
            self.hover = None;
            self.last_stylus_hover = None;
            if self.open { ctx.request_repaint(); }
            return;
        }
        let Some(data) = report.strip_prefix("M:") else { return; };
        let Some((x,y)) = data.split_once(',') else { return; };
        let Ok(x) = x.parse::<f32>() else { return; };
        let Ok(y) = y.parse::<f32>() else { return; };
        if !x.is_finite() || !y.is_finite() { return; }
        let ppp = ctx.pixels_per_point().max(0.5);
        let point = pos2(x / ppp, y / ppp);
        if !ctx.content_rect().expand(24.0).contains(point) { return; }
        self.hover = Some(point);
        self.last_stylus_hover = Some(Instant::now());
        // This also updates wheel highlighting without a tap: stylus
        // HOVER_ENTER / MOVE, unlike PointerButton, is never a selection.
        if self.open { ctx.request_repaint(); }
    }

    pub fn menu(&mut self, ctx: &Context) -> bool {
        let action_id = Id::new("gridcraft.android.wheel.menu");
        let action = ctx.data(|d| d.get_temp::<String>(action_id)).unwrap_or_default();
        if action.is_empty() { return false; }
        ctx.data_mut(|d| d.insert_temp(action_id, String::new()));
        match action.as_str() {
            "toggle" => {
                self.enabled = !self.enabled;
                self.open = false;
                self.single_wait = None;
                self.last_stylus_hover = None;
                self.persist();
                true
            }
            "settings" => { self.settings_open = true; self.open = false; false }
            "show" => { self.show_at_pointer(ctx); false }
            _ => false,
        }
    }
    fn apply(&mut self, app: &mut SheetApp) {
        let Some(index) = self.pending_action.take() else { return };
        match index {
            6 | 7 => {
                // Same quiet history semantics as hardware Ctrl+Z/Ctrl+Y.
                // Commit the active cell before asking the engine to undo.
                if !app.commit_edit(0, 0, false, false) { return; }
                let command = if index == 6 { "edit.undo" } else { "edit.redo" };
                if let Err(e) = app.run(command, serde_json::json!({})) {
                    if !e.contains("nothing to undo") && !e.contains("nothing to redo")
                        && !e.contains("is not available right now") {
                        log::warn!("GridCraft stylus wheel {command}: {e}");
                    }
                }
            }
            1 => app.open_dialog("formatCells", serde_json::json!({})),
            2 => app.open_dialog("insertFunction", serde_json::json!({})),
            10 | 11 => {
                let z = app.session.active()
                    .and_then(|d| d.wb.active().map(|s| s.zoom)).unwrap_or(100);
                let delta = if index == 10 { 10 } else { -10 };
                app.run_or_alert("view.zoom",
                    serde_json::json!({"percent": (i32::from(z) + delta).clamp(10,400)}));
            }
            14 => app.open_dialog("goTo", serde_json::json!({})),
            _ => {
                let command = match index {
                    0 => "edit.selectAll", 3 => "edit.fillDown", 4 => "edit.copy",
                    5 => "edit.paste", 6 => "edit.undo", 7 => "edit.redo",
                    8 => "sheet.previous", 9 => "sheet.next", 12 => "file.save",
                    13 => "edit.clearContents", _ => "sheet.insert",
                };
                app.run_or_alert(command, serde_json::json!({}));
            }
        }
    }
    // Native egui slider themes previously rendered grey on this tablet.
    // Paint a local, high-contrast green slider without changing app themes.
    fn green_slider(ui: &mut Ui, name: &str, value: &mut f32,
        min: f32, max: f32) -> bool {
        let mut changed = false;
        ui.horizontal(|ui| {
            ui.label(name);
            let remaining = (ui.available_width()-61.0).clamp(100.0, 190.0);
            let (rect, response) = ui.allocate_exact_size(
                vec2(remaining, 26.0), Sense::click_and_drag());
            if (response.clicked() || response.dragged())
                && let Some(at) = response.interact_pointer_pos() {
                let fraction = ((at.x-rect.left()-7.0)/
                    (rect.width()-14.0).max(1.0)).clamp(0.0,1.0);
                let next = (min + fraction * (max-min)).round();
                if (*value-next).abs()>0.1 { *value=next; changed=true; }
            }
            let p = ui.painter_at(rect);
            let begin = rect.left()+7.0;
            let end = rect.right()-7.0;
            let fraction = ((*value-min)/(max-min)).clamp(0.0,1.0);
            let x = begin + (end-begin)*fraction;
            let y = rect.center().y;
            p.line_segment([pos2(begin,y),pos2(end,y)],
                Stroke::new(5.0,Color32::from_rgb(70,75,71)));
            p.line_segment([pos2(begin,y),pos2(x,y)],
                Stroke::new(5.0,Color32::from_rgb(61,190,75)));
            p.circle_filled(pos2(x,y),8.0,LIME);
            p.circle_stroke(pos2(x,y),8.0,
                Stroke::new(1.2,Color32::from_rgb(7,86,24)));
            ui.label(format!("{:.0}%", *value));
        });
        changed
    }
    fn customise(&mut self, ctx: &Context) {
        if !self.settings_open { return; }
        self.open = false;
        self.single_wait = None;
        let mut window_open = self.settings_open;
        let mut dirty = false;
        let response = egui::Window::new("Stylus Wheel — Default")
            .id(Id::new("gc-wheel-settings"))
            .open(&mut window_open).resizable(false).collapsible(false)
            .default_width(322.0).show(ctx, |ui| {
                ui.label("GridCraft Default • 8 configurable segments");
                ui.separator();
                dirty |= Self::green_slider(ui,"Wheel size",
                    &mut self.size_percent,75.0,125.0);
                dirty |= Self::green_slider(ui,"Opacity",
                    &mut self.opacity_percent,60.0,100.0);
                ui.small("Changes update the live wheel on the canvas.");
                ui.separator();
                for slot in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", slot + 1));
                        let mut chosen = self.slots[slot];
                        egui::ComboBox::from_id_salt(("gc-wheel-slot",slot))
                            .width(175.0).selected_text(LABELS[chosen]).show_ui(ui, |ui| {
                                for i in 0..LABELS.len() {
                                    ui.selectable_value(&mut chosen, i, LABELS[i]);
                                }
                            });
                        if chosen != self.slots[slot] {
                            if let Some(old) = self.slots.iter().position(|n| *n == chosen) {
                                self.slots[old] = self.slots[slot];
                            }
                            self.slots[slot] = chosen;
                            dirty = true;
                        }
                    });
                }
                ui.separator();
                if ui.button("Reset to Default").clicked() {
                    self.slots = DEFAULT;
                    self.size_percent = 100.0;
                    self.opacity_percent = 85.0;
                    dirty = true;
                }
                // Temporary acceptance-check indicator: tells the tester
                // whether real Java stylus-hover samples reach the native app.
                let incoming = self.last_stylus_hover.is_some_and(
                    |at| at.elapsed() < Duration::from_secs(3));
                let message = if !self.enabled {
                    "Stylus hover: enable wheel in Gc menu"
                } else if incoming {
                    "Stylus hover: signal detected"
                } else {
                    "Stylus hover: move Magic-Pencil above the screen"
                };
                ui.small(message);
                ui.small("Pen side-button: single to open • double to open immediately.");
            });
        self.settings_open = window_open;
        if !self.settings_open { self.preview_center = None; }
        if dirty { self.persist(); ctx.request_repaint(); }
        if let Some(response) = response {
            let rect = response.response.rect;
            let screen = ctx.content_rect();
            let size = SIZE * self.scale();
            let margin = 18.0;
            let on_right = screen.right() - rect.right() >= size + margin * 2.0;
            let on_left = rect.left() - screen.left() >= size + margin * 2.0;
            let x = if on_right { (rect.right()+screen.right())/2.0 }
                else if on_left { (rect.left()+screen.left())/2.0 }
                else { screen.center().x };
            let at = pos2(
                x.clamp(screen.left()+size/2.0, (screen.right()-size/2.0).max(screen.left()+size/2.0)),
                rect.center().y.clamp(screen.top()+size/2.0, (screen.bottom()-size/2.0).max(screen.top()+size/2.0)),
            );
            self.preview_center = Some(at);
            let highlight = self.hover.and_then(|p| self.hit_at(p,at));
            egui::Area::new(Id::new("gc-wheel-actual-preview"))
                .order(Order::Foreground).interactable(false)
                .fixed_pos(at-vec2(size/2.0,size/2.0))
                .show(ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(vec2(size,size), Sense::hover());
                    self.paint(ui, rect, self.scale(), highlight);
                });
        }
    }
    pub fn render(&mut self, ctx: &Context, app: &mut SheetApp) {
        self.apply(app);
        self.customise(ctx);
        self.paint_stylus_pointer(ctx);
        if !self.enabled || !self.open || self.settings_open { return; }
        let Some(at) = self.center else { return; };
        let t = (self.opened_at.elapsed().as_secs_f32()/0.18).min(1.0);
        if t < 1.0 { ctx.request_repaint(); }
        let scale = self.scale() * (0.86+0.14*t);
        let size = SIZE * scale;
        let highlight = self.hover.and_then(|p| self.hit(p));
        egui::Area::new(Id::new("gc-wheel-visible"))
            .order(Order::Foreground).interactable(false)
            .fixed_pos(at-vec2(size/2.0,size/2.0))
            .show(ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(size,size), Sense::hover());
                self.paint(ui, rect, scale, highlight);
            });
        ctx.request_repaint_after(Duration::from_millis(100));
    }
    /// Native HONOR pen-hover pointer: visual only, never an egui pointer
    /// event. The cursor stays visible over the canvas and wheel independently
    /// of mouse/trackpad position. No events are synthesised.
    fn paint_stylus_pointer(&self, ctx: &Context) {
        if !self.enabled { return; }
        let Some(last) = self.last_stylus_hover else { return };
        if last.elapsed() > Duration::from_secs(4) { return; }
        let Some(at) = self.hover else { return };
        if !ctx.content_rect().contains(at) { return; }
        let pointer_size = 28.0;
        egui::Area::new(Id::new("gc-visible-stylus-cursor"))
            .order(Order::Tooltip).interactable(false)
            .fixed_pos(at-vec2(3.0,3.0))
            .show(ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(
                    vec2(pointer_size,pointer_size),Sense::hover());
                let painter = ui.painter_at(rect);
                let base = rect.min;
                let tip = base + vec2(3.0,3.0);
                painter.add(Shape::convex_polygon(vec![
                    tip,tip+vec2(2.0,19.0),tip+vec2(7.0,14.0),
                    tip+vec2(11.0,23.0),tip+vec2(14.0,21.0),
                    tip+vec2(10.0,12.0),tip+vec2(17.0,12.0),
                ],Color32::from_rgb(250,252,248),
                    Stroke::new(1.3,DARK)));
                painter.circle_stroke(tip+vec2(1.0,1.0),5.0,
                    Stroke::new(1.1,LIME));
            });
        ctx.request_repaint_after(Duration::from_millis(70));
    }

    fn gc_icon(ctx: &Context) -> egui::TextureHandle {
        let id = Id::new("gridcraft-wheel-approved-user-gc");
        if let Some(texture) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(id)) {
            return texture;
        }
        // Same protected Gc launcher asset as the Android title bar, rendered
        // into a round transparent 128px RGBA by the isolated build overlay.
        const PIXELS: &[u8] = include_bytes!("gridcraft-wheel-gc.rgba");
        let image = egui::ColorImage::from_rgba_unmultiplied([128, 128], PIXELS);
        let texture = ctx.load_texture("gridcraft-wheel-gc-mark", image, egui::TextureOptions::LINEAR);
        ctx.data_mut(|d| d.insert_temp(id, texture.clone()));
        texture
    }
    fn paint(&self, ui: &mut Ui, rect: egui::Rect, scale: f32, highlighted: Option<usize>) {
        let c = rect.center();
        let painter = ui.painter_at(rect);
        // Twelve soft, tightly feathered layers: PhotoCraft's owner-approved shadow.
        for i in 0..12 {
            let spread = (12.0-i as f32*0.82)*scale;
            let alpha = (3.0 + i as f32*0.7) as u8;
            painter.circle_filled(c+vec2(0.8,2.0)*scale, R*scale+spread,
                Color32::from_rgba_unmultiplied(0,0,0,alpha));
        }
        painter.circle_filled(c,R*scale,Color32::from_rgba_unmultiplied(
            15,24,20,(244.0*self.opacity_percent/100.0) as u8));
        for i in 0..8 {
            let deg = -90.0 + i as f32 * 45.0;
            let a = (deg-22.0).to_radians();
            let b = (deg+22.0).to_radians();
            let mut vertices = vec![c];
            for n in 0..=16 {
                let rad = a+(b-a)*n as f32/16.0;
                vertices.push(c+vec2(rad.cos(),rad.sin())*R*scale);
            }
            let active = highlighted == Some(i);
            // PhotoCraft reference: alternating graphite greys, NOT green
            // segments. Gc green is reserved for hover, centre and rim.
            let color = if active { Color32::from_rgb(20, 115, 40) }
                else if i % 2 == 0 { Color32::from_rgb(62, 63, 65) }
                else { Color32::from_rgb(46, 47, 49) };
            let color = color.gamma_multiply(self.opacity_percent/100.0);
            painter.add(Shape::convex_polygon(vertices,color,Stroke::new(
                if active { 1.65 } else { 0.7 },
                if active { BRIGHT } else { Color32::from_gray(75) },
            )));
            let point = c+vec2(deg.to_radians().cos(),deg.to_radians().sin())*87.0*scale;
            let icon_box = egui::Rect::from_center_size(point-vec2(0.0,10.0)*scale,
                vec2(24.0,24.0)*scale);
            draw_icon(&painter,icon_box,self.slots[i]);
            painter.text(point+vec2(0.0,13.0)*scale,egui::Align2::CENTER_CENTER,
                LABELS[self.slots[i]],FontId::proportional(11.0*scale),Color32::WHITE);
        }
        // Owner-approved thin Gc-green stroke for the circular wheel.
        painter.circle_stroke(c,R*scale,Stroke::new(0.95*scale,LIME));
        painter.circle_filled(c,(INNER+2.0)*scale,DARK);
        painter.circle_stroke(c,(INNER+2.0)*scale,Stroke::new(1.3,LIME));
        // Exact artwork-inspired round centre: deep-green solid, lime Gc letters.
        // No imported square icon or duplicate Android adaptive mask.
        let gc_mark = Self::gc_icon(ui.ctx());
        painter.image(gc_mark.id(), egui::Rect::from_center_size(
            c-vec2(0.0,8.0)*scale, vec2(50.0,50.0)*scale),
            egui::Rect::from_min_max(pos2(0.0,0.0),pos2(1.0,1.0)), Color32::WHITE);
        painter.text(c+vec2(0.0,23.0)*scale,egui::Align2::CENTER_CENTER,
            highlighted.map(|i| LABELS[self.slots[i]]).unwrap_or("Default"),
            FontId::proportional(10.0*scale),Color32::WHITE);
    }
}
