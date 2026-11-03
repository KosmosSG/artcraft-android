"""DeckCraft Android.15: accessible Dk launcher menu and safe updater handoff.

Applied AFTER all existing port, fonts, update settings, egui and GPU patches.
Preserves the branded Dk logo, individual font import, 4 GiB SAF folder cache,
startup update preferences, installed signature verification and user consent.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1])
ui=root/"source/deckcraft/crates/ui-egui/src"
java=root/"templates/android/SafActivity.java"

def edit(path, old, new):
    s=path.read_text()
    if s.count(old)!=1:
        raise ValueError(f"{path}: expected exactly one app-launcher anchor {old[:100]!r}; count={s.count(old)}")
    path.write_text(s.replace(old,new,1))

# The top-left Dk icon used to be painted into an inert allocated rectangle.
# Give that same branded icon a real button and a compact click-to-open menu.
edit(ui/"lib.rs",
    '''                    let (_, rect) = ui.allocate_space(egui::vec2(24.0, 24.0));
                    dialogs::paint_logo(ui.painter(), rect);''',
    '''                    let launcher = ui.menu_button("      ", |ui| {
                        ui.set_min_width(230.0);
                        ui.heading("DeckCraft · App Menu");
                        ui.separator();
                        for (label, command) in [
                            ("Import Fonts (TTF/OTF)…", "app.importFont"),
                            ("Select Font Folder…", "app.fontFolder"),
                            ("Refresh Fonts", "app.refreshFonts"),
                            ("", ""),
                            ("Check for Updates…", "app.checkUpdates"),
                            ("Startup Update Settings…", "app.updateSettings"),
                            ("", ""),
                            ("GPU Diagnostics…", "app.gpuDiagnostics"),
                            ("About DeckCraft", "app.about"),
                        ] {
                            if command.is_empty() { ui.separator(); continue; }
                            if ui.add_sized([230.0, 32.0], egui::Button::new(label)).clicked() {
                                let _ = self.run(command, serde_json::json!({}));
                                ui.close();
                            }
                        }
                    });
                    // The original approved icon is painted over an interactive
                    // menu button, not duplicated as text or re-masked.
                    dialogs::paint_logo(ui.painter(), launcher.response.rect.shrink(2.0));''')

# Prevent every app launch from contacting GitHub while retaining a manual
# "Check for Updates" action. Defaults remain opt-in; minimum 24h between
# startup checks, with clock rollback handled safely.
edit(java,
    '''        if (getSharedPreferences("deckcraft_updates", MODE_PRIVATE).getBoolean("startup", false)) {
            deckCheckUpdates(true);
        }''',
    '''        android.content.SharedPreferences deckPrefs = getSharedPreferences("deckcraft_updates", MODE_PRIVATE);
        long deckNow = System.currentTimeMillis();
        long deckLast = deckPrefs.getLong("last_startup_check", 0L);
        if (deckPrefs.getBoolean("startup", false) && deckNow >= deckLast &&
                deckNow - deckLast >= 24L * 60L * 60L * 1000L) {
            deckPrefs.edit().putLong("last_startup_check", deckNow).apply();
            deckCheckUpdates(true);
        }''')

# Preview releases must be an explicit choice; the stable channel is default.
s=java.read_text()
if s.count('prefs.getBoolean("preview", true)') != 1 or s.count('getBoolean("preview", true)') != 2:
    raise ValueError("Unexpected update channel defaults")
java.write_text(s.replace('getBoolean("preview", true)', 'getBoolean("preview", false)'))

# After an authenticated APK was downloaded and exported using Android SAF,
# offer the normal OS installer as a user-initiated action. Do not attempt a
# silent install or bypass the platform confirmation / app-certificate check.
edit(java,
    '''                deckMessage("Verified DeckCraft APK saved. Open it from Files to update. Keep the installed app; uninstalling removes its data.");''',
    '''                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("Verified DeckCraft update")
                    .setMessage("The APK was verified and saved. Android will ask for installation approval. " +
                        "Keep DeckCraft installed; the update must use its existing signing certificate.")
                    .setNegativeButton("Later", null)
                    .setPositiveButton("Open Android installer", (dialog, which) -> {
                        try {
                            Intent install = new Intent(Intent.ACTION_VIEW);
                            install.setDataAndType(uri, "application/vnd.android.package-archive");
                            install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                            startActivity(install);
                        } catch (Exception e) {
                            deckMessage("Could not launch Android installer. Open the verified APK from Files. " + e.getMessage());
                        }
                    }).show());''')

# Users asked for up to 5,000 files and 4 GiB: scan recursively with a hard
# accepted-font-file cap, preserving previous cached fonts if a scan stops.
edit(java,
    '''while (!pending.isEmpty() && budget.used() < DK_SCAN_LIMIT && entries < 50000) {''',
    '''while (!pending.isEmpty() && budget.used() < DK_SCAN_LIMIT && entries < 50000 && accepted < 5000) {''')
edit(java,
    '''if (++entries > 50000 || budget.used() >= DK_SCAN_LIMIT) { limited = true; break; }''',
    '''if (++entries > 50000 || budget.used() >= DK_SCAN_LIMIT || accepted >= 5000) { limited = true; break; }''')
edit(java,
    '''limited |= !pending.isEmpty() || budget.used() >= DK_SCAN_LIMIT || entries >= 50000;''',
    '''limited |= !pending.isEmpty() || budget.used() >= DK_SCAN_LIMIT || entries >= 50000 || accepted >= 5000;''')

print("PASS: Dk launcher controls, preserved SAF fonts, opt-in daily updates, verified OS installer handoff")
