// GRIDCRAFT_ANDROID_NATIVE_MENU_V1
// Embedded only into the pinned GridCraft Android builder's disposable
// upstream checkout. The existing title-bar has spare horizontal space;
// no bottom dock, floating window, or new title-bar row is introduced.
// Java/JNI operations are queued to the generated Android shell through
// egui's transient Context data, never invoked from the upstream crate.
            ui.menu_button("GridCraft Tools", |ui| {
                ui.set_min_width(260.0);
                let command_id = egui::Id::new("gridcraft.android.menu.action");
                ui.label(egui::RichText::new("Fonts").strong());
                for (title, command) in [
                    ("Import TTF / OTF...", "import"),
                    ("Select Shared Font Folder...", "folder"),
                    ("Refresh Shared Fonts", "refresh"),
                ] {
                    if ui.button(title).clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(command_id, command.to_owned()));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                }
                let font_status = ui.ctx().data(|d|
                    d.get_temp::<String>(egui::Id::new("gridcraft.android.menu.font_status"))
                ).unwrap_or_default();
                if !font_status.is_empty() {
                    ui.small(font_status);
                }
                if ui.button("Detected font families / Rescan").clicked() {
                    ui.ctx().data_mut(|d| d.insert_temp(command_id, "diagnose_fonts".to_owned()));
                    ui.ctx().request_repaint();
                }
                let catalog = ui.ctx().data(|d| d.get_temp::<String>(
                    egui::Id::new("gridcraft.android.menu.catalog_status"))).unwrap_or_default();
                egui::ScrollArea::vertical().id_salt("gridcraft.font.diagnostics")
                    .max_height(200.0).show(ui, |ui| { ui.set_max_width(420.0); ui.small(catalog); });
                ui.separator();
                ui.label(egui::RichText::new("Android updates").strong());
                if ui.button("Check for GridCraft Updates").clicked() {
                    ui.ctx().data_mut(|d| d.insert_temp(command_id, "updates".to_owned()));
                    ui.ctx().request_repaint();
                    ui.close();
                }
                let checking = ui.ctx().data(|d|
                    d.get_temp::<bool>(egui::Id::new("gridcraft.android.menu.checking"))
                ).unwrap_or(false);
                if checking {
                    ui.horizontal(|ui| {
                        ui.spinner();
                        ui.label("Checking GitHub Releases...");
                    });
                }
                let update_status = ui.ctx().data(|d|
                    d.get_temp::<String>(egui::Id::new("gridcraft.android.menu.update_status"))
                ).unwrap_or_default();
                if !update_status.is_empty() {
                    ui.small(update_status);
                }
                let has_release = ui.ctx().data(|d|
                    d.get_temp::<bool>(egui::Id::new("gridcraft.android.menu.has_release"))
                ).unwrap_or(false);
                let install_available = ui.ctx().data(|d|
                    d.get_temp::<bool>(egui::Id::new("gridcraft.android.menu.can_install"))
                ).unwrap_or(false);
                if install_available && ui.button("Download & Install Verified Update...").clicked() {
                    ui.ctx().data_mut(|d| d.insert_temp(command_id, "download_install".to_owned()));
                    ui.ctx().request_repaint();
                    ui.close();
                }
                if has_release && ui.button("View verified GitHub Release...").clicked() {
                    ui.ctx().data_mut(|d| d.insert_temp(command_id, "open_release".to_owned()));
                    ui.ctx().request_repaint();
                    ui.close();
                }
                let mut startup = ui.ctx().data(|d|
                    d.get_temp::<bool>(egui::Id::new("gridcraft.android.menu.startup_check"))
                ).unwrap_or(false);
                if ui.checkbox(&mut startup, "Check for updates at startup").changed() {
                    ui.ctx().data_mut(|d| {
                        d.insert_temp(command_id, if startup { "startup_on" } else { "startup_off" }.to_owned());
                        d.insert_temp(egui::Id::new("gridcraft.android.menu.startup_check"), startup);
                    });
                    ui.ctx().request_repaint();
                }
                ui.separator();
                ui.label(egui::RichText::new("Appearance").strong());
                let mut dark = ui.ctx().theme() == egui::Theme::Dark;
                if ui.checkbox(&mut dark, "Dark mode").changed() {
                    // GridCraft's own view.darkMode command persists the
                    // choice; do not override its existing System/Light mode.
                    app.run_or_alert("view.darkMode", json!({}));
                    ui.ctx().request_repaint();
                    ui.close();
                }
                ui.menu_button("Theme preferences (System / Light / Dark)", |ui| {
                    theme_choices(app, ui);
                });
                // Touch drag defaults to scrolling; users can opt into
                // one-finger drag-selection without affecting mouse or
                // two-finger trackpad scrolling.
                let selection_id = egui::Id::new("gridcraft.android.touch_select");
                let mut touch_select = ui.ctx().data(|d| d.get_temp::<bool>(selection_id)).unwrap_or(false);
                if ui.checkbox(&mut touch_select, "Touch drag selects cells").changed() {
                    ui.ctx().data_mut(|d| d.insert_temp(selection_id, touch_select));
                    ui.ctx().request_repaint();
                }
                ui.label(egui::RichText::new("Hold a cell, then drag to select; drag the green fill handle to extend.").small());
                ui.label(egui::RichText::new("Graphics: wgpu GPU • Vulkan preferred, OpenGL fallback").small());
                ui.separator();
                ui.label(egui::RichText::new("Spreadsheet shortcuts").strong());
                for (title, command) in [
                    ("Undo", "edit.undo"), ("Redo", "edit.redo"),
                    ("Previous sheet", "sheet.previous"), ("Next sheet", "sheet.next"),
                ] {
                    if ui.button(title).clicked() {
                        app.run_or_alert(command, json!({}));
                        ui.close();
                    }
                }
                ui.horizontal(|ui| {
                    let zoom = app.session.active()
                        .and_then(|d| d.wb.active().map(|s| s.zoom))
                        .unwrap_or(100);
                    for (title, percent) in [
                        ("Zoom -", (i32::from(zoom) - 10).clamp(10, 400)),
                        ("Zoom +", (i32::from(zoom) + 10).clamp(10, 400)),
                    ] {
                        if ui.button(title).clicked() {
                            app.run_or_alert("view.zoom", json!({"percent": percent}));
                            ui.close();
                        }
                    }
                });
                ui.separator();
                ui.small("Imports refresh the Home font list automatically. Select a family to apply it to cells.");
            });
