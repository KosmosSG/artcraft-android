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
                        }"""
m = once(m, anchor, injected, "EffectCraft Help menu")
menu.write_text(m)

j = java.read_text().rstrip()
if not j.endswith("}") or "ecCheckForUpdates" in j:
    raise SystemExit("STOP: generated Java Activity template changed")
# This temporary template is used solely to generate EffectCraft's Android Activity.
j = j[:-1] + addon.read_text() + "\n}\n"
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
                   "        self.inner.ui(ui, frame);\\\\n        self.updates.ui(ui.ctx());")
        shutil.copy2(root / "tools/effectcraft/android_updater.rs",
                     staging_dir / "src/effectcraft_updater.rs")
    (staging_dir / "src" / "lib.rs").write_text(entry)'''
# Ensure the injected generator sees backslash-n escapes, not newlines within quotes.
after = after.replace("\\\\\\\\n", "\\\\n")
after = after.replace(chr(92) * 2 + "n", chr(92) + "n")
b = once(b, before, after, "EffectCraft launcher generation")
builder.write_text(b)
print("Prepared EffectCraft Help > Check for Updates, JNI updater, INTERNET permission and guarded official release links.")
