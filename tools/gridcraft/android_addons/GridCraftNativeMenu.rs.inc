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
                // One App Updates submenu; keep approved Gc icon, fonts and theme intact.
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
