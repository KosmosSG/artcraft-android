// DesignCraft-only Android Dc menu, injected into the pinned upstream app bar.
// Keep it beside Home. The native wrapper consumes the action bits next frame.
// Never copy this UI into the released DesignCraft or other applications.
#[cfg(target_os = "android")]
static DC_MENU_ACTIONS: std::sync::atomic::AtomicU16 =
    std::sync::atomic::AtomicU16::new(0);

#[cfg(target_os = "android")]
pub fn take_dc_menu_actions() -> u16 {
    DC_MENU_ACTIONS.swap(0, std::sync::atomic::Ordering::Relaxed)
}

#[cfg(target_os = "android")]
fn dc_launcher_menu(app: &mut DesignApp, ui: &mut egui::Ui) {
    let id = egui::Id::new("designcraft.dc.menu.texture");
    let texture = ui.ctx().data(|data| data.get_temp::<egui::TextureHandle>(id))
        .unwrap_or_else(|| {
            let rgba = include_bytes!("dc-launcher-icon.rgba");
            let picture = egui::ColorImage::from_rgba_unmultiplied([96, 96], rgba);
            let handle = ui.ctx().load_texture(
                "Approved DesignCraft Dc icon", picture, egui::TextureOptions::LINEAR);
            ui.ctx().data_mut(|data| data.insert_temp(id, handle.clone()));
            handle
        });
    let image = egui::Image::from_texture((texture.id(), egui::vec2(22.0, 22.0)));
    let button = egui::Button::image_and_text(image, "▾").min_size(egui::vec2(36.0, 26.0));
    egui::containers::menu::MenuButton::from_button(button).ui(ui, |ui| {
        ui.set_min_width(200.0);
        ui.with_layout(egui::Layout::top_down_justified(egui::Align::Min), |ui| {
            ui.menu_button("Fonts", |ui| {
                for (label, bit) in [
                    ("Import Fonts (TTF/OTF/TTC)…", 1_u16),
                    ("Select Shared Font Folder…", 2_u16),
                    ("Refresh Shared Fonts", 4_u16),
                    ("Reload Font Catalog", 8_u16),
                ] {
                    if ui.button(label).clicked() {
                        DC_MENU_ACTIONS.fetch_or(bit, std::sync::atomic::Ordering::Relaxed);
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                }
            });
            ui.menu_button("Updates", |ui| {
                for (label, bit) in [
                    ("Check Updates", 16_u16),
                    ("Startup Update Check…", 32_u16),
                ] {
                    if ui.button(label).clicked() {
                        DC_MENU_ACTIONS.fetch_or(bit, std::sync::atomic::Ordering::Relaxed);
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                }
            });
            ui.menu_button("Appearance", |ui| {
                for (label, code) in [
                    ("Dark", "dark"),
                    ("Medium Dark", "mediumDark"),
                    ("Medium Light", "mediumLight"),
                    ("Light", "light"),
                    ("High Contrast", "highContrast"),
                ] {
                    if ui.button(label).clicked() {
                        let _ = app.run("window.brightness", serde_json::json!({"brightness": code}));
                        ui.close();
                    }
                }
            });
            ui.separator();
            ui.menu_button("Android Tools", |ui| {
                ui.label("Keyboard: V/T/H/Z/A/P/N/F/M/B");
                ui.label("Ctrl+W → Don't Save (D) / Save (S) / Cancel (C)");
                ui.label("Esc exits document typing");
            });
            ui.separator();
            if ui.button("About DesignCraft").clicked() {
                let _ = app.run("help.about", serde_json::json!({}));
                ui.close();
            }
        });
    });
}
