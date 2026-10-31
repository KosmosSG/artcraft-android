#!/usr/bin/env python3
"""Port the released Android font/menu/DCS behavior to official DeckCraft 0.13.1.

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
    edit('menus.rs', '("Normal", "view.normal"),', '("Tablet Tools", "view.tabletTools"),\n                ("Normal", "view.normal"),')
    edit('menus.rs', '("Command Palette", "app.palette")', '("Import Font…", "app.importFont"), ("Command Palette", "app.palette")')
    edit('app.rs', '        ribbon::title_bar(self, ui);', '        self.tablet_controls(ui);\n        ribbon::title_bar(self, ui);')
    tree = ast.parse((HERE / 'patch_deckcraft_tablet.py').read_text())
    tablet = next(ast.literal_eval(n.args[1].left) for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'change'
        and len(n.args) == 2 and isinstance(n.args[1], ast.BinOp))
    tablet = tablet.replace('fn tablet_controls(', 'pub(crate) fn tablet_controls(')
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
    body = body.replace('    let mut done = false;', '    let shortcut = ui.ctx().data_mut(|d| d.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))).or_else(|| crate::take_dcs(ui.ctx()));\n    let mut done = false;')
    body = body.replace('24.0))).clicked() {', '24.0))).clicked() || shortcut == Some(1) {', 1)
    close = body.index('fn dlg_close(')
    body = body[:close] + body[close:].replace('24.0))).clicked() {', '24.0))).clicked() || shortcut == Some(1) {', 1)
    body = body.replace('new("Cancel (C)").min_size(vec2(72.0, 24.0))).clicked() {', 'new("Cancel (C)").min_size(vec2(72.0, 24.0))).clicked() || shortcut == Some(2) {')
    body = body.replace('if save.clicked() ||', 'if shortcut == Some(3) || save.clicked() ||')
    body = body.replace('                if app.save_all() {', '                if app.services.android_save_close.is_some() {\n                    app.android_save_and_close(true);\n                } else if app.save_all() {')
    body = body.replace('                app.save();', '                if app.services.android_save_close.is_some() {\n                    app.android_save_and_close(false);\n                } else {\n                app.save();')
    body = body.replace('                    run(app, "file.close", json!({}));\n                }\n                done = true;', '                    run(app, "file.close", json!({}));\n                }\n                }\n                done = true;')
    p.write_text(text[:start] + body + text[end:])
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
    print('DeckCraft 0.13.1: font persistence, native menus, update routing and D/C/S ported')

if __name__ == '__main__':
    apply(sys.argv[1])
