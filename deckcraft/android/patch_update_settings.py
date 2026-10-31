"""Keep Android updates app-scoped; add persisted channel and opt-in startup controls."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
def edit(name,old,new):
 p=root/name;s=p.read_text();assert s.count(old)==1,(name,old[:70]);p.write_text(s.replace(old,new,1))
java='templates/android/SafActivity.java'
edit(java,'    public void deckCheckUpdates() {','''    public void deckUpdateSettings() {
        runOnUiThread(() -> {
            android.content.SharedPreferences prefs = getSharedPreferences("deckcraft_updates", MODE_PRIVATE);
            new android.app.AlertDialog.Builder(this).setTitle("Startup Update Settings")
                .setMultiChoiceItems(new String[]{"Check for updates at startup", "Stable + Preview Releases"},
                    new boolean[]{prefs.getBoolean("startup", false), prefs.getBoolean("preview", true)},
                    (dialog, which, checked) -> prefs.edit().putBoolean(which == 0 ? "startup" : "preview", checked).apply())
                .setPositiveButton("Done", null).show();
        });
    }
    public void deckCheckUpdates() { deckCheckUpdates(false); }
    private void deckCheckUpdates(boolean startup) {''')
edit(java,'r.optBoolean("draft") || r.optBoolean("prerelease")',
     'r.optBoolean("draft") || (r.optBoolean("prerelease") && !getSharedPreferences("deckcraft_updates", MODE_PRIVATE).getBoolean("preview", true))')
edit(java,'if (!tag.startsWith("deckcraft-v") ||',
     'if (!tag.matches("deckcraft-v[0-9]+\\\\.[0-9]+\\\\.[0-9]+-android\\\\.[0-9]+") ||')
old='if (!name.startsWith("deckcraft-") || !name.contains("arm64") || !name.endsWith(".apk") || name.contains("debug") || name.contains("unsigned")) continue;'
new='''String expectedName = "deckcraft-v" + tag.substring("deckcraft-v".length()) + "-arm64-v8a.apk";
                            if (!name.equals(expectedName) || !"uploaded".equals(a.optString("state"))) continue;'''
edit(java,old,new)
edit(java,'String bestName = null;', 'String bestName = null; boolean bestPreview = false;')
edit(java,'bestName = tag; break;', 'bestName = tag; bestPreview = r.optBoolean("prerelease"); break;')
edit(java,'final String label = bestName;', 'final String label = bestName; final boolean preview = bestPreview;')
edit(java,'.setTitle("DeckCraft update found")', '.setTitle(preview ? "DeckCraft preview update" : "DeckCraft stable update")')
edit(java,'.setMessage(label + "\\nInstalled: "', '.setMessage((preview ? "Preview release\\n" : "Stable release\\n") + label + "\\nInstalled: "')
edit(java,'if (best == null) { deckMessage(', 'if (best == null) { if (!startup) deckMessage(')
edit(java,'} catch (Exception e) { deckMessage("Could not check updates.', '} catch (Exception e) { if (!startup) deckMessage("Could not check updates.')
edit(java,'runOnUiThread(() -> android.widget.Toast.makeText(this, "Checking DeckCraft updates…", android.widget.Toast.LENGTH_SHORT).show());',
     'if (!startup) runOnUiThread(() -> android.widget.Toast.makeText(this, "Checking DeckCraft updates…", android.widget.Toast.LENGTH_SHORT).show());')
edit(java,'        super.onCreate(savedInstanceState);','''        super.onCreate(savedInstanceState);
        if (getSharedPreferences("deckcraft_updates", MODE_PRIVATE).getBoolean("startup", false)) {
            deckCheckUpdates(true);
        }''')
p=root/'templates/android/saf_bridge.rs';s=p.read_text();a=s.index('        pub fn check_deckcraft_updates(');b=s.index('        pub fn request_open(',a);method=s[a:b]
p.write_text(s[:a]+method.replace('check_deckcraft_updates','deck_update_settings').replace('deckCheckUpdates','deckUpdateSettings')+s[a:])
edit('lib/build-common.sh','            if _purpose == "deckcraft-updates" {','''            if _purpose == "deck-update-settings" {
                let _ = open_bridge.deck_update_settings(); return;
            }
            if _purpose == "deckcraft-updates" {''')
ui='source/deckcraft/crates/ui-egui/src/'
edit(ui+'lib.rs','    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),','''    ("app.updateSettings", "Startup Update Settings", None, "{}"),
    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),''')
edit(ui+'app/commands.rs','            "app.importFont" => self.import_font_dialog(),','''            "app.updateSettings" => {
                if let Some(open) = self.services.open_async.as_mut() { open("deck-update-settings", 0); }
            },
            "app.importFont" => self.import_font_dialog(),''')
edit(ui+'menus.rs','("Check for Updates…", "app.checkUpdates"),','("Check for Updates…", "app.checkUpdates"), ("Startup Update Settings", "app.updateSettings"),')
