#!/usr/bin/env python3
"""Port the released Android font/menu/DCS behavior to official DeckCraft 0.14.1.

Edits only a disposable upstream checkout. Every replacement fails closed on drift.
"""
import ast
from pathlib import Path
import sys
from patch_unsaved_dcs import HELPER

HERE = Path(__file__).parent


def apply(root):
    src = Path(root) / 'crates/ui-egui/src'
    def edit(name, old, new):
        p = src / name
        text = p.read_text()
        if text.count(old) != 1:
            raise ValueError(f'{name}: expected one anchor: {old[:90]}')
        p.write_text(text.replace(old, new, 1))

    # Keep the already released persistence path, validation and font database integration.
    tree = ast.parse((HERE / 'patch_deckcraft_fonts.py').read_text())
    addition = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'addition' for t in n.targets))
    addition = addition.replace('fn restore_private_fonts()', 'pub(crate) fn restore_private_fonts()')
    addition = addition.replace('fn import_font_bytes(', 'pub(crate) fn import_font_bytes(')
    addition = addition.replace('std::env::var_os("XDG_DATA_HOME").or_else',
        'std::env::var_os("DECKCRAFT_FONT_IMPORT_ROOT").or_else(|| std::env::var_os("XDG_DATA_HOME")).or_else')
    addition = addition.replace('        let added = deckcraft_fonts::FontDb::global().add_font(bytes.to_vec());',
        '        let added = deckcraft_fonts::FontDb::global().add_font(bytes.to_vec());\n        self.textures = textures::Textures::default();')
    # Methods live at crate root, so split app modules can call them without private sibling access.
    p = src / 'lib.rs'
    p.write_text(p.read_text() + '\nimpl SlideApp {\n' + addition + '\n}\n')
    edit('app.rs', '        let audio_out = services.audio_out.take();',
        '        Self::restore_private_fonts();\n        let audio_out = services.audio_out.take();')
    edit('state.rs', 'enum FilePurpose {\n    Open,', 'enum FilePurpose {\n    Open,\n    Font,')
    edit('app/files.rs', '        "open" => FilePurpose::Open,', '        "open" => FilePurpose::Open,\n        "font" => FilePurpose::Font,')
    edit('app/files.rs', '        FilePurpose::Open => open_command(name),',
        '        FilePurpose::Open => open_command(name),\n        FilePurpose::Font => None,')
    edit('app/files.rs', '        let req = self.pending_files.remove(pos);',
        '        let req = self.pending_files.remove(pos);\n        if req.purpose == FilePurpose::Font {\n            self.import_font_bytes(name, bytes);\n            return;\n        }')
    edit('lib.rs', '    ("app.openDialog", "Open…", None, "{purpose?}"),',
        '    ("app.openDialog", "Open…", None, "{purpose?}"),\n    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),\n    ("view.tabletTools", "Tablet Tools", None, "{}"),')
    edit('app/commands.rs', '            "app.openDialog" => self.pick_and_open(),',
        '            "app.openDialog" => self.pick_and_open(),\n            "app.importFont" => self.import_font_dialog(),\n            "view.tabletTools" => self.ui.tablet_tools = !self.ui.tablet_tools,')
    edit('app/commands.rs', '                #[cfg(not(target_arch = "wasm32"))]\n                updates_ui::request_check(self);',
        '''                #[cfg(target_os = "android")]
                if let Some(open) = self.services.open_async.as_mut() { open("deckcraft-updates", 0); }
                #[cfg(all(not(target_arch = "wasm32"), not(target_os = "android")))]
                updates_ui::request_check(self);''')
    edit('state.rs', '    pub ribbon_collapsed: bool,', '    pub ribbon_collapsed: bool,\n    #[serde(default)]\n    pub tablet_tools: bool,')
    edit('state.rs', '            ribbon_collapsed: false,', '            ribbon_collapsed: false,\n            tablet_tools: false,')
    # Keep Import Font under Help (and Tablet Tools) only.
    edit('menus.rs', '("Normal", "view.normal"),', '("Dark Theme", "view.dark"),\n                ("Tablet Tools", "view.tabletTools"),\n                ("-", ""),\n                ("Normal", "view.normal"),')
    edit('menus.rs', '("Command Palette", "app.palette")', '("Import Font…", "app.importFont"), ("Command Palette", "app.palette")')
    edit('app.rs', '        ribbon::title_bar(self, ui);', '        self.tablet_controls(ui);\n        ribbon::title_bar(self, ui);')
    tree = ast.parse((HERE / 'patch_deckcraft_tablet.py').read_text())
    tablet = next(ast.literal_eval(n.args[1].left) for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'change'
        and len(n.args) == 2 and isinstance(n.args[1], ast.BinOp))
    tablet = tablet.replace('fn tablet_controls(', 'pub(crate) fn tablet_controls(')
    # Left align popover entries while retaining 190x32 touch hit zones.
    tablet = tablet.replace('egui::Button::new(label)', 'egui::Button::new("").left_text(label)')
    # Persistent light/dark toggle is provided by official DeckCraft view.dark.
    tablet = tablet.replace('if command == "view.tabletTools" && self.ui.tablet_tools {',
        'if command == "view.dark" && self.ui.brightness == theme::Brightness::Dark { "✓ Dark Theme" } else if command == "view.tabletTools" && self.ui.tablet_tools {')
    p = src / 'lib.rs'; p.write_text(p.read_text() + '\nimpl SlideApp {\n' + tablet + '\n}\n')

    # D/C/S remains confined to the unsaved dialog, with asynchronous save acknowledgement.
    edit('services.rs', 'pub enum InboxEvent {', 'pub enum InboxEvent {\n    AndroidSaveFinished { id: u64, success: bool },')
    edit('services.rs', '    pub download: Option<DownloadFn>,', '    pub download: Option<DownloadFn>,\n    pub android_save_close: Option<Box<dyn FnMut(u64, &str, &[u8])>>,')
    edit('lib.rs', 'pub struct SlideApp {', 'pub struct SlideApp {\n    android_pending_close: Option<(u64, u64, std::sync::Arc<deckcraft_model::Presentation>, bool)>,')
    edit('app.rs', '        SlideApp {', '        SlideApp {\n            android_pending_close: None,')
    edit('app/files.rs', '                InboxEvent::Cancelled { id } =>',
        '                InboxEvent::AndroidSaveFinished { id, success } => self.android_save_finished(id, success),\n                InboxEvent::Cancelled { id } =>')
    p = src / 'lib.rs'; p.write_text(p.read_text() + (HERE / 'save_close.rs').read_text())
    # Put key capture at root; dialog bodies can access it without duplicating transport logic.
    p.write_text(p.read_text() + HELPER.replace('fn take_dcs(', 'pub(crate) fn take_dcs(') + (HERE / 'dcs_tests.rs').read_text())
    p = src / 'dialogs/body.rs'; text = p.read_text()
    start = text.index('fn dlg_quit('); end = text.index('fn dlg_comment(', start)
    body = text[start:end]
    for label, key in [("Don't Save", 'D'), ('Cancel', 'C'), ('Save', 'S')]:
        body = body.replace(f'new("{label}")', f'new("{label} ({key})")')
    # Unlike a lazy or_else, always drain the modal's egui key/text events.
    # Match the device-tested Android.4 D/C/S behaviour.
    body = body.replace('    let mut done = false;', '    let java_action = ui.ctx().data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs")));\n    let egui_action = crate::take_dcs(ui.ctx());\n    let shortcut = java_action.or(egui_action);\n    let mut done = false;')
    body = body.replace('24.0))).clicked() {', '24.0))).clicked() || shortcut == Some(1) {', 1)
    close = body.index('fn dlg_close(')
    body = body[:close] + body[close:].replace('24.0))).clicked() {', '24.0))).clicked() || shortcut == Some(1) {', 1)
    body = body.replace('new("Cancel (C)").min_size(vec2(72.0, 24.0))).clicked() {', 'new("Cancel (C)").min_size(vec2(72.0, 24.0))).clicked() || shortcut == Some(2) {')
    body = body.replace('if save.clicked() ||', 'if shortcut == Some(3) || save.clicked() ||')
    body = body.replace('                if app.save_all() {', '                if app.services.android_save_close.is_some() {\n                    app.android_save_and_close(true);\n                } else if app.save_all() {')
    body = body.replace('                app.save();', '                if app.services.android_save_close.is_some() {\n                    app.android_save_and_close(false);\n                } else {\n                app.save();')
    body = body.replace('                    run(app, "file.close", json!({}));\n                }\n                done = true;', '                    run(app, "file.close", json!({}));\n                }\n                }\n                done = true;')
    p.write_text(text[:start] + body + text[end:])
    # Restore actual modal layering from device-tested Android.4.
    p = src / 'dialogs.rs'; s = p.read_text()
    old_show = '''    window.show(ctx, |ui| {
        ui.set_min_width(match d.id.as_str() {
            "themeColors" => 700.0,
            "themeFonts" => 400.0,
            _ => 340.0,
        });
        if d.id == "themeColors" {
            ui.set_min_height(360.0);
        } else if d.id == "themeFonts" {
            ui.set_min_height(280.0);
        }
        close = body(app, ui, &mut d);
    });'''
    assert s.count(old_show) == 1, 'Official modal shell changed'
    assert s.count('.open(&mut open);') == 1
    s = s.replace('.open(&mut open);', ';', 1)
    modal_show = '''    if matches!(d.id.as_str(), "close" | "quit") {
        egui::Modal::new(egui::Id::new(("deckcraft.confirm.modal", d.id.clone()))).show(ctx, |ui| {
            ui.set_min_width(340.0);
            ui.set_max_width(380.0);
            ui.vertical(|ui| {
                ui.horizontal(|ui| {
                    // Symmetric 24pt left spacer and close button keep the
                    // title geometrically centered within the real modal width.
                    let width = ui.available_width();
                    let gap = ui.spacing().item_spacing.x;
                    ui.add_sized([24.0, 26.0], egui::Label::new(""));
                    ui.add_sized([(width - 48.0 - 2.0 * gap).max(100.0), 26.0],
                        egui::Label::new(egui::RichText::new("DeckCraft").size(20.0))
                            .halign(egui::Align::Center));
                    if ui.add_sized([24.0, 26.0], egui::Button::new("×")).clicked() {
                        close = true;
                    }
                });
                ui.separator();
                close |= body(app, ui, &mut d);
            });
        });
    } else {
''' + old_show.replace('    window.show(ctx,', '    window.open(&mut open).show(ctx,') + '''
    }'''
    p.write_text(s.replace(old_show, modal_show, 1))
    edit('app.rs', '    pub fn logic(&mut self, ctx: &egui::Context) {',
        '    pub fn logic(&mut self, ctx: &egui::Context) {\n        self.android_capture_unsaved_dcs(ctx);')
    # Android Ctrl+W must work while slide text/IME has keyboard focus. The
    # official upstream app/keys.rs exits early if a field owns input, before
    # reaching menus::ui_shortcut. Route *only* Ctrl+W ahead of that early return
    # to the existing acknowledged close_presentation() D/C/S dialog, never
    # to Activity.finish(), and only when a presentation is open.
    edit('app/keys.rs',
        '''    /// Keyboard and clipboard for the slide (when no text field has focus).
    pub(super) fn keyboard(&mut self, ctx: &egui::Context) {''',
        '''    /// Match the Android hardware keyboard close shortcut even if a text
    /// field owns focus. Keep all other text shortcuts with their editor.
    fn android_editing_ctrl_w(events: &[egui::Event]) -> bool {
        events.iter().any(|event| matches!(
            event,
            egui::Event::Key {
                key: egui::Key::W, pressed: true, repeat: false, modifiers, ..
            } if (modifiers.ctrl || modifiers.command) && !modifiers.alt && !modifiers.shift
        ))
    }

    /// Keyboard and clipboard for the slide (when no text field has focus).
    pub(super) fn keyboard(&mut self, ctx: &egui::Context) {''')
    edit('app/keys.rs',
        '''        if ctx.memory(|m| m.focused().is_some()) || modal {''',
        '''        #[cfg(target_os = "android")]
        if !modal
            && self.session.active().is_some()
            && (ctx.data_mut(|d| d.remove_temp::<bool>(egui::Id::new("deckcraft.android.ctrl_w"))).unwrap_or(false)
                || ((ctx.memory(|m| m.focused().is_some())
                    || self.session.active().is_some_and(|d| d.selection.text.is_some()))
                    && Self::android_editing_ctrl_w(&events)))
        {
            // Same close path as File > Close and ordinary Ctrl+W. Dirty work
            // opens the real Save/Don't Save/Cancel modal; no background
            // activity exit and no silent loss of the committed slide text.
            self.note_settled_composition(ctx);
            self.suspend_ime_reset(viewport);
            self.route_ime_controls_only(ctx, &events);
            if let Some(id) = ctx.memory(|m| m.focused()) {
                ctx.memory_mut(|m| m.surrender_focus(id));
            }
            self.close_presentation();
            self.drain_requests();
            return;
        }
        // Route hardware arrows to the official engine text.move command
        // before egui's focused-widget guard. The engine interprets Shift as
        // "extend selection" and plain arrows as caret movement. Do not move
        // slide objects while canvas text editing is active.
        #[cfg(target_os = "android")]
        if !modal && !ctx.text_edit_focused() && !ctx.any_popup_open()
            && self.session.active().is_some_and(|d| d.selection.text.is_some())
        {
            if let Some(action) = ctx.data_mut(|d| d.remove_temp::<u8>(
                egui::Id::new("deckcraft.android.editor_arrow")))
            {
                let name = match action & 15 {
                    1 => "Left", 2 => "Right", 3 => "Up", 4 => "Down",
                    _ => "",
                };
                if !name.is_empty() {
                    self.note_settled_composition(ctx);
                    let modifiers = Mods { shift: action & 16 != 0, alt: false, cmd: false };
                    if let Err(err) = self.session.key(name, modifiers) {
                        self.set_status(err.to_string());
                    }
                    ctx.request_repaint();
                    self.drain_requests();
                    return;
                }
            }
        }
        // Android hardware Ctrl+A/C/X/V can be intercepted by the IME before
        // ctx.input(). The early RawInput and Java side channel carry a
        // one-shot action. Standard egui text fields and modals keep theirs.
        #[cfg(target_os = "android")]
        {
            let action = ctx.data_mut(|d| d.remove_temp::<u8>(
                egui::Id::new("deckcraft.android.clip_action")));
            let mut native_text = ctx.data_mut(|d| d.remove_temp::<String>(
                egui::Id::new("deckcraft.android.clip_text")));
            let custom_editing = !modal
                && self.session.active().is_some_and(|d| d.selection.text.is_some())
                && !ctx.text_edit_focused();
            if custom_editing {
                let mut handled_clipboard = false;
                match action {
                    Some(1) => {
                        if let Err(err) = self.session.execute("text.selectAll", &json!({})) {
                            self.set_status(err.to_string());
                        }
                        handled_clipboard = true;
                    }
                    Some(2) => {
                        self.publish_clipboard(ctx, false);
                        self.android_queue_clipboard_sync(ctx);
                        handled_clipboard = true;
                    }
                    Some(3) => {
                        let revision = self.session.active().map(|d| d.revision);
                        self.publish_clipboard(ctx, true);
                        self.android_queue_clipboard_sync(ctx);
                        if self.session.active().map(|d| d.revision) != revision {
                            self.note_application_edit(ctx);
                        }
                        handled_clipboard = true;
                    }
                    Some(4) => {
                        if native_text.is_none() {
                            native_text = events.iter().find_map(|ev| match ev {
                                egui::Event::Paste(text) => Some(text.clone()),
                                _ => None,
                            });
                        }
                        if let Some(text) = native_text.as_deref() {
                            let pasted = if text == OBJECTS_MARKER { "" } else { text };
                            let revision = self.session.active().map(|d| d.revision);
                            if let Err(err) = self.session.execute("edit.paste", &json!({"text": pasted})) {
                                self.set_status(err.to_string());
                            }
                            if self.session.active().map(|d| d.revision) != revision {
                                self.note_application_edit(ctx);
                            }
                        } else {
                            self.set_status("Android clipboard is empty");
                        }
                        handled_clipboard = true;
                    }
                    _ => {}
                }
                // Keep the usual synthetic egui clipboard events as fallback
                // when the hardware key did not reach either one-shot handler.
                if !handled_clipboard {
                    for ev in &events {
                        match ev {
                            egui::Event::Copy => {
                                self.publish_clipboard(ctx, false);
                        self.android_queue_clipboard_sync(ctx);
                                handled_clipboard = true;
                            }
                            egui::Event::Cut => {
                                let revision = self.session.active().map(|d| d.revision);
                                self.publish_clipboard(ctx, true);
                        self.android_queue_clipboard_sync(ctx);
                                if self.session.active().map(|d| d.revision) != revision {
                                    self.note_application_edit(ctx);
                                }
                                handled_clipboard = true;
                            }
                            egui::Event::Paste(text) => {
                                let pasted = if text == OBJECTS_MARKER { "" } else { text.as_str() };
                                let revision = self.session.active().map(|d| d.revision);
                                if let Err(err) = self.session.execute("edit.paste", &json!({"text": pasted})) {
                                    self.set_status(err.to_string());
                                }
                                if self.session.active().map(|d| d.revision) != revision {
                                    self.note_application_edit(ctx);
                                }
                                handled_clipboard = true;
                            }
                            _ => {}
                        }
                    }
                }
                if handled_clipboard {
                    // Update the slide and publish clipboard output immediately
                    // rather than waiting for a pointer tap to cause a paint.
                    ctx.request_repaint();
                    self.drain_requests();
                    return;
                }
            }
        }
        if ctx.memory(|m| m.focused().is_some()) || modal {''')
    # Physical keyboard commands are occasionally consumed by the Android IME
    # before the UI frame advances. Poll only while slide text is actively
    # edited, so Java's one-shot shortcut queue drains without an extra tap.
    edit('app/keys.rs',
         '''        let events = ctx.input(|i| i.events.clone());''',
         '''        let events = ctx.input(|i| i.events.clone());
        #[cfg(target_os = "android")]
        if self.session.active().is_some_and(|d| d.selection.text.is_some()) {
            ctx.request_repaint_after(std::time::Duration::from_millis(24));
        }''')

    # Publish Copy/Cut text to Android ClipboardManager synchronously in this
    # same frame via the host bridge; egui's platform-output copy is deferred.
    edit('app/keys.rs',
        '''    /// Match the Android hardware keyboard close shortcut even if a text''',
        '''    pub(crate) fn android_queue_clipboard_sync(&self, ctx: &egui::Context) {
        let text = self.session.clipboard.plain.clone();
        if !text.is_empty() {
            ctx.data_mut(|d| d.insert_temp(
                egui::Id::new("deckcraft.android.clipboard.pending"), text));
            ctx.request_repaint();
        }
    }

    /// Match the Android hardware keyboard close shortcut even if a text''')

    # Expose the shortcut-match helper to host-side Rust regression tests.
    edit('app/keys.rs',
        '''    fn android_editing_ctrl_w(events: &[egui::Event]) -> bool {''',
        '''    pub(crate) fn android_editing_ctrl_w(events: &[egui::Event]) -> bool {''')

    # The pinned upstream ribbon hardcodes a Mac-only Paste tooltip.
    # Android hardware keyboards use Control, not Command.
    edit('ribbon/home.rs', 'main.on_hover_text("Paste (⌘V)")',
         'main.on_hover_text(if cfg!(target_os = "android") { "Paste (Ctrl+V)" } else { "Paste (⌘V)" })')

    # Carry forward the release's render/round-trip/font-style regression, not just menu checks.
    tablet_tree = ast.parse((HERE / 'patch_deckcraft_tablet.py').read_text())
    tests = next(n.value for n in ast.walk(tablet_tree) if isinstance(n, ast.Constant)
                 and isinstance(n.value, str) and 'mod android_font_regression' in n.value)
    p = src / 'lib.rs'; p.write_text(p.read_text() + tests)
    # Preserve legacy family/style aliases for fonts loaded through Android's picker.
    original = (HERE / 'patch_deckcraft_tablet.py').read_text()
    alias_patch = original[original.index("p = Path(sys.argv[1]) / 'crates/fonts/src/fontdb.rs'"):original.index('# Reuse the approved Dk artwork')]
    exec(compile(alias_patch, 'legacy_font_aliases', 'exec'), {'Path': Path, 'sys': type('Args', (), {'argv': ['', str(root)]})})
    # Android's gesture backend suppresses touch/pointer hover after the second
    # finger joins, and sends a Zoom event instead. Native canvas zoom previously
    # required resp.hovered(), so the gesture often looked inert. Remember the
    # first touch origin ONLY while it started inside the canvas and a document
    # is editable, and use that origin to gate/anchor native pinch events.
    # Mouse/trackpad wheel zoom remains governed by the original hover check.
    edit('canvas.rs',
        '''    let (wheel, zoom_delta, hover) = ui.input(|i| (i.smooth_scroll_delta, i.zoom_delta(), i.pointer.hover_pos()));
    let zooming = resp.hovered() && (zoom_delta - 1.0).abs() > 1e-3;''',
        '''    let (wheel, zoom_delta, hover) = ui.input(|i| (i.smooth_scroll_delta, i.zoom_delta(), i.pointer.hover_pos()));
    #[cfg(target_os = "android")]
    let (touch_zoom_anchor, touch_pan_active): (Option<Pos2>, bool) = {
        let id = scroll_id.with("deckcraft_android_pinch_anchor");
        let (events, now, multi) = ui.input(|i| (i.events.clone(), i.time, i.multi_touch()));
        let mut last: Option<(Pos2, f64)> = ui.data_mut(|d| d.get_temp(id));
        for event in &events {
            match event {
                egui::Event::Touch { phase: egui::TouchPhase::Start, pos, .. } => {
                    // Touches beginning in the ribbon/menu never zoom the slide.
                    last = avail.contains(*pos).then_some((*pos, now));
                }
                egui::Event::Touch { phase: egui::TouchPhase::End, .. } => {
                    last = None;
                }
                // Cancel means winit recognised a two-finger gesture.
                // Keep its origin; subsequent Zoom events may have no hover.
                _ => {}
            }
        }
        let mut multi_anchor = None;
        if let Some(gesture) = multi {
            if avail.contains(gesture.start_pos) && avail.contains(gesture.center_pos) {
                multi_anchor = Some(gesture.center_pos);
                last = Some((gesture.center_pos, now));
            } else {
                last = None;
            }
        }
        let native_pinch = events.iter().any(|e| matches!(e, egui::Event::Zoom(_)));
        // Android's two-finger pan is translated by winit into a point wheel
        // event. It also clears hover, so the canvas must remember the origin.
        // A mouse/trackpad wheel alone cannot activate this without a touch.
        let native_pan = events.iter().any(|e| matches!(e,
            egui::Event::MouseWheel { unit: egui::MouseWheelUnit::Point, .. }));
        let allowed = app.dialog.is_none() && app.palette.is_none() && !app.backstage_open();
        let anchor = if allowed && (native_pinch || native_pan || multi_anchor.is_some()) {
            multi_anchor.or_else(|| {
                last.filter(|(pos, time)| avail.contains(*pos) && now >= *time && now - *time < 8.0)
                    .map(|(pos, _)| pos)
            })
        } else { None };
        // Pan only if this wheel event belongs to a touch that began on the
        // slide canvas, NOT if it belongs to the ribbon, mouse or modal.
        let touch_pan = allowed && native_pan && anchor.is_some();
        if let Some(pos) = anchor {
            last = Some((pos, now));
        }
        if !allowed { last = None; }
        ui.data_mut(|d| {
            if let Some(origin) = last { d.insert_temp(id, origin); }
            else { d.remove_temp::<(Pos2, f64)>(id); }
        });
        (anchor, touch_pan)
    };
    #[cfg(not(target_os = "android"))]
    let (touch_zoom_anchor, touch_pan_active): (Option<Pos2>, bool) = (None, false);
    // The Android backend can cancel the pointer hover for a pinch. Zoom only
    // if the original pointer is over the canvas OR a pinch began inside it.
    let zooming = (resp.hovered() || touch_zoom_anchor.is_some()) && (zoom_delta - 1.0).abs() > 1e-3;''')
    edit('canvas.rs',
        '''zooming.then_some(hover).flatten(), avail''',
        '''zooming.then_some(touch_zoom_anchor.or(hover)).flatten(), avail''')

    edit('canvas.rs',
        '''    if (resp.hovered() || on_bar) && !zooming {
        if overflow != egui::Vec2::ZERO {
            offset -= wheel;
        } else {
            wheel_navigation(app, ui, carry_id, doc_uid);
        }
    }''',
        '''    if (resp.hovered() || on_bar || touch_pan_active) && !zooming {
        if overflow != egui::Vec2::ZERO {
            #[cfg(target_os = "android")]
            let scroll_gain = if ui.input(|i| i.events.iter().any(|e|
                matches!(e, egui::Event::MouseWheel { unit: egui::MouseWheelUnit::Point, .. })
            )) { if touch_pan_active { 1.65_f32 } else { 1.95_f32 } } else { 1.0 };
            #[cfg(not(target_os = "android"))]
            let scroll_gain = 1.0_f32;
            #[cfg(target_os = "android")]
            let frame_scroll = if !touch_pan_active && scroll_gain > 1.0 {
                let key = scroll_id.with("deckcraft_trackpad_smooth");
                let (old, last_input): (egui::Vec2, f64) = ui.data_mut(|d|
                    d.get_temp(key)).unwrap_or((egui::Vec2::ZERO, 0.0));
                let now = ui.input(|i| i.time);
                // A trackpad may send large, uneven point-wheel bursts. Interpolate
                // to touchscreen-like motion, then let the last 2–5 frames
                // settle with bounded momentum. Do not synthesize page turns.
                let input = wheel * scroll_gain;
                let motion = if input != egui::Vec2::ZERO {
                    old * 0.36 + input * 0.64
                } else if now - last_input < 0.22 {
                    old * 0.72
                } else {
                    egui::Vec2::ZERO
                };
                let next = if motion.length() < 0.65 { egui::Vec2::ZERO }
                    else { egui::vec2(motion.x.clamp(-64.0, 64.0),
                                      motion.y.clamp(-64.0, 64.0)) };
                ui.data_mut(|d| d.insert_temp(key,
                    (next, if input != egui::Vec2::ZERO { now } else { last_input })));
                if next != egui::Vec2::ZERO {
                    ui.ctx().request_repaint_after(std::time::Duration::from_millis(16));
                }
                next
            } else { wheel * scroll_gain };
            #[cfg(not(target_os = "android"))]
            let frame_scroll = wheel * scroll_gain;
            offset -= frame_scroll;
        } else if !touch_pan_active {
            // A two-finger swipe over a fitted slide must not turn pages.
            wheel_navigation(app, ui, carry_id, doc_uid);
        }
    }''')

    print('DeckCraft 0.14.1: font persistence, native menus, update routing and D/C/S ported')

if __name__ == '__main__':
    apply(sys.argv[1])
