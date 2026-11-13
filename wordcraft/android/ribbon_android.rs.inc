
// Android-only ribbon integration. The platform shell handles JNI actions after
// the ribbon finishes drawing; no Android dependency enters the upstream UI crate.
#[cfg(target_os = "android")]
fn artcraft_android_menu(ui: &mut Ui) {
    // The same approved artwork used for the Android launcher, scaled down for the
    // first (leftmost) control of WordCraft's top tab strip.
    let icon_id = egui::Id::new("wc_approved_menu_texture");
    let texture = ui.ctx().data(|d| d.get_temp::<egui::TextureHandle>(icon_id))
        .unwrap_or_else(|| {
            let rgba = include_bytes!("wordcraft-android-menu-icon.rgba");
            let color = egui::ColorImage::from_rgba_unmultiplied([40, 40], rgba);
            let texture = ui.ctx().load_texture("WordCraft approved launcher icon", color, egui::TextureOptions::LINEAR);
            ui.ctx().data_mut(|d| d.insert_temp(icon_id, texture.clone()));
            texture
        });
    // No egui button frame: the original launcher artwork is the entire icon.
    // It remains an accessible clickable menu trigger without the outlined square.
    let button = ui.add(egui::Button::image(
        egui::Image::new((texture.id(), egui::vec2(24.0, 24.0)))
    ).frame(false)).on_hover_text("WordCraft • ArtCraft tools");
    egui::Popup::menu(&button).show(|ui| {
        // WC_COMPACT_GC_STYLE_MENU_V1: Match the approved GridCraft icon menu.
        // Keep the existing SAF import/folder/refresh actions directly accessible.
        // The one verified updater submenu below is intentionally unchanged.
        ui.set_min_width(270.0);
        let refreshing = ui.ctx().data(|d|
            d.get_temp::<bool>(egui::Id::new("wc_menu_font_busy"))
        ).unwrap_or(false);
        for (label, action) in [
            ("Import Fonts (TTF / OTF)…", "font_import"),
            ("Choose Shared Font Folder…", "font_folder"),
            ("Refresh Shared Fonts", "font_refresh"),
        ] {
            let label = if refreshing && action == "font_refresh" {
                "Refreshing fonts…"
            } else { label };
            if ui.add_enabled(!refreshing, egui::Button::new(label)).clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("wc_menu_action"), action.to_owned()
                ));
                ui.ctx().request_repaint();
                if action != "font_refresh" { ui.close(); }
            }
        }
        ui.menu_button("Font Status & Diagnostics", |ui| {
            ui.set_min_width(330.0);
            ui.small("Shared fonts: recursive folders, 5,000 files / 4 GiB maximum.");
            let status = ui.ctx().data(|d|
                d.get_temp::<String>(egui::Id::new("wc_menu_status"))
            ).unwrap_or_default();
            if !status.is_empty() {
                ui.separator();
                ui.small(status);
            }
            ui.small("Fonts can be imported individually or from a shared folder.");
        });
        ui.separator();
        ui.menu_button("App Updates", |ui| {
            ui.set_min_width(250.0);
            let action_id = egui::Id::new("artcraft.updater.action");
            let installed = ui.ctx().data(|d|
                d.get_temp::<String>(egui::Id::new("artcraft.updater.installed"))
            ).unwrap_or_default();
            if !installed.is_empty() { ui.small(format!("Installed: {installed}")); }
            if ui.button("Check for Updates").clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(action_id, "check".to_owned()));
                ui.ctx().request_repaint();
                ui.close();
            }
            let available = ui.ctx().data(|d|
                d.get_temp::<bool>(egui::Id::new("artcraft.updater.available"))
            ).unwrap_or(false);
            if available && ui.button("Download & Install Update…").clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(action_id, "download".to_owned()));
                ui.ctx().request_repaint();
                ui.close();
            }
            if available && ui.button("View Release Notes…").clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(action_id, "view".to_owned()));
                ui.ctx().request_repaint();
                ui.close();
            }
            let mut startup = ui.ctx().data(|d|
                d.get_temp::<bool>(egui::Id::new("artcraft.updater.startup"))
            ).unwrap_or(false);
            if ui.checkbox(&mut startup, "Check at Startup").changed() {
                ui.ctx().data_mut(|d| {
                    d.insert_temp(action_id, "toggle".to_owned());
                    d.insert_temp(egui::Id::new("artcraft.updater.startup"), startup);
                });
                ui.ctx().request_repaint();
            }
            let status = ui.ctx().data(|d|
                d.get_temp::<String>(egui::Id::new("artcraft.updater.status"))
            ).unwrap_or_default();
            if !status.is_empty() { ui.small(status); }
            // Diagnostics are visible only to separately installed, temporary-signed candidates.
            let diagnostics = ui.ctx().data(|d|
                d.get_temp::<bool>(egui::Id::new("artcraft.updater.diagnostics"))
            ).unwrap_or(false);
            if diagnostics {
                ui.separator();
                if ui.button("Test APK download + SHA-256 (no install)").clicked() {
                    ui.ctx().data_mut(|d| d.insert_temp(action_id, "test".to_owned()));
                    ui.ctx().request_repaint();
                    ui.close();
                }
            }
        });
        ui.separator();
        // WC_GC_STYLE_APPEARANCE_V1: Reuse WordCraft's persistent interface
        // theme (ui.theme) rather than GridCraft's page-only view.darkMode.
        ui.menu_button("Appearance", |ui| {
            ui.set_min_width(250.0);
            // WC_ANDROID11_APPEARANCE_SINGLE_THEME_V1:
            // Theme preferences own System/Light/Dark; no duplicate Dark mode toggle.
            ui.menu_button("Theme preferences (System / Light / Dark)", |ui| {
                let selected = ui.ctx().data(|d|
                    d.get_temp::<String>(egui::Id::new("wc_menu_interface_theme"))
                ).unwrap_or_else(|| "system".to_owned());
                for (label, code, action) in [
                    ("System (follow device)", "system", "theme_system"),
                    ("Light", "light", "theme_light"),
                    ("Dark", "dark", "theme_dark"),
                ] {
                    if ui.selectable_label(selected == code, label).clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(
                            egui::Id::new("wc_menu_action"), action.to_owned()
                        ));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                }
            });
            ui.separator();
            let mut dark_page = ui.ctx().data(|d|
                d.get_temp::<bool>(egui::Id::new("wc_menu_dark_page"))
            ).unwrap_or(false);
            if ui.checkbox(&mut dark_page, "Dark document pages").changed() {
                let action = if dark_page { "page_dark_on" } else { "page_dark_off" };
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("wc_menu_action"), action.to_owned()
                ));
                ui.ctx().request_repaint();
                ui.close();
            }
            ui.small("Page colours are separate from the interface theme.");
        });
        // WC_BLUE_STYLUS_WHEEL_MENU_V1: PhotoCraft-style wheel, WordCraft colour.
        ui.menu_button("Stylus Wheel", |ui| {
            ui.set_min_width(240.0);
            let mut visible = ui.ctx().data(|d|
                d.get_temp::<bool>(egui::Id::new("wc_menu_wheel_visible"))
            ).unwrap_or(true);
            if ui.checkbox(&mut visible, "Show Stylus Wheel").changed() {
                let action = if visible { "wheel_on" } else { "wheel_off" };
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("wc_menu_action"), action.to_owned()
                ));
                ui.ctx().request_repaint();
            }
            if ui.button("Customize Stylus Wheel…").clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("wc_menu_action"), "wheel_customize".to_owned()
                ));
                ui.ctx().request_repaint();
                ui.close();
            }
        });
        ui.menu_button("Keyboard & Shortcuts", |ui| {
            ui.set_min_width(230.0);
            let mut pad = ui.ctx().data(|d|
                d.get_temp::<bool>(egui::Id::new("wc_menu_pad"))
            ).unwrap_or(false);
            if ui.checkbox(&mut pad, "Show Shortcut Pad").changed() {
                let action = if pad { "pad_on" } else { "pad_off" };
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("wc_menu_action"), action.to_owned()
                ));
                ui.ctx().request_repaint();
            }
            if ui.button("Customize physical keyboard…").clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("wc_menu_action"), "keyboard".to_owned()
                ));
                ui.close();
            }
        });
        // WC_ANDROID10_COMPACT_MENU_V1: pen pressure is on by default.
        // Stylus/hover/ink support remains available via the Draw tab, but
        // the large diagnostic Stylus & Handwriting submenu is removed.
        ui.menu_button("About WordCraft", |ui| {
            ui.set_min_width(300.0);
            let installed = ui.ctx().data(|d|
                d.get_temp::<String>(egui::Id::new("artcraft.updater.installed"))
            ).unwrap_or_default();
            if !installed.is_empty() { ui.small(format!("Installed: {installed}")); }
            let gpu = ui.ctx().data(|d|
                d.get_temp::<String>(egui::Id::new("wc_menu_gpu"))
            ).unwrap_or_default();
            if !gpu.is_empty() { ui.small(gpu); }
            ui.small("Approved Android ARM64 build • Wc launcher icon.");
        });
    });
}
