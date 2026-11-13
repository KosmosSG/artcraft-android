// GRIDCRAFT_ANDROID_NATIVE_MENU_V1
// Compact WordCraft-style top-left Gc menu. All approved actions are preserved:
// fonts/SAF, verified updater, appearance, touch selection, shortcuts and diagnostics.
// Large font catalogs now render only inside an explicitly opened submenu.
            ui.menu_button("GridCraft Tools", |ui| {
                ui.set_min_width(270.0);
                let command_id = egui::Id::new("gridcraft.android.menu.action");
                for (title, command) in [
                    ("Import Fonts (TTF / OTF)…", "import"),
                    ("Choose Shared Font Folder…", "folder"),
                    ("Refresh Shared Fonts", "refresh"),
                ] {
                    if ui.button(title).clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(command_id, command.to_owned()));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                }
                ui.menu_button("Font Catalog & Diagnostics", |ui| {
                    ui.set_min_width(330.0);
                    if ui.button("Detected font families / Rescan").clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(command_id, "diagnose_fonts".to_owned()));
                        ui.ctx().request_repaint();
                    }
                    let font_status = ui.ctx().data(|d|
                        d.get_temp::<String>(egui::Id::new("gridcraft.android.menu.font_status"))
                    ).unwrap_or_default();
                    if !font_status.is_empty() { ui.small(font_status); }
                    ui.separator();
                    let catalog = ui.ctx().data(|d| d.get_temp::<String>(
                        egui::Id::new("gridcraft.android.menu.catalog_status")
                    )).unwrap_or_default();
                    egui::ScrollArea::vertical().id_salt("gridcraft.font.diagnostics")
                        .max_height(260.0).show(ui, |ui| {
                            ui.set_max_width(430.0);
                            ui.small(catalog);
                        });
                    ui.small("Imported fonts refresh the Home font list automatically.");
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
                ui.menu_button("Appearance", |ui| {
                    ui.set_min_width(235.0);
                    let mut dark = ui.ctx().theme() == egui::Theme::Dark;
                    if ui.checkbox(&mut dark, "Dark mode").changed() {
                        // Keep the approved persisted System/Light/Dark behavior.
                        app.run_or_alert("view.darkMode", json!({}));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                    ui.menu_button("Theme preferences (System / Light / Dark)", |ui| {
                        theme_choices(app, ui);
                    });
                    // Touch drag selection defaults off; two-finger scrolling is untouched.
                    let selection_id = egui::Id::new("gridcraft.android.touch_select");
                    let mut touch_select = ui.ctx().data(|d|
                        d.get_temp::<bool>(selection_id)
                    ).unwrap_or(false);
                    if ui.checkbox(&mut touch_select, "Touch drag selects cells").changed() {
                        ui.ctx().data_mut(|d| d.insert_temp(selection_id, touch_select));
                        ui.ctx().request_repaint();
                    }
                    ui.small("Hold a cell, then drag to select; drag the fill handle to extend.");
                });
                // GRIDCRAFT_PHOTO_WHEEL_V1: PhotoCraft Default UI, exact Gc colour.
                ui.menu_button("Stylus Wheel", |ui| {
                    let enabled = ui.ctx().data(|d|
                        d.get_temp::<bool>(egui::Id::new("gridcraft.android.wheel.enabled"))
                    ).unwrap_or(false);
                    let command_id = egui::Id::new("gridcraft.android.wheel.menu");
                    if ui.button(if enabled { "✓ Stylus Wheel ON (tap to disable)" }
                        else { "Stylus Wheel OFF (tap to enable)" }).clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(command_id, "toggle".to_owned()));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                    if ui.button("Customize Wheel…").clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(command_id, "settings".to_owned()));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                    if enabled && ui.button("Show Wheel at Pointer").clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(command_id, "show".to_owned()));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                    ui.small("Default • 8 customizable segments");
                    ui.small("HONOR Magic-Pencil: hover + side button");
                    ui.small("Wheel preview uses actual size and opacity.");
                });
                ui.menu_button("Spreadsheet Shortcuts", |ui| {
                    for (title, command) in [
                        ("Undo", "edit.undo"), ("Redo", "edit.redo"),
                        ("Previous sheet", "sheet.previous"), ("Next sheet", "sheet.next"),
                    ] {
                        if ui.button(title).clicked() {
                            app.run_or_alert(command, json!({}));
                            ui.close();
                        }
                    }
                    ui.separator();
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
                });
                ui.separator();
                ui.menu_button("About GridCraft", |ui| {
                    ui.small("Graphics: wgpu GPU • Vulkan preferred, OpenGL fallback");
                    ui.small("Imported fonts: recursive shared folder up to 5,000 files / 4 GiB.");
                    ui.small("Touch, trackpad and keyboard features retained.");
                });
            });
