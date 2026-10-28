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
menu = root / "source/effectcraft/crates/ui-egui/src/menus.rs"
builder = root / "lib/build-common.sh"
java = root / "templates/android/SafActivity.java"
addon = root / "tools/effectcraft/UpdaterBridge.java.inc"
rust = root / "tools/effectcraft/android_updater.rs"

def once(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"STOP: {label} changed (expected once, found {n})")
    return src.replace(old, new, 1)

m = menu.read_text()
anchor = "                        crate::widgets::menu_scroll(ui, |ui| menu_nodes(app, ui, children, &mut clicked, &mut nav, 0));"
injected = anchor + """
                        #[cfg(target_os = "android")]
                        if label == "Help" {
                            ui.separator();
                            if ui.button("Check for Updates").clicked() {
                                ui.ctx().data_mut(|d| d.insert_temp(
                                    egui::Id::new("artcraft.effectcraft.check_updates_requested"), true));
                                ui.close();
                            }
                            if ui.button("Startup Update Settings").clicked() {
                                ui.ctx().data_mut(|d| d.insert_temp(
                                    egui::Id::new("artcraft.effectcraft.update_settings_requested"), true));
                                ui.close();
                            }
                        }
                        #[cfg(target_os = "android")]
                        if label == "Window" {
                            ui.separator();
                            ui.menu_button("Fonts", |ui| {
                                for (title, key) in [
                                    ("Import Font (TTF/OTF)…", "artcraft.effectcraft.import_font"),
                                    ("Select Shared Font Folder…", "artcraft.effectcraft.select_fonts"),
                                    ("Refresh Shared Fonts", "artcraft.effectcraft.refresh_fonts"),
                                ] {
                                    if ui.button(title).clicked() {
                                        ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new(key), true));
                                        ui.close();
                                    }
                                }
                            });
                        }"""
m = once(m, anchor, injected, "EffectCraft Help menu")
menu.write_text(m)

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
    public int ecUnsavedDialog(boolean active) {
        ecDialogActive = active;
        int action = ecDialogAction.getAndSet(0);
        return active ? action : 0;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {
            int code = event.getKeyCode();
            if (ecDialogKeys.contains(code)) {
                if (event.getAction() == android.view.KeyEvent.ACTION_UP) ecDialogKeys.remove(code);
                return true;
            }
            int action = code == android.view.KeyEvent.KEYCODE_D ? 1 : code == android.view.KeyEvent.KEYCODE_C ? 2 : code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;
            if (ecDialogActive && action != 0 && event.hasNoModifiers()
                    && event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                ecDialogKeys.add(code);
                if (event.getRepeatCount() == 0) ecDialogAction.compareAndSet(0, action);
                return true;
            }
        }

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
j = once(j, '                view.clearFocus();', '                view.clearFocus();\n                artcraftRestoreCanvasFocus();', 'EffectCraft native surface focus')
j = j[:-1] + """
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
                   "        self.inner.android_capture_unsaved_dcs(ui.ctx());\\\\n        self.updates.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());\\\\n        self.inner.ui(ui, frame);\\\\n        self.updates.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());\\\\n        self.updates.ui(ui.ctx());")
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

