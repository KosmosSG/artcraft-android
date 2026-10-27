
// Android-only ribbon integration. The platform shell handles JNI actions after
// the ribbon finishes drawing; no Android dependency enters the upstream UI crate.
#[cfg(target_os = "android")]
fn artcraft_android_menu(ui: &mut Ui) {
    ui.menu_button("ArtCraft", |ui| {
        ui.set_min_width(270.0);
        let refreshing = ui.ctx().data(|d| d.get_temp::<bool>(egui::Id::new("wc_menu_font_busy"))).unwrap_or(false);
        for (label, action) in [
            ("Choose shared font folder…", "font_folder"),
            ("Refresh shared fonts", "font_refresh"),
            ("Check for Updates", "check_updates"),
        ] {
            let font_action = action == "font_folder" || action == "font_refresh";
            let label = if refreshing && action == "font_refresh" { "Refreshing fonts…" } else { label };
            if ui.add_enabled(!font_action || !refreshing, egui::Button::new(label)).clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("wc_menu_action"), action.to_owned()));
                if action != "font_refresh" { ui.close(); }
            }
        }
        let mut startup = ui.ctx().data(|d| d.get_temp::<bool>(egui::Id::new("wc_menu_startup"))).unwrap_or(false);
        if ui.checkbox(&mut startup, "Check updates on startup").changed() {
            let action = if startup { "startup_on" } else { "startup_off" };
            ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("wc_menu_action"), action.to_owned()));
        }
        let release = ui.ctx().data(|d| d.get_temp::<String>(egui::Id::new("wc_menu_release"))).unwrap_or_default();
        if !release.is_empty() && ui.button("View published release").clicked() {
            ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("wc_menu_action"), "view_release".to_owned()));
            ui.close();
        }
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
        ui.label("Shared fonts: TTF / OTF / TTC / OTC; imports stay in WordCraft.");
        let gpu = ui.ctx().data(|d| d.get_temp::<String>(egui::Id::new("wc_menu_gpu"))).unwrap_or_default();
        ui.label(gpu);
        let status = ui.ctx().data(|d| d.get_temp::<String>(egui::Id::new("wc_menu_status"))).unwrap_or_default();
        ui.label(status);
    });
}
