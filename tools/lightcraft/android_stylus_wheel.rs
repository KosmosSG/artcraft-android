//! Android-only LightCraft stylus shortcut wheel.
//! Uses the same painter for the active wheel and the 1:1 customization preview.
//! The foreground Area owns the pointer hit region, so a hover over a wheel
//! segment never intentionally dispatches a canvas selection.
use egui::{Align2, Color32, FontId, Id, Order, Pos2, Sense, Stroke, Vec2};
use serde::{Deserialize, Serialize};

const CYAN: Color32 = Color32::from_rgb(0, 166, 235);
const NAVY: Color32 = Color32::from_rgb(0, 45, 69);
const OPEN: &str = "lightcraft.android.wheel.open";
const SETTINGS: &str = "lightcraft.android.wheel.settings";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum WheelAction {
    Edit, Crop, Mask, Remove, Picker, Zoom, Undo, Redo, Profiles,
    Versions, BeforeAfter, Fit, History, Compare,
}

impl WheelAction {
    const ALL: [Self; 14] = [
        Self::Edit, Self::Crop, Self::Mask, Self::Remove,
        Self::Picker, Self::Zoom, Self::Undo, Self::Redo,
        Self::Profiles, Self::Versions, Self::BeforeAfter,
        Self::Fit, Self::History, Self::Compare,
    ];

    fn label(self) -> &'static str {
        match self {
            Self::Edit => "Edit", Self::Crop => "Crop", Self::Mask => "Mask",
            Self::Remove => "Remove", Self::Picker => "Picker",
            Self::Zoom => "Zoom", Self::Undo => "Undo", Self::Redo => "Redo",
            Self::Profiles => "Profiles", Self::Versions => "Versions",
            Self::BeforeAfter => "Before/After", Self::Fit => "Fit",
            Self::History => "History", Self::Compare => "Compare",
        }
    }

    fn symbol(self) -> &'static str {
        match self {
            Self::Edit => "✦", Self::Crop => "⌗", Self::Mask => "◉",
            Self::Remove => "✕", Self::Picker => "⌖", Self::Zoom => "⊕",
            Self::Undo => "↶", Self::Redo => "↷", Self::Profiles => "◈",
            Self::Versions => "▤", Self::BeforeAfter => "◐",
            Self::Fit => "□", Self::History => "◷", Self::Compare => "◫",
        }
    }

    fn command(self) -> &'static str {
        match self {
            Self::Edit => "panel.edit",
            Self::Crop => "panel.crop",
            Self::Mask => "panel.masking",
            Self::Remove => "panel.remove",
            Self::Picker => "tool.wbPicker",
            Self::Zoom => "view.zoomToggle",
            Self::Undo => "edit.undo",
            Self::Redo => "edit.redo",
            Self::Profiles => "panel.profiles",
            Self::Versions => "panel.versions",
            Self::BeforeAfter => "view.beforeAfter",
            Self::Fit => "view.zoomFit",
            Self::History => "panel.activity",
            Self::Compare => "view.compare",
        }
    }
}

/// Saved with AppSettings in ui.json; every field has a backward-compatible default.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default, rename_all = "camelCase")]
pub struct WheelPrefs {
    pub enabled: bool,
    pub size_percent: f32,
    pub opacity_percent: f32,
    pub soft_shadow: bool,
    pub slots: [WheelAction; 8],
}

impl Default for WheelPrefs {
    fn default() -> Self {
        Self {
            enabled: true,
            size_percent: 100.0,
            opacity_percent: 90.0,
            soft_shadow: true,
            slots: [
                WheelAction::Edit, WheelAction::Crop, WheelAction::Mask,
                WheelAction::Remove, WheelAction::Picker, WheelAction::Zoom,
                WheelAction::Undo, WheelAction::Redo,
            ],
        }
    }
}

pub fn open_settings(ctx: &egui::Context) {
    ctx.data_mut(|d| d.insert_temp(Id::new(SETTINGS), true));
    ctx.request_repaint();
}

/// Shared pixel-exact renderer for both preview and live wheel; returns a chosen command.
fn paint_wheel(ui: &mut egui::Ui, prefs: &WheelPrefs, interactive: bool) -> Option<WheelAction> {
    let radius = 124.0 * (prefs.size_percent.clamp(70.0, 150.0) / 100.0);
    let diameter = radius * 2.0;
    let (rect, response) = ui.allocate_exact_size(Vec2::splat(diameter), if interactive { Sense::click() } else { Sense::hover() });
    let center = rect.center();
    let alpha = (prefs.opacity_percent.clamp(25.0, 100.0) / 100.0).clamp(0.25, 1.0);
    let painter = ui.painter_at(rect);
    let hub = radius * 0.39;
    let start = -std::f32::consts::FRAC_PI_2;
    let step = std::f32::consts::TAU / 8.0;
    let pointer = if interactive { response.hover_pos() } else { None };
    let hovered = pointer.and_then(|p| {
        let v = p - center;
        let r = v.length();
        if r <= hub || r > radius { return None; }
        let angle = (v.y.atan2(v.x) - start).rem_euclid(std::f32::consts::TAU);
        Some(((angle / step).floor() as usize).min(7))
    });

    if prefs.soft_shadow {
        for i in (0..5).rev() {
            painter.circle_filled(
                center + egui::vec2(1.0, 3.0 + i as f32 * 1.5),
                radius + 2.0 + i as f32 * 2.4,
                Color32::from_black_alpha((12 - i * 2) as u8),
            );
        }
    }
    for index in 0..8 {
        let a = start + step * index as f32;
        let b = a + step;
        let mut vertices = Vec::with_capacity(12);
        vertices.push(center);
        for n in 0..=9 {
            let theta = a + (b - a) * (n as f32 / 9.0);
            vertices.push(center + Vec2::angled(theta) * radius);
        }
        let active = hovered == Some(index);
        let fill = if active { Color32::from_rgb(3, 125, 189) } else { Color32::from_rgb(67, 72, 78) };
        painter.add(egui::Shape::convex_polygon(
            vertices,
            fill.gamma_multiply(alpha),
            Stroke::new(0.8, Color32::from_gray(100).gamma_multiply(alpha)),
        ));
        let mid = (a + b) * 0.5;
        let icon_pos = center + Vec2::angled(mid) * (radius * 0.72);
        let label_pos = center + Vec2::angled(mid) * (radius * 0.88);
        painter.text(icon_pos, Align2::CENTER_CENTER, prefs.slots[index].symbol(), FontId::proportional(21.0), Color32::WHITE);
        painter.text(label_pos, Align2::CENTER_CENTER, prefs.slots[index].label(), FontId::proportional(10.0), Color32::WHITE);
    }

    painter.circle_filled(center, hub + 2.0, CYAN.gamma_multiply(alpha));
    painter.circle_filled(center, hub, NAVY);
    // The user-approved Lc icon is the same PNG the top-left Android menu uses.
    let icon_size = hub * 1.02;
    let icon_rect = egui::Rect::from_center_size(center, Vec2::splat(icon_size));
    let image = egui::Image::from_bytes(
        "bytes://lightcraft/stylus-wheel/lc-menu.png",
        include_bytes!("menus/lc-menu.png"),
    ).fit_to_exact_size(Vec2::splat(icon_size));
    ui.put(icon_rect, image);

    if interactive && response.clicked() {
        let pos = response.interact_pointer_pos()?;
        let v = pos - center;
        let r = v.length();
        if r > hub && r <= radius {
            let angle = (v.y.atan2(v.x) - start).rem_euclid(std::f32::consts::TAU);
            return Some(prefs.slots[((angle / step).floor() as usize).min(7)]);
        }
    }
    None
}

fn run_action(app: &mut crate::LightcraftApp, ctx: &egui::Context, action: WheelAction) {
    if let Err(message) = app.run(action.command(), serde_json::Value::Null) {
        app.toast(ctx, message);
    }
}

pub fn show(app: &mut crate::LightcraftApp, ctx: &egui::Context) {
    // The customizer edits a local copy and writes back through AppSettings:
    // the existing LightCraft UI preference writer persists it in ui.json.
    let mut prefs = app.ui.settings.stylus_wheel.clone();
    let mut is_open = ctx.data(|d| d.get_temp::<bool>(Id::new(OPEN))).unwrap_or(false);
    let mut settings_open = ctx.data(|d| d.get_temp::<bool>(Id::new(SETTINGS))).unwrap_or(false);
    let mut selected = None;

    // Compact shortcut pad: every button performs an actual LightCraft command.
    if prefs.enabled && !settings_open {
        egui::Area::new(Id::new("lightcraft.android.wheel.pad"))
            .order(Order::Foreground)
            .anchor(Align2::RIGHT_CENTER, egui::vec2(-10.0, 0.0))
            .show(ctx, |ui| {
                ui.vertical(|ui| {
                    ui.spacing_mut().item_spacing.y = 5.0;
                    for (title, action) in [
                        ("Undo", WheelAction::Undo),
                        ("Redo", WheelAction::Redo),
                    ] {
                        if ui.add_sized([54.0, 45.0], egui::Button::new(title)).clicked() {
                            selected = Some(action);
                        }
                    }
                    let wheel_button = egui::Button::new(egui::RichText::new("Lc").strong().color(CYAN));
                    if ui.add_sized([54.0, 54.0], wheel_button).clicked() {
                        is_open = !is_open;
                        ctx.request_repaint();
                    }
                    if ui.add_sized([54.0, 45.0], egui::Button::new("Zoom")).clicked() {
                        selected = Some(WheelAction::Zoom);
                    }
                    if ui.add_sized([54.0, 45.0], egui::Button::new("Fit")).clicked() {
                        selected = Some(WheelAction::Fit);
                    }
                });
            });
    }

    if !prefs.enabled { is_open = false; }
    if is_open && !settings_open {
        egui_extras::install_image_loaders(ctx);
        let screen = ctx.content_rect();
        let radius = 124.0 * (prefs.size_percent.clamp(70.0, 150.0) / 100.0);
        let center = Pos2::new(
            (screen.width() * 0.60).clamp(radius + 8.0, screen.right() - radius - 70.0),
            (screen.height() * 0.64).clamp(radius + 8.0, screen.bottom() - radius - 8.0),
        );
        let pos = center - Vec2::splat(radius);
        let result = egui::Area::new(Id::new("lightcraft.android.wheel.active"))
            .fixed_pos(pos)
            .order(Order::Foreground)
            .show(ctx, |ui| paint_wheel(ui, &prefs, true));
        if let Some(action) = result.inner {
            selected = Some(action);
            is_open = false;
        }
        // Escape closes the wheel without invoking a background shortcut.
        if ctx.input(|i| i.key_pressed(egui::Key::Escape)) {
            is_open = false;
        }
    }

    if settings_open {
        egui_extras::install_image_loaders(ctx);
        let mut requested_open = true;
        egui::Window::new("LightCraft Stylus Wheel")
            .id(Id::new("lightcraft.android.wheel.settings.window"))
            .default_width(370.0)
            .resizable(true)
            .open(&mut requested_open)
            .show(ctx, |ui| {
                ui.checkbox(&mut prefs.enabled, "Enable Stylus Wheel");
                ui.horizontal(|ui| {
                    ui.label("Wheel Size");
                    ui.add(egui::Slider::new(&mut prefs.size_percent, 70.0..=150.0).suffix("%"));
                });
                ui.horizontal(|ui| {
                    ui.label("Opacity");
                    ui.add(egui::Slider::new(&mut prefs.opacity_percent, 25.0..=100.0).suffix("%"));
                });
                ui.checkbox(&mut prefs.soft_shadow, "Soft Shadow");
                ui.separator();
                ui.label("Live 1:1 Preview — matches the actual wheel size and opacity");
                egui::ScrollArea::vertical().max_height(390.0).show(ui, |ui| {
                    ui.vertical_centered(|ui| { let _ = paint_wheel(ui, &prefs, false); });
                });
                ui.separator();
                ui.label("Customize each wheel segment");
                for (idx, slot) in prefs.slots.iter_mut().enumerate() {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", idx + 1));
                        egui::ComboBox::from_id_salt(("lightcraft-wheel-action", idx))
                            .selected_text(slot.label())
                            .show_ui(ui, |ui| {
                                for action in WheelAction::ALL {
                                    ui.selectable_value(slot, action, action.label());
                                }
                            });
                    });
                }
                if ui.button("Reset Wheel to Default").clicked() {
                    prefs = WheelPrefs::default();
                }
            });
        settings_open = requested_open;
    }

    app.ui.settings.stylus_wheel = prefs;
    ctx.data_mut(|d| {
        d.insert_temp(Id::new(OPEN), is_open);
        d.insert_temp(Id::new(SETTINGS), settings_open);
    });
    if let Some(action) = selected { run_action(app, ctx, action); }
}
