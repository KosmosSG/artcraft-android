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
                ui.small("Imported fonts become available after restarting GridCraft.");
            });
