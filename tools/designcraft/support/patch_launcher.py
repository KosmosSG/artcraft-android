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
    source = replace_once(source, "struct AndroidShell {", "mod tablet;\nstruct AndroidShell {\n    tablet: tablet::Tablet,")
    source = replace_once(source, "        self.ime.poll(raw);", '''        self.ime.poll(raw);
        // Physical Escape releases a genuinely focused egui editor; the
        // original shortcut and modal handlers still receive Escape.
        let android_escape_from_text = raw.events.iter().any(|event| matches!(event,
            egui::Event::Key { key: egui::Key::Escape, pressed: true, repeat: false, modifiers, .. }
                if !modifiers.command && !modifiers.alt))
            && (ctx.text_edit_focused() || self.inner.canvas_ime());
        if android_escape_from_text {
            // A transient Android-only dismissal: keep Window > Contextual Task Bar
            // enabled, but hide the HUD until the next canvas pointer selection.
            ctx.data_mut(|data| data.insert_temp(
                egui::Id::new("designcraft.android.escape_hide_taskbar"), true));
            if ctx.text_edit_focused() {
                ctx.memory_mut(|memory| {
                    if let Some(id) = memory.focused() { memory.surrender_focus(id); }
                });
            }
        }''')
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
        }
        return super.dispatchKeyEvent(event);
    }''')
    text = replace_once(text, '                view.clearFocus();', '''                view.clearFocus();
                // Release the hidden IME host after Escape and restore physical
                // shortcut focus to GameActivity's actual visible surface.
                android.view.Window win = getWindow();
                android.view.View content = win == null ? null :
                        win.getDecorView().findViewById(android.R.id.content);
                if (content instanceof android.view.ViewGroup) {
                    android.view.ViewGroup group = (android.view.ViewGroup) content;
                    for (int i = 0; i < group.getChildCount(); i++) {
                        android.view.View child = group.getChildAt(i);
                        if (child != view && child.isShown()) {
                            child.setFocusable(true);
                            child.setFocusableInTouchMode(true);
                            if (child.requestFocus()) break;
                        }
                    }
                }''')
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
    (java.parent / "DesignCraftUpdatePolicy.java").write_text(
        Path(__file__).with_name("DesignCraftUpdatePolicy.java").read_text())
    manifest = root / 'Cargo.toml'
    manifest.write_text(manifest.read_text() + '\n[[package.metadata.android.uses_permission]]\nname = "android.permission.INTERNET"\n')


if __name__ == "__main__":
    patch(Path(sys.argv[1]))

