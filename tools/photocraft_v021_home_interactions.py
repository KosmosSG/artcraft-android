#!/usr/bin/env python3
"""PhotoCraft Android Home-only tap and HTTPS browser-link repair.

Apply only to an ephemeral v0.21.0 Android test checkout AFTER all existing
preserved overlays. Never touch production, signing, other UI or gesture paths.
Fail closed if upstream or Android adapter anchors change.
"""
from pathlib import Path
import argparse
import subprocess

PIN = "efb7ebd0c0dab1fc108ee4642aa47c22694271a8"

def patch(path: Path, old: str, new: str) -> None:
    src = path.read_text(encoding="utf-8")
    count = src.count(old)
    if count != 1:
        raise RuntimeError(f"Home repair aborted, anchor drift: {path} {old[:90]!r} count={count}")
    path.write_text(src.replace(old, new, 1), encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    args = parser.parse_args()
    upstream_sha = subprocess.check_output(
        ["git", "-C", str(args.upstream), "rev-parse", "HEAD"], text=True).strip()
    if upstream_sha != PIN:
        raise RuntimeError("Home repair requires exact official v0.21.0 release")

    start = args.upstream / "crates/ui-egui/src/canvas/start_screen.rs"
    rust = args.adapter / "src/lib.rs"
    java = args.adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"

    # Android browser links: upstream links.rs uses Services.open_url, which
    # the Android shell omitted. JNI hands HTTPS URLs to ACTION_VIEW.
    patch(java, "    public String pcFilesDir() { return appStorageDir().getAbsolutePath(); }",
'''    /** Launch the upstream PhotoCraft community links in the device browser. */
    public void pcOpenExternalUrl(String url) {
        if (url == null) return;
        Uri uri = Uri.parse(url);
        String host = uri.getHost();
        if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null
                || !("getartcraft.com".equalsIgnoreCase(host)
                  || "www.getartcraft.com".equalsIgnoreCase(host)
                  || "github.com".equalsIgnoreCase(host)
                  || "discord.gg".equalsIgnoreCase(host))) {
            Log.w(TAG, "Refusing unsupported external URL");
            return;
        }
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                intent.addCategory(Intent.CATEGORY_BROWSABLE);
                startActivity(intent);
            } catch (android.content.ActivityNotFoundException | SecurityException error) {
                Log.e(TAG, "Could not launch an external browser", error);
                android.widget.Toast.makeText(this, "No browser available",
                        android.widget.Toast.LENGTH_SHORT).show();
            }
        });
    }

    public String pcFilesDir() { return appStorageDir().getAbsolutePath(); }''')

    patch(rust, '    fn request_open(&self, id: u64, multiple: bool) -> Result<(), String> {',
'''    /// Open the upstream Home-screen Learn/Website/Discord/GitHub links on Android.
    fn open_external_url(&self, url: &str) -> Result<(), String> {
        if !url.starts_with("https://") {
            return Err("Only HTTPS browser links are supported".into());
        }
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let text = env.new_string(url)?;
            let text_obj = JObject::from(text);
            env.call_method(&*activity, jni_str!("pcOpenExternalUrl"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&text_obj)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn request_open(&self, id: u64, multiple: bool) -> Result<(), String> {''')
    patch(rust, '    let write_bridge = bridge.clone_for_services();',
'''    let url_bridge = bridge.clone_for_services();
    let write_bridge = bridge.clone_for_services();''')
    patch(rust, '        inbox: Some(inbox),',
'''        inbox: Some(inbox),
        open_url: Some(Box::new(move |url: &str| url_bridge.open_external_url(url))),''')

    # A one-finger touchscreen tap on the *visible* Open button may fail even
    # though the platform delivered raw Touch events (several MagicOS variants
    # synthesize a mouse click only off-centre). Independently recognize a
    # stationary touch Begin/End entirely inside the same button. This affects
    # only the Home Open control, not New, menus, canvas, stylus or shortcuts.
    patch(start, 'use super::{PhotocraftApp, Rect, Sense};',
'''use super::{PhotocraftApp, Rect, Sense};

#[cfg(target_os = "android")]
fn artcraft_home_open_touch(ui: &egui::Ui, rect: Rect) -> bool {
    let ctx = ui.ctx();
    let key = egui::Id::new("artcraft_home_open_touch");
    let mut began = ctx.data_mut(|d|
        d.get_temp::<Option<(egui::TouchId, egui::Pos2)>>(key).flatten());
    let mut activate = false;
    ctx.input(|input| {
        for event in &input.events {
            let egui::Event::Touch { id, phase, pos, .. } = event else { continue };
            match phase {
                egui::TouchPhase::Start => {
                    // A second finger cancels the pending click.
                    began = if began.is_none() && rect.contains(*pos) {
                        Some((*id, *pos))
                    } else { None };
                }
                egui::TouchPhase::Move => {
                    if began.is_some_and(|(active, origin)|
                        active == *id && origin.distance_sq(*pos) > 144.0) {
                        began = None;
                    }
                }
                egui::TouchPhase::End => {
                    if let Some((active, origin)) = began {
                        if active == *id {
                            activate = rect.contains(*pos)
                                && origin.distance_sq(*pos) <= 144.0;
                            began = None;
                        }
                    }
                }
                egui::TouchPhase::Cancel => began = None,
            }
        }
    });
    ctx.data_mut(|d| d.insert_temp(key, began));
    activate
}
''')
    # Apply to rail-only Open button, not the narrow-layout row or canvas.
    old='''    if open_resp.clicked() {
        let _ = app.open_dialog_file();
    }

    ui.add_space(16.0);'''
    new='''    #[cfg(target_os = "android")]
    let touch_tapped = artcraft_home_open_touch(ui, open_rect);
    #[cfg(not(target_os = "android"))]
    let touch_tapped = false;
    if open_resp.clicked() || touch_tapped {
        let _ = app.open_dialog_file();
    }

    ui.add_space(16.0);'''
    patch(start, old, new)

    assert java.read_text().count('public void pcOpenExternalUrl(String url)') == 1
    assert rust.read_text().count('open_url: Some(Box::new(move |url: &str|') == 1
    assert start.read_text().count('artcraft_home_open_touch(ui, open_rect)') == 1
    print("PASS: Android Home Open touch fallback and four HTTPS browser links staged")
    print("PASS: all existing dialogs, GPU, gestures, menus, font, AI and signing untouched")

if __name__ == "__main__":
    main()
