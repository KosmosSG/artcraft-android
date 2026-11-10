#!/usr/bin/env python3
"""DeckCraft Android v0.17.0-android.2: PhotoCraft-style startup update toggles.

Apply after the approved Android.3 overlays and compact Dk menu in the disposable
CI builder checkout. Leave protected published sources, release credentials and
all other apps untouched. Fail closed if a previous integration anchor drifts.
"""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: patch_v017_photocraft_updates.py <disposable-builder>")
root = Path(sys.argv[1])


def replace_one(rel, old, new):
    path = root / rel
    value = path.read_text(encoding="utf-8")
    hits = value.count(old)
    if hits != 1:
        raise RuntimeError(f"{rel}: expected one approved anchor, found {hits}: {old[:110]!r}")
    path.write_text(value.replace(old, new, 1), encoding="utf-8")


# Replace the Android system settings modal with immediate, persisted,
# PhotoCraft-style toggles and native bottom toast feedback. Stable channel
# remains the default; preview releases remain a separate explicit opt-in.
java_path = root / "templates/android/SafActivity.java"
java = java_path.read_text(encoding="utf-8")
settings = re.compile(
    r'    public void deckUpdateSettings\(\) \{\n.*?    \}\n(?=    public void deckCheckUpdates\(\))',
    re.DOTALL,
)
new_settings = """    // The Dk > App Updates menu behaves like PhotoCraft: no modal dialog.
    // Java Toast is the platform's bottom app-icon feedback pill on Android.
    public void deckUpdateSettings() {
        runOnUiThread(() -> {
            android.content.SharedPreferences prefs = getSharedPreferences("deckcraft_updates", MODE_PRIVATE);
            boolean enabled = !prefs.getBoolean("startup", false);
            android.content.SharedPreferences.Editor editor = prefs.edit().putBoolean("startup", enabled);
            // Turning checks on should allow one check at the next app launch,
            // without changing the existing 24-hour throttle after that.
            if (enabled) editor.putLong("last_startup_check", 0L);
            editor.apply();
            android.widget.Toast.makeText(this, "Dk Update checks at startup: " + (enabled ? "ON" : "OFF"),
                    android.widget.Toast.LENGTH_SHORT).show();
        });
    }

    // Keep the existing stable/preview channel setting without a floating window.
    public void deckPreviewSettings() {
        runOnUiThread(() -> {
            android.content.SharedPreferences prefs = getSharedPreferences("deckcraft_updates", MODE_PRIVATE);
            boolean enabled = !prefs.getBoolean("preview", false);
            prefs.edit().putBoolean("preview", enabled).apply();
            android.widget.Toast.makeText(this, "Dk Preview releases: " + (enabled ? "ON" : "OFF"),
                    android.widget.Toast.LENGTH_SHORT).show();
        });
    }
"""
java, count = settings.subn(lambda _: new_settings, java)
if count != 1:
    raise RuntimeError(f"Expected one DeckCraft Startup Update Settings dialog; found {count}")
java_path.write_text(java, encoding="utf-8")

# Reuse the already-reviewed JNI bridge structure; only the new method and
# purpose differ. Both calls run Java UI changes on its main thread.
bridge_path = root / "templates/android/saf_bridge.rs"
bridge = bridge_path.read_text(encoding="utf-8")
match = re.search(
    r'        pub fn deck_update_settings\(&self\) -> Result<\(\), String> \{\n.*?\n        \}\n\n',
    bridge,
    re.DOTALL,
)
if match is None or bridge.count("pub fn deck_update_settings(") != 1:
    raise RuntimeError("Reviewed DeckCraft settings JNI bridge changed")
existing = match.group()
preview_bridge = (
    existing.replace("deck_update_settings", "deck_preview_settings")
    .replace("deckUpdateSettings", "deckPreviewSettings")
)
if "deck_preview_settings" in bridge:
    raise RuntimeError("Preview toggle JNI bridge already exists")
bridge_path.write_text(
    bridge[:match.end()] + preview_bridge + bridge[match.end():],
    encoding="utf-8",
)

replace_one(
    "lib/build-common.sh",
    '''            if _purpose == "deck-update-settings" {
                let _ = open_bridge.deck_update_settings(); return;
            }
''',
    '''            if _purpose == "deck-update-settings" {
                let _ = open_bridge.deck_update_settings(); return;
            }
            if _purpose == "deck-update-preview" {
                let _ = open_bridge.deck_preview_settings(); return;
            }
''',
)

ui_dir = "source/deckcraft/crates/ui-egui/src/"
replace_one(
    ui_dir + "lib.rs",
    '''    ("app.updateSettings", "Startup Update Settings", None, "{}"),''',
    '''    ("app.updateSettings", "Toggle Update Check at Startup", None, "{}"),
    ("app.previewSettings", "Toggle Preview Releases", None, "{}"),''',
)
replace_one(
    ui_dir + "app/commands.rs",
    '''            "app.updateSettings" => {
                if let Some(open) = self.services.open_async.as_mut() { open("deck-update-settings", 0); }
            },''',
    '''            "app.updateSettings" => {
                if let Some(open) = self.services.open_async.as_mut() { open("deck-update-settings", 0); }
            },
            "app.previewSettings" => {
                if let Some(open) = self.services.open_async.as_mut() { open("deck-update-preview", 0); }
            },''',
)
replace_one(
    ui_dir + "menus.rs",
    '''("Check for Updates…", "app.checkUpdates"), ("Startup Update Settings", "app.updateSettings"),''',
    '''("Check for Updates…", "app.checkUpdates"), ("Toggle Update Check at Startup", "app.updateSettings"), ("Toggle Preview Releases", "app.previewSettings"),''',
)
replace_one(
    ui_dir + "lib.rs",
    '''                                ("Check for Updates…", "app.checkUpdates"),
                                ("Startup Update Settings…", "app.updateSettings"),''',
    '''                                ("Check for Updates…", "app.checkUpdates"),
                                ("Toggle Update Check at Startup", "app.updateSettings"),
                                ("Toggle Preview Releases", "app.previewSettings"),''',
)

java = java_path.read_text(encoding="utf-8")
ui = (root / ui_dir / "lib.rs").read_text(encoding="utf-8")
commands = (root / ui_dir / "app/commands.rs").read_text(encoding="utf-8")
bridge = bridge_path.read_text(encoding="utf-8")
shell = (root / "lib/build-common.sh").read_text(encoding="utf-8")
assert java.count("public void deckUpdateSettings()") == 1
assert java.count("public void deckPreviewSettings()") == 1
assert 'setTitle("Startup Update Settings")' not in java
assert '"Dk Update checks at startup: "' in java
assert '"Dk Preview releases: "' in java
assert 'getBoolean("startup", false)' in java
assert 'getBoolean("preview", false)' in java
assert 'getLong("last_startup_check", 0L)' in java
assert "24L * 60L * 60L * 1000L" in java
assert 'app.checkUpdates' in ui
assert 'app.previewSettings' in ui and 'app.previewSettings' in commands
assert ui.count('("Toggle Update Check at Startup", "app.updateSettings")') == 1
assert ui.count('("Toggle Preview Releases", "app.previewSettings")') == 1
assert 'deck_preview_settings' in bridge and 'deck-preview-toggle' not in shell
assert 'open_bridge.deck_preview_settings()' in shell
assert 'deck-preview' not in shell or 'deck-update-preview' in shell
assert 'deckCertificates(installed).equals(deckCertificates(next))' in java
print("PASS: PhotoCraft-style Dk update submenu, immediate ON/OFF bottom toasts, no startup dialog")
print("PASS: persisted stable/preview choice, 24-hour throttle, certificate validation and original update installer")
