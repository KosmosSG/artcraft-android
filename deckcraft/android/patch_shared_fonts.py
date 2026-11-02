"""Wire read-only 4 GiB SAF scanning to DeckCraft's lazy font catalog."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);here=Path(__file__).parent

def edit(path,old,new):
    p=root/path;s=p.read_text()
    if s.count(old)!=1:raise ValueError(f'{path}: anchor drift {old[:60]}')
    p.write_text(s.replace(old,new,1))

edit('templates/android/SafActivity.java','    private static final String TAG = "__TAG__";',
     '    static ' + (here/'FontScanBudget.java').read_text() + '\n' + (here/'shared_fonts.java.inc').read_text()+'\n    private static final String TAG = "__TAG__";')
edit('templates/android/SafActivity.java','        super.onActivityResult(requestCode, resultCode, data);',
     '        super.onActivityResult(requestCode, resultCode, data);\n        if (deckFontFolderResult(requestCode, resultCode, data)) return;')
edit('templates/android/SafActivity.java','        super.onDestroy();','        dkFontWorker.shutdown();\n        super.onDestroy();')
p=root/'templates/android/saf_bridge.rs';s=p.read_text()
a=s.index('        pub fn check_deckcraft_updates(');b=s.index('        pub fn request_open(',a)
method=s[a:b]
p.write_text(s[:a]+method.replace('check_deckcraft_updates','deck_choose_font_folder').replace('deckCheckUpdates','deckChooseFontFolder')+method.replace('check_deckcraft_updates','deck_refresh_fonts').replace('deckCheckUpdates','deckRefreshFonts')+s[a:])
edit('lib/build-common.sh','            if _purpose == "deckcraft-updates" {', '''            if _purpose == "deck-font-folder" {
                let _ = open_bridge.deck_choose_font_folder(); return;
            }
            if _purpose == "deck-font-refresh" {
                let _ = open_bridge.deck_refresh_fonts(); return;
            }
            if _purpose == "deckcraft-updates" {''')
p=root/'lib/build-common.sh';s=p.read_text();a=s.index('    "deckcraft": {');b=s.index('    "gridcraft": {',a);part=s[a:b]
anchor='        match (kind, status) {'
assert part.count(anchor)==1
part=part.replace(anchor,'''        if kind == "deck-fonts" {
            let message = value.get("message").and_then(serde_json::Value::as_str).unwrap_or("Font scan finished").to_owned();
            let inbox = inbox.clone();
            std::thread::spawn(move || {
                let count = deckcraft_ui_egui::android_refresh_font_catalog();
                inbox.lock().unwrap_or_else(|e| e.into_inner()).push(InboxEvent::AndroidFontsScanned { message: format!("{message} {count} cataloged faces.") });
            });
            continue;
        }
'''+anchor);p.write_text(s[:a]+part+s[b:])
ui='source/deckcraft/crates/ui-egui/src/'
edit(ui+'services.rs','pub enum InboxEvent {','pub enum InboxEvent {\n    AndroidFontsScanned { message: String },')
edit(ui+'app/files.rs','                InboxEvent::Cancelled { id } =>', '''                InboxEvent::AndroidFontsScanned { message } => {
                    self.textures = crate::textures::Textures::default();
                    self.notify(message);
                },
                InboxEvent::Cancelled { id } =>''')
edit(ui+'lib.rs','    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),','''    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),
    ("app.fontFolder", "Select Shared Font Folder…", None, "{}"),
    ("app.refreshFonts", "Refresh Shared Fonts", None, "{}"),''')
edit(ui+'app/commands.rs','            "app.importFont" => self.import_font_dialog(),','''            "app.importFont" => self.import_font_dialog(),
            "app.fontFolder" | "app.refreshFonts" => {
                if let Some(open) = self.services.open_async.as_mut() {
                    open(if id == "app.fontFolder" { "deck-font-folder" } else { "deck-font-refresh" }, 0);
                } else { self.notify("Shared folders require the Android host"); }
            },''')
edit(ui+'menus.rs','("Import Font…", "app.importFont"), ("Command Palette", "app.palette")',
     '("Import Font…", "app.importFont"), ("Select Shared Font Folder…", "app.fontFolder"), ("Refresh Shared Fonts", "app.refreshFonts"), ("Command Palette", "app.palette")')
p=root/(ui+'lib.rs');p.write_text(p.read_text()+'''
#[cfg(not(target_arch = "wasm32"))]
pub fn android_refresh_font_catalog() -> usize {
    deckcraft_fonts::FontDb::global().load_system_fonts()
}
''')
# Cache files are cataloged lazily, so a 4 GiB folder is never retained as font byte vectors.
edit('source/deckcraft/crates/fonts/src/fontdb.rs','    let home = std::env::var_os("HOME").map(std::path::PathBuf::from);','''    #[cfg(target_os = "android")]
    if let Some(root) = std::env::var_os("DECKCRAFT_FONT_IMPORT_ROOT") {
        dirs.push(std::path::PathBuf::from(root).join("DeckCraft/shared-fonts"));
    }
    let home = std::env::var_os("HOME").map(std::path::PathBuf::from);''')
