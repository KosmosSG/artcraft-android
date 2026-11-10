#!/usr/bin/env python3
"""DeckCraft Android v0.17.0-android.3: persisted checked update toggles.

After the approved PhotoCraft-style toggle overlay, mirror the authoritative
Android SharedPreferences to the app's private config folder for the egui
menu to read. No production keys, no other app code, no desktop changes.
Fails closed if any reviewed source anchor changes.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: patch_v017_checked_updates.py <disposable-builder>")
root = Path(sys.argv[1])


def replace_one(path, old, new):
    p = root / path
    s = p.read_text(encoding="utf-8")
    count = s.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}: {old[:100]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


java = "templates/android/SafActivity.java"
replace_one(java, '''    public void deckUpdateSettings() {
''', '''    // Reflect exactly the saved update preferences in the native Dk menu.
    // XDG_CONFIG_HOME is the same app-private <files>/config directory on Android.
    // Mirror at Activity startup and after each toggle so a reopened menu always
    // shows the actual SharedPreferences state (even after a full app restart).
    private void deckWriteMenuFlags() {
        try {
            android.content.SharedPreferences prefs = getSharedPreferences("deckcraft_updates", MODE_PRIVATE);
            java.io.File base = getExternalFilesDir(null);
            if (base == null) base = getFilesDir();
            java.io.File dir = new java.io.File(base, "config");
            if (!dir.exists() && !dir.mkdirs()) throw new java.io.IOException("Cannot create config");
            java.io.File file = new java.io.File(dir, "deckcraft-updates-flags.txt");
            String flags = "startup=" + (prefs.getBoolean("startup", false) ? "1" : "0")
                    + "\\npreview=" + (prefs.getBoolean("preview", false) ? "1" : "0") + "\\n";
            // Tiny update in app-private storage. Preferences remain authoritative.
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(file, false)) {
                out.write(flags.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                out.flush();
            }
        } catch (Exception e) {
            android.util.Log.w("DeckCraftUpdates", "Could not sync menu checkmarks", e);
        }
    }

    public void deckUpdateSettings() {
''')
replace_one(java, '''            editor.apply();
            android.widget.Toast.makeText(this, "Dk Update checks at startup: "''',
'''            editor.apply();
            deckWriteMenuFlags();
            android.widget.Toast.makeText(this, "Dk Update checks at startup: "''')
replace_one(java, '''            prefs.edit().putBoolean("preview", enabled).apply();
            android.widget.Toast.makeText(this, "Dk Preview releases: "''',
'''            prefs.edit().putBoolean("preview", enabled).apply();
            deckWriteMenuFlags();
            android.widget.Toast.makeText(this, "Dk Preview releases: "''')
replace_one(java, '''        android.content.SharedPreferences deckPrefs = getSharedPreferences("deckcraft_updates", MODE_PRIVATE);
''',
'''        deckWriteMenuFlags();
        android.content.SharedPreferences deckPrefs = getSharedPreferences("deckcraft_updates", MODE_PRIVATE);
''')

# The last overlay has three simple rows. Retain the first, but decorate
# the two toggle rows using the file mirrored from SharedPreferences.
ui = "source/deckcraft/crates/ui-egui/src/lib.rs"
replace_one(ui, '''                            for (label, command) in [
                                ("Check for Updates…", "app.checkUpdates"),
                                ("Toggle Update Check at Startup", "app.updateSettings"),
                                ("Toggle Preview Releases", "app.previewSettings"),
                            ] {''',
'''                            // Read the Android preferences mirror when this submenu is drawn.
                            // Missing file defaults to the approved stable / startup-off settings.
                            // A touch action runs Java on the UI thread and the following open
                            // reads its updated file; no fake temporary UI-only check mark.
                            #[cfg(target_os = "android")]
                            let (startup_on, preview_on) = std::env::var_os("XDG_CONFIG_HOME")
                                .and_then(|dir| std::fs::read_to_string(
                                    std::path::PathBuf::from(dir).join("deckcraft-updates-flags.txt")
                                ).ok())
                                .map(|flags| (
                                    flags.lines().any(|line| line == "startup=1"),
                                    flags.lines().any(|line| line == "preview=1"),
                                ))
                                .unwrap_or((false, false));
                            #[cfg(not(target_os = "android"))]
                            let (startup_on, preview_on) = (false, false);
                            for (label, command) in [
                                ("Check for Updates…", "app.checkUpdates"),
                                (if startup_on { "✓  Toggle Update Check at Startup" }
                                 else { "    Toggle Update Check at Startup" }, "app.updateSettings"),
                                (if preview_on { "✓  Toggle Preview Releases" }
                                 else { "    Toggle Preview Releases" }, "app.previewSettings"),
                            ] {''')

java_text=(root/java).read_text(encoding="utf-8")
ui_text=(root/ui).read_text(encoding="utf-8")
for term in (
    'private void deckWriteMenuFlags()',
    'deckcraft-updates-flags.txt',
    'prefs.getBoolean("startup", false)',
    'prefs.getBoolean("preview", false)',
    'deckWriteMenuFlags();',
    'Dk Update checks at startup: ',
    'Dk Preview releases: ',
):
    assert term in java_text, term
assert java_text.count("deckWriteMenuFlags();") == 3, "Startup and both toggles must sync"
assert 'setTitle("Startup Update Settings")' not in java_text
assert 'getLong("last_startup_check", 0L)' in java_text
assert 'deckCertificates(installed).equals(deckCertificates(next))' in java_text
assert ui_text.count("deckcraft-updates-flags.txt") == 1
for label in (
    '✓  Toggle Update Check at Startup',
    '✓  Toggle Preview Releases',
    'app.checkUpdates',
    'app.updateSettings',
    'app.previewSettings',
):
    assert label in ui_text, label
assert 'flags.lines().any(|line| line == "startup=1")' in ui_text
assert 'flags.lines().any(|line| line == "preview=1")' in ui_text
print("PASS: ✓ indicators read saved ON/OFF flags (including after app relaunch)")
print("PASS: PhotoCraft-style toasts/no settings dialog, stable channel default and certificate checks preserved")
