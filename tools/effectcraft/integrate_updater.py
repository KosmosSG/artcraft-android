#!/usr/bin/env python3
"""Stage PhotoCraft-style EffectCraft update UI in a TEMPORARY Android checkout.

Run after prepare_candidate.py and before build.sh. It is deliberately fail-closed
on source/template changes. No other app's repo files are changed or committed.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: integrate_updater.py <builder-root>")
root = Path(sys.argv[1]).resolve()
from patch_unsaved_dcs import apply as apply_unsaved_dcs
apply_unsaved_dcs(root / "source/effectcraft")
from patch_font_catalog import apply as apply_font_catalog
apply_font_catalog(root / "source/effectcraft")
from font_paths import patch_android_font_paths
font_template = root / "templates/android/system_fonts.rs"
font_template.write_text(patch_android_font_paths(font_template.read_text()))
from v020_compat import menu_path_and_anchor
menu, menu_anchor = menu_path_and_anchor(root / "source/effectcraft")
builder = root / "lib/build-common.sh"
java = root / "templates/android/SafActivity.java"
addon = root / "tools/effectcraft/UpdaterBridge.java.inc"
rust = root / "tools/effectcraft/android_updater.rs"

def once(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"STOP: {label} changed (expected once, found {n})")
    return src.replace(old, new, 1)

# Keep upstream File / Window / Help unchanged; use the existing top-left Ec icon.
from menu_corner import patch_header
patch_header(root / "source/effectcraft")

j = java.read_text().rstrip()
if not j.endswith("}") or "ecCheckForUpdates" in j:
    raise SystemExit("STOP: generated Java Activity template changed")
# Only this EffectCraft-only temporary builder template is patched. A physical
# Escape retains the upstream editor event and restores canvas focus after IME
# input; ordinary letters and Chinese composition are left completely alone.
declarations = [f'public final class __CLASS__ extends {base} {{'
                for base in ('NativeActivity', 'GameActivity')]
matched = [declaration for declaration in declarations if j.count(declaration) == 1]
if len(matched) != 1 or 'boolean dispatchKeyEvent(' in j:
    raise SystemExit('STOP: unsupported or already patched EffectCraft Activity')
j = once(j, matched[0], matched[0] + '''
    private final java.util.concurrent.atomic.AtomicInteger ecDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean ecDialogActive;
    private final java.util.HashSet<Integer> ecDialogKeys = new java.util.HashSet<>();
    private final java.util.HashSet<Integer> ecCtrlKeys = new java.util.HashSet<>();
    private final java.util.concurrent.ConcurrentLinkedQueue<Integer> ecPhysicalShortcuts =
        new java.util.concurrent.ConcurrentLinkedQueue<>();
    /** Physical Ctrl+W (1) / Ctrl+Q (2), routed to the native guarded menu. */
    public int ecPollPhysicalShortcut() {
        Integer action = ecPhysicalShortcuts.poll();
        return action == null ? 0 : action.intValue();
    }
    private boolean ecConsumePhysicalShortcut(android.view.KeyEvent event) {
        if (event == null || (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) != 0)
            return false;
        int code = event.getKeyCode();
        if (ecCtrlKeys.contains(code)) {
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) ecCtrlKeys.remove(code);
            return true;
        }
        int action = code == android.view.KeyEvent.KEYCODE_W ? 1 :
                     code == android.view.KeyEvent.KEYCODE_Q ? 2 : 0;
        if (action == 0 || ecDialogActive || !event.isCtrlPressed()
                || event.isShiftPressed() || event.isAltPressed() || event.isMetaPressed())
            return false;
        if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
            if (ecCtrlKeys.add(code) && event.getRepeatCount() == 0)
                ecPhysicalShortcuts.offer(action);
            return true;
        }
        return false;
    }
    private boolean ecConsumeDialogKey(android.view.KeyEvent event) {
        if (event == null || (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) != 0)
            return false;
        int code = event.getKeyCode();
        if (ecDialogKeys.contains(code)) {
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) ecDialogKeys.remove(code);
            return true;
        }
        int action = code == android.view.KeyEvent.KEYCODE_D ? 1 :
                     (code == android.view.KeyEvent.KEYCODE_C || code == android.view.KeyEvent.KEYCODE_ESCAPE) ? 2 :
                     code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;
        if (!ecDialogActive || action == 0 || !event.hasNoModifiers()) return false;
        if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
            ecDialogKeys.add(code);
            if (event.getRepeatCount() == 0) ecDialogAction.compareAndSet(0, action);
            return true;
        }
        return false;
    }
    public int ecUnsavedDialog(boolean active) {
        boolean appeared = active && !ecDialogActive;
        ecDialogActive = active;
        if (appeared) {
            // Close Android's hidden EditText/IME before handing D/C/S to the modal.
            // The project text remains intact; the native editor commits it separately.
            imeHide();
            runOnUiThread(this::artcraftRestoreCanvasFocus);
        }
        int action = ecDialogAction.getAndSet(0);
        return active ? action : 0;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        // Intercept physical shortcuts even when the invisible IME view owns focus.
        if (ecConsumeDialogKey(event) || ecConsumePhysicalShortcut(event)) return true;

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
    }''', "EffectCraft physical Escape passthrough")
# NativeActivity delivers keys through dispatchKeyEvent, not Activity.onKeyDown.
if 'extends NativeActivity' in matched[0]:
    start = j.index("        // Bypass focused EditText/SurfaceView dispatch:")
    end = j.index("        return super.dispatchKeyEvent(event);", start)
    j = j[:start] + j[end:]
# Guard the IME itself as well: some Android keyboard drivers send keys via
# InputConnection rather than dispatchKeyEvent, particularly while typing.
j = once(j, '    public void imeShow() {\n', '    public void imeShow() {\n        if (ecDialogActive) return;\n', 'EffectCraft modal IME suppression')
j = once(j, '                        public boolean commitText(CharSequence text, int newCursorPosition) {',
    '                        public boolean commitText(CharSequence text, int newCursorPosition) {\n                            if (ecDialogActive) return true;',
    'EffectCraft modal no text commits')
j = once(j, '                        public boolean setComposingText(CharSequence text, int newCursorPosition) {',
    '                        public boolean setComposingText(CharSequence text, int newCursorPosition) {\n                            if (ecDialogActive) return true;',
    'EffectCraft modal no composing')
j = once(j, '                        public boolean deleteSurroundingText(int beforeLength, int afterLength) {',
    '                        public boolean deleteSurroundingText(int beforeLength, int afterLength) {\n                            if (ecDialogActive) return true;',
    'EffectCraft modal no deletion')
j = once(j, '                        public boolean sendKeyEvent(KeyEvent event) {',
    '                        public boolean sendKeyEvent(KeyEvent event) {\n                            if (ecConsumeDialogKey(event) || ecConsumePhysicalShortcut(event)) return true;',
    'EffectCraft IME keyboard routing')
j = once(j, '                view.clearFocus();', '                view.clearFocus();\n                artcraftRestoreCanvasFocus();', 'EffectCraft native surface focus')
j = j[:-1] + """
    @Override protected void onDestroy() {
        android.util.Log.i("EffectCraftLifecycle", "Activity onDestroy finishing=" + isFinishing());
        super.onDestroy();
        android.util.Log.i("EffectCraftLifecycle", "Activity onDestroy completed");
    }
    private android.view.View artcraftNativeSurface(android.view.View node) {
        if (node == null || !node.isShown()) return null;
        if (node instanceof android.view.SurfaceView
                || node.getClass().getName().equals("android.app.NativeActivity$NativeContentView")) return node;
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
""" + '\n}'
# This temporary template is used solely to generate EffectCraft's Android Activity.
j = j[:-1] + addon.read_text() + (root / "tools/effectcraft/FontsBridge.java.inc").read_text() + "\n}\n"
j = once(j, "        super.onActivityResult(requestCode, resultCode, data);", "        super.onActivityResult(requestCode, resultCode, data);\n        if (ecFontActivityResult(requestCode, resultCode, data)) return;", "font picker callback")
java.write_text(j)

b = builder.read_text()
before = '    (staging_dir / "Cargo.toml").write_text(manifest)'
after = '''    if app == "effectcraft":
        # Only EffectCraft needs network access for the manual GitHub release check.
        manifest += '\\\\n[[package.metadata.android.uses_permission]]\\\\nname = "android.permission.INTERNET"\\\\n'
        tomllib.loads(manifest)
    (staging_dir / "Cargo.toml").write_text(manifest)'''
# Python string above is injected into another Python program. Write literal
# backslash-n escapes to the generator, not physical newlines inside the quote.
after = after.replace("'\\\\\\\\n", "'\\\\n").replace("permission]]\\\\\\\\n", "permission]]\\\\n")
after = after.replace(chr(92) * 2 + "n", chr(92) + "n")
b = once(b, before, after, "Android manifest generator")

before = '    (staging_dir / "src" / "lib.rs").write_text(entry)'
after = '''    if app == "effectcraft":
        # Changes apply solely to the fully rendered EffectCraft launcher.
        def replace_ec(old, new):
            global entry
            if entry.count(old) != 1:
                raise SystemExit("STOP: EffectCraft UI launcher template changed: " + old[:60])
            entry = entry.replace(old, new, 1)
        replace_ec("mod system_fonts;",
                   "mod effectcraft_updater;\\\\nmod system_fonts;")
        replace_ec("    inner: EffectcraftApp,\\\\n    app: AndroidApp,",
                   "    inner: EffectcraftApp,\\\\n    updates: effectcraft_updater::Updater,\\\\n    app: AndroidApp,")
        replace_ec("let ime = ime_bridge::ime::ImeBridge::new(&app);",
                   "let updates = effectcraft_updater::Updater::new(&app);\\\\n        let ime = ime_bridge::ime::ImeBridge::new(&app);")
        replace_ec("Self { inner, app, ime,", "Self { inner, updates, app, ime,")
        replace_ec("        self.inner.logic(ctx, frame);",
                   "        self.updates.poll(ctx);\\\\n        self.inner.logic(ctx, frame);")
        replace_ec("        self.inner.ui(ui, frame);",
                   """        self.updates.keyboard_shortcuts(&mut self.inner, ui.ctx());\\n        if self.inner.android_unsaved_dcs_active() && self.inner.session.state.text_edit.is_some() {\\n            if let Err(error) = self.inner.session.execute("text.endEdit", serde_json::json!({})) {\\n                log::warn!("EffectCraft modal text commit: {error}");\\n            }\\n            ui.memory_mut(|m| { if let Some(focus) = m.focused() { m.surrender_focus(focus); } });\\n        }\\n        self.inner.android_capture_unsaved_dcs(ui.ctx());\\\\n        self.updates.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());\\\\n        self.inner.ui(ui, frame);\\\\n        self.updates.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());\\\\n        self.updates.ui(ui.ctx(), &mut self.inner.ui.start_screen);""")
        replace_ec('        self.handle_clipboard_shortcuts(raw);', '        self.handle_clipboard_shortcuts(raw);\\n        // Some Android tablet keyboards report their Esc key as BrowserBack.\\n        // Normalize the keyboard event before egui and app text-edit guards.\\n        for event in &mut raw.events {\\n            if let egui::Event::Key { key, physical_key, modifiers, .. } = event {\\n                if *key == egui::Key::BrowserBack && !modifiers.any() {\\n                    *key = egui::Key::Escape;\\n                    *physical_key = Some(egui::Key::Escape);\\n                }\\n            }\\n        }\\n        if raw.events.iter().any(|event| matches!(event,\\n            egui::Event::Key { key: egui::Key::Escape, pressed: true, repeat: false, modifiers, .. }\\n                if !modifiers.any())) {\\n            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.exit_typing"), true));\\n        }\\n')
        replace_ec('        self.inner.ui(ui, frame);', '        let android_escape = ui.ctx().data_mut(|d|\\n            d.remove_temp::<bool>(egui::Id::new("artcraft.exit_typing"))).unwrap_or(false);\\n        if android_escape && self.inner.dialog.is_none() && !egui::Popup::is_any_open(ui.ctx())\\n            && self.inner.session.state.text_edit.is_some()\\n            {\\n            if let Err(error) = self.inner.session.execute("text.endEdit", serde_json::json!({})) {\\n                log::warn!("Android text exit: {error}");\\n            }\\n            ui.memory_mut(|m| { if let Some(focus) = m.focused() { m.surrender_focus(focus); } });\\n            ui.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Escape));\\n        }\\n        self.inner.ui(ui, frame);\\n        if android_escape && self.inner.dialog.is_none() && !egui::Popup::is_any_open(ui.ctx())\\n            && ui.ctx().text_edit_focused() {\\n            ui.memory_mut(|m| {\\n                if let Some(focus) = m.focused() { m.surrender_focus(focus); }\\n            });\\n        }\\n')
        shutil.copy2(root / "tools/effectcraft/android_updater.rs",
                     staging_dir / "src/effectcraft_updater.rs")
        import runpy
        runpy.run_path(str(root / "tools/effectcraft/launcher_icon.py"))["generate"](
            root / "tools/effectcraft/icon/ec-approved-512.png", staging_dir / "res")
    (staging_dir / "src" / "lib.rs").write_text(entry)''' 
# Ensure the injected generator sees backslash-n escapes, not newlines within quotes.
after = after.replace("\\\\\\\\n", "\\\\n")
after = after.replace(chr(92) * 2 + "n", chr(92) + "n")
b = once(b, before, after, "EffectCraft launcher generation")
builder.write_text(b)
print("Prepared EffectCraft Help > Check for Updates, JNI updater, INTERNET permission and guarded official release links.")

