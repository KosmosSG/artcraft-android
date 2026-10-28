"""Extend only the staged DesignCraft launcher; upstream source stays unchanged."""
from pathlib import Path
import sys


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Reviewed launcher API changed: {old[:80]}")
    return text.replace(old, new)


def patch(root):
    path = root / "src/lib.rs"
    source = path.read_text()
    source = replace_once(source, '        self.inner.ui(ui);', '        self.inner.ui(ui);\n        if android_escape && self.inner.ui.dialog.is_none() && self.inner.ui.palette.is_none() && !egui::Popup::is_any_open(ui.ctx())\n            && ui.ctx().text_edit_focused() {\n            ui.memory_mut(|m| {\n                if let Some(focus) = m.focused() { m.surrender_focus(focus); }\n            });\n        }\n')
    source = replace_once(source, '        self.handle_clipboard_shortcuts(raw);', '        self.handle_clipboard_shortcuts(raw);\n        // Capture Escape before egui focus traversal or widget consumption.\n        // Some Android tablet keyboards report their Esc key as BrowserBack.\n        // Normalize the keyboard event before egui and app text-edit guards.\n        for event in &mut raw.events {\n            if let egui::Event::Key { key, physical_key, modifiers, .. } = event {\n                if *key == egui::Key::BrowserBack && !modifiers.any() {\n                    *key = egui::Key::Escape;\n                    *physical_key = Some(egui::Key::Escape);\n                }\n            }\n        }\n        if raw.events.iter().any(|event| matches!(event,\n            egui::Event::Key { key: egui::Key::Escape, pressed: true, repeat: false, modifiers, .. }\n                if !modifiers.any())) {\n            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.exit_typing"), true));\n        }\n')
    source = replace_once(source, '        system_fonts::install_system_fonts(ui.ctx());', '        let android_escape = ui.ctx().data_mut(|d|\n            d.remove_temp::<bool>(egui::Id::new("artcraft.exit_typing"))).unwrap_or(false);\n        if android_escape && self.inner.ui.dialog.is_none() && self.inner.ui.palette.is_none()\n            && !egui::Popup::is_any_open(ui.ctx()) && !ui.ctx().text_edit_focused()\n            && self.inner.session.active().is_some_and(|doc| doc.selection.text.is_some()) {\n            // End the engine\'s type session, not just Android\'s invisible EditText.\n            self.inner.select_tool("selection");\n            if let Err(error) = self.inner.run("text.exitToFrame", serde_json::json!({})) {\n                log::warn!("Android text exit: {error}");\n            }\n            ui.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Escape));\n        }\n        system_fonts::install_system_fonts(ui.ctx());')
    source = replace_once(source, "struct AndroidShell {", "mod tablet;\nstruct AndroidShell {\n    tablet: tablet::Tablet,")
    source = replace_once(source, "Self { inner, app, ime,", "Self { tablet: tablet::Tablet::default(), inner, app, ime,")
    source = replace_once(source, "        system_fonts::install_system_fonts(ui.ctx());", "        self.tablet.ui(ui, &mut self.inner, &self.saf_bridge, &self.saf_state);\n        system_fonts::install_system_fonts(ui.ctx());")
    source = replace_once(source, "Box::new(move |_cc| Ok(Box::new(shell)))", "Box::new(move |cc| { tablet::record_gpu(cc); Ok(Box::new(shell)) })")
    old = 'inbox.lock().unwrap_or_else(|error| error.into_inner()).push(ImportedFile { request: request.clone(), name, bytes });'
    source = replace_once(source, old, '''if request.purpose == "android-font" {
                                if let Err(error) = tablet::install_font(&name, &bytes) {
                                    log::error!("Font import: {error}");
                                    tablet::font_result(Err(error));
                                } else {
                                    tablet::font_result(Ok("Font imported".to_owned()));
                                }
                            } else {
                                ''' + old + '''
                            }''')
    source = replace_once(source, '            ("open", "ok") => {', '''            ("font_folder", status) => {
                if status == "ok" {
                    tablet::font_result(Ok(format!("Shared font folder refreshed ({} fonts)", value.get("count").and_then(serde_json::Value::as_u64).unwrap_or(0))));
                } else if status != "cancel" {
                    tablet::font_result(Err(value.get("message").and_then(serde_json::Value::as_str).unwrap_or("Shared font refresh failed").to_owned()));
                }
            }
            ("open", "ok") => {''')
    source = replace_once(source, '                    match std::fs::read(&path) {', '''                    if request.purpose == "android-font" && std::fs::metadata(&path).map(|m| m.len() > 32 * 1024 * 1024).unwrap_or(true) {
                        tablet::font_result(Err("Font file is unreadable or exceeds 32 MB".into()));
                        continue;
                    }
                    match std::fs::read(&path) {''')
    text = source
    start = text.index('        pub fn request_folder(')
    end = text.index('\n        ///', start)
    method = text[start:end].replace('request_folder', 'tablet_action').replace('safRequestFolder', 'dcAction')
    path.write_text(text[:end] + '\n' + method + text[end:])
    (root / "src/tablet.rs").write_text(Path(__file__).with_name("tablet.rs").read_text())
    java = next((root / "java").rglob("DesignCraftActivity.java"))
    text = java.read_text()
    # MagicPad: Escape must reach upstream canvas while Android's invisible
    # text-input host relinquishes focus. Never swallow a hardware key here.
    text = replace_once(text, 'public final class DesignCraftActivity extends GameActivity {', '''public final class DesignCraftActivity extends GameActivity {
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && event.getKeyCode() == android.view.KeyEvent.KEYCODE_ESCAPE
                && event.getAction() == android.view.KeyEvent.ACTION_DOWN && imeWanted && event.getRepeatCount() == 0 && event.hasNoModifiers()) {
            imeHide();
            artcraftRestoreCanvasFocus();
        }
        if (!imeWanted) artcraftRestoreCanvasFocus();
        // Bypass focused EditText/SurfaceView dispatch: GameActivity's public
        // handlers enqueue the original event (including modifiers and key-up).
        // Let the IME keep printable input while editing; Escape always reaches
        // the native editor, even if Android has already hidden its keyboard.
        if (event != null
                && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0
                && (event.getKeyCode() == android.view.KeyEvent.KEYCODE_ESCAPE
                    || (!imeWanted && !event.isSystem()))) {
            if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                super.onKeyDown(event.getKeyCode(), event);
                return true;
            }
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) {
                super.onKeyUp(event.getKeyCode(), event);
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }''')
    text = replace_once(text, '                view.clearFocus();', '                view.clearFocus();\n                artcraftRestoreCanvasFocus();')
    text = text[:text.rfind('}')] + """
    private android.view.View artcraftNativeSurface(android.view.View node) {
        if (node == null || !node.isShown()) return null;
        if (node instanceof android.view.SurfaceView) return node;
        if (node instanceof android.view.ViewGroup) {
            android.view.ViewGroup group = (android.view.ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                android.view.View child = artcraftNativeSurface(group.getChildAt(i));
                if (child != null) return child;
            }
        }
        return null;
    }
    private void artcraftRestoreCanvasFocus() {
        android.view.Window win = getWindow();
        android.view.View surface = win == null ? null : artcraftNativeSurface(win.getDecorView());
        if (surface != null && !surface.hasFocus()) {
            surface.setFocusable(true);
            surface.setFocusableInTouchMode(true);
            surface.requestFocus();
        }
    }
""" + text[text.rfind('}'):]
    text = replace_once(text, '        super.onCreate(savedInstanceState);', '''        super.onCreate(savedInstanceState);
        if (getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean("dc_startup_check", false)) dcCheckUpdates(false);
        dcRestoreSharedFontsOnStartup();''')
    text = replace_once(text, '        super.onActivityResult(requestCode, resultCode, data);', '''        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_FONT_FOLDER) {
            requestIds.remove(REQ_FONT_FOLDER);
            if (resultCode != RESULT_OK || data == null || data.getData() == null) { enqueueCancel(0, "font_folder"); return; }
            try {
                Uri tree = data.getData();
                int flags = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
                if (flags == 0) throw new SecurityException("Read access was not granted");
                getContentResolver().takePersistableUriPermission(tree, flags);
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(FONT_FOLDER_PREF, tree.toString()).apply();
                scanFontFolder(0, tree);
            } catch (Exception error) { enqueueError(0, "font_folder", error.toString()); }
            return;
        }''')
    methods = '\n    private static final int REQ_FONT_FOLDER = 0x6041;\n    private static final String FONT_FOLDER_PREF = "dc_shared_font_tree";\n'
    for filename in ('font_methods.java', 'update_methods.java'):
        methods += Path(__file__).with_name(filename).read_text() + '\n'
    index = text.rfind('}')
    java.write_text(text[:index] + methods + text[index:])
    activity_package = next(
        (line for line in text.splitlines() if line.startswith("package ")), None)
    if activity_package not in (
        "package com.artcraft.designcraft;",
        "package com.artcraft.designcraft.candidate;",
    ):
        raise ValueError("Unexpected generated DesignCraft Java package")
    # The disposable-key candidate uses a separate application ID. Its Java
    # helper must have the same package declaration as the generated Activity,
    # but the policy's production identity/security validation must NOT change.
    policy = Path(__file__).with_name("DesignCraftUpdatePolicy.java").read_text()
    policy = replace_once(policy, "package com.artcraft.designcraft;", activity_package)
    (java.parent / "DesignCraftUpdatePolicy.java").write_text(policy)
    manifest = root / 'Cargo.toml'
    manifest.write_text(manifest.read_text() + '\n[[package.metadata.android.uses_permission]]\nname = "android.permission.INTERNET"\n')


if __name__ == "__main__":
    patch(Path(sys.argv[1]))

