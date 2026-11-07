
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
        ui.set_min_width(270.0);
        let refreshing = ui.ctx().data(|d| d.get_temp::<bool>(egui::Id::new("wc_menu_font_busy"))).unwrap_or(false);
        for (label, action) in [
            ("Choose shared font folder…", "font_folder"),
            ("Refresh shared fonts", "font_refresh"),
        ] {
            let font_action = action == "font_folder" || action == "font_refresh";
            let label = if refreshing && action == "font_refresh" { "Refreshing fonts…" } else { label };
            if ui.add_enabled(!font_action || !refreshing, egui::Button::new(label)).clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("wc_menu_action"), action.to_owned()));
                if action != "font_refresh" { ui.close(); }
            }
        }
        ui.separator();
        // Single verified updater inside the approved Wc icon menu.
        // The former read-only checker stays in source as a compatibility fallback,
        // but has no duplicate menu entry or independent startup preference.
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
        let mut pad = ui.ctx().data(|d| d.get_temp::<bool>(egui::Id::new("wc_menu_pad"))).unwrap_or(false);
        if ui.checkbox(&mut pad, "Show Shortcut Pad").changed() {
            let action = if pad { "pad_on" } else { "pad_off" };
            ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("wc_menu_action"), action.to_owned()));
        }
        if ui.button("Customize physical keyboard…").clicked() {
            ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("wc_menu_action"), "keyboard".to_owned()));
            ui.close();
        }
        ui.separator();
        ui.label("Recursive shared fonts: 5,000 files / 4 GiB maximum.");
        let gpu = ui.ctx().data(|d| d.get_temp::<String>(egui::Id::new("wc_menu_gpu"))).unwrap_or_default();
        ui.label(gpu);
        let status = ui.ctx().data(|d| d.get_temp::<String>(egui::Id::new("wc_menu_status"))).unwrap_or_default();
        ui.label(status);
    });
}
