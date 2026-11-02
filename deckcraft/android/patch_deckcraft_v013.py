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
    edit('menus.rs', '("Open…", "app.openDialog"),', '("Open…", "app.openDialog"),\n                ("Import Font…", "app.importFont"),')
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
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if ui.button("×").clicked() { close = true; }
                        ui.add_space(94.0);
                        ui.heading("DeckCraft");
                    });
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
    let touch_zoom_anchor: Option<Pos2> = {
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
        let allowed = app.dialog.is_none() && app.palette.is_none() && !app.backstage_open();
        let anchor = if allowed && (native_pinch || multi_anchor.is_some()) {
            multi_anchor.or_else(|| {
                last.filter(|(pos, time)| avail.contains(*pos) && now >= *time && now - *time < 8.0)
                    .map(|(pos, _)| pos)
            })
        } else { None };
        if let Some(pos) = anchor {
            last = Some((pos, now));
        }
        if !allowed { last = None; }
        ui.data_mut(|d| {
            if let Some(origin) = last { d.insert_temp(id, origin); }
            else { d.remove_temp::<(Pos2, f64)>(id); }
        });
        anchor
    };
    #[cfg(not(target_os = "android"))]
    let touch_zoom_anchor: Option<Pos2> = None;
    // The Android backend can cancel the pointer hover for a pinch. Zoom only
    // if the original pointer is over the canvas OR a pinch began inside it.
    let zooming = (resp.hovered() || touch_zoom_anchor.is_some()) && (zoom_delta - 1.0).abs() > 1e-3;''')
    edit('canvas.rs',
        '''zooming.then_some(hover).flatten(), avail''',
        '''zooming.then_some(touch_zoom_anchor.or(hover)).flatten(), avail''')

    print('DeckCraft 0.14.1: font persistence, native menus, update routing and D/C/S ported')

if __name__ == '__main__':
    apply(sys.argv[1])
