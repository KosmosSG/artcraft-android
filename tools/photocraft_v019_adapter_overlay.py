#!/usr/bin/env python3
"""Apply *runner-only* PhotoCraft 0.19 Android adapter/UI API compatibility.

This script is deliberately invoked only after official v0.19.0 is checked out
and after the original v0.14.0-android.4 preservation gate passes. It edits the
temporary Actions workspace's upstream checkout and Android adapter copy;
no production code, signing key, release, or upstream history is committed.

An anchor mismatch is fatal: do not silently remove AI functionality or file
import behavior when a new official PhotoCraft tag changes upstream APIs.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

UPSTREAM_SHA = "2df9f807702a935184041355a86405380bda8274"


def replace_once(path: Path, before: str, after: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(before)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected one known v0.19.0 anchor, found {count}; "
            "review upstream manually rather than dropping Android features"
        )
    path.write_text(source.replace(before, after, 1), encoding="utf-8")
    print(f"  staged compatibility patch: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--android-adapter", type=Path, required=True)
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    adapter = args.android_adapter.resolve()
    actual_sha = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != UPSTREAM_SHA:
        raise SystemExit(f"Refusing compatibility edits for unreviewed upstream {actual_sha}")

    menus = upstream / "crates/ui-egui/src/menus.rs"
    items = upstream / "crates/ui-egui/src/menus/items.rs"
    invoke = upstream / "crates/ui-egui/src/menus/invoke.rs"
    host = adapter / "src/lib.rs"

    # Preserve the owner-tested Android AI menu and its persisted Window toggle.
    # Unlike the old v0.14 UI, official v0.19 has no artcraft_* accessors.
    replace_once(
        menus,
        "pub use state::is_enabled;\n",
        """pub use state::is_enabled;

// Android-only integration state: the production AI panel remains controlled
// by the owner's local preference, with a Window menu toggle for recovery.
#[cfg(target_os = "android")]
static ARTCRAFT_AI_TOOLS_VISIBLE: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(true);

#[cfg(target_os = "android")]
pub fn artcraft_set_ai_tools_visible(visible: bool) {
    use std::sync::atomic::Ordering;
    ARTCRAFT_AI_TOOLS_VISIBLE.store(visible, Ordering::Relaxed);
}

#[cfg(target_os = "android")]
pub fn artcraft_ai_tools_visible() -> bool {
    use std::sync::atomic::Ordering;
    ARTCRAFT_AI_TOOLS_VISIBLE.load(Ordering::Relaxed)
}
""",
    )
    replace_once(
        items,
        "    photocraft_engine::commands::find(id).is_some()\n",
        "    (cfg!(target_os = \"android\") && id == \"window.artcraft.showAiTools\")\n        || photocraft_engine::commands::find(id).is_some()\n",
    )
    replace_once(
        items,
        "    crate::plugin_ui::insert_menu_items(app, &mut items);\n",
        """    crate::plugin_ui::insert_menu_items(app, &mut items);
    #[cfg(target_os = "android")]
    {
        // Always discoverable in Window even after the AI top strip is hidden.
        let at = items
            .iter()
            .rposition(|it| it.path.first().map(String::as_str) == Some("Window"))
            .map_or(items.len(), |index| index + 1);
        items.insert(at, MenuItem {
            id: "window.artcraft.showAiTools".into(),
            label: "Show AI Tools".into(),
            path: vec!["Window".into()],
            shortcut: None,
            enabled: true,
            checked: Some(super::artcraft_ai_tools_visible()),
            color: None,
        });
    }
""",
    )
    replace_once(
        invoke,
        "fn invoke_early_commands(app: &mut PhotocraftApp, ctx: &egui::Context, id: &str, params: &Value) -> Option<Result<Value, String>> {\n",
        """fn invoke_early_commands(app: &mut PhotocraftApp, ctx: &egui::Context, id: &str, params: &Value) -> Option<Result<Value, String>> {
    #[cfg(target_os = "android")]
    if id == "window.artcraft.showAiTools" {
        let visible = !super::artcraft_ai_tools_visible();
        super::artcraft_set_ai_tools_visible(visible);
        return Some(Ok(json!({"visible": visible})));
    }
""",
    )

    # v0.19 switched the import callback's third argument from a usize
    # max-group-depth to the entire ImportOptions value. Preserve all user
    # settings by passing the received options through, not just group depth.
    replace_once(
        host,
        """            |name: &str, bytes: &[u8], max_svg_group_depth: usize| {
                photocraft_io::import_with_svg_group_depth(name, bytes, max_svg_group_depth)
""",
        """            |name: &str, bytes: &[u8], options: &photocraft_io::ImportOptions| {
                photocraft_io::import_with_options(name, bytes, options)
""",
    )

    # The full tablet fork uses GameActivity and its own JNI bridge. Carry
    # only its safe UI-scroll behavior through this temporary adapter overlay:
    # the published NativeActivity/SAF/keyboard source remains byte-identical.
    replace_once(host, "mod ai_menu;\n", "mod ai_menu;\nmod ui_touch_scroll;\n")
    replace_once(
        host,
        "    modifiers: egui::Modifiers,\n    ai_menu: ai_menu::AndroidAiMenu,\n",
        "    modifiers: egui::Modifiers,\n    touch_scroll: ui_touch_scroll::UiTouchScroll,\n    ai_menu: ai_menu::AndroidAiMenu,\n",
    )
    replace_once(
        host,
        "        apply_android_modifiers(&mut self.modifiers, raw);\n        self.inner.raw_input_hook(ctx, raw);\n",
        "        apply_android_modifiers(&mut self.modifiers, raw);\n        self.touch_scroll.route(ctx, raw);\n        self.inner.raw_input_hook(ctx, raw);\n",
    )
    replace_once(
        host,
        "                modifiers: egui::Modifiers::default(),\n                ai_menu: ai_menu::AndroidAiMenu::new(",
        "                modifiers: egui::Modifiers::default(),\n                touch_scroll: ui_touch_scroll::UiTouchScroll::default(),\n                ai_menu: ai_menu::AndroidAiMenu::new(",
    )

    # A prerelease SemVer label is valid for Cargo and for Android's versionName.
    # Preserve the upstream workspace version, matching the user's -android.N
    # naming convention solely for the compatibility APK and About information.
    replace_once(
        adapter / "Cargo.toml",
        "version.workspace = true\n",
        'version = "0.19.0-android.4"\n',
    )

    # New ArtCraft-owned overlay only; do not replace our shipped NativeActivity.
    replace_once(
        menus,
        '    ARTCRAFT_AI_TOOLS_VISIBLE.load(Ordering::Relaxed)\n}\n',
        '''    ARTCRAFT_AI_TOOLS_VISIBLE.load(Ordering::Relaxed)
}
// Shortcut Pad settings are owned by the Android adapter, not upstream.
#[cfg(target_os = "android")]
static ARTCRAFT_PAD_VISIBLE: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
#[cfg(target_os = "android")]
static ARTCRAFT_PAD_LEFT: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
#[cfg(target_os = "android")]
static ARTCRAFT_UPDATE_REQUESTED: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
#[cfg(target_os = "android")]
pub fn artcraft_pad_visible() -> bool {
    ARTCRAFT_PAD_VISIBLE.load(std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
pub fn artcraft_pad_left() -> bool {
    ARTCRAFT_PAD_LEFT.load(std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
pub fn artcraft_pad_set_visible(v: bool) {
    ARTCRAFT_PAD_VISIBLE.store(v, std::sync::atomic::Ordering::Relaxed);
}
#[cfg(target_os = "android")]
pub fn artcraft_pad_set_left(v: bool) {
    ARTCRAFT_PAD_LEFT.store(v, std::sync::atomic::Ordering::Relaxed);
}
#[cfg(target_os = "android")]
pub fn artcraft_take_update_request() -> bool {
    ARTCRAFT_UPDATE_REQUESTED.swap(false, std::sync::atomic::Ordering::Relaxed)
}
'''
    )
    replace_once(
        items,
        '    (cfg!(target_os = "android") && id == "window.artcraft.showAiTools")\n',
        '    (cfg!(target_os = "android") && (id == "window.artcraft.showAiTools" || id.starts_with("window.artcraft.shortcutPad.")))\n',
    )
    replace_once(
        items,
        '            checked: Some(super::artcraft_ai_tools_visible()),\n            color: None,\n        });\n    }\n',
        '''            checked: Some(super::artcraft_ai_tools_visible()),
            color: None,
        });
        let path = vec!["Window".into(), "Shortcut Pad".into()];
        for (id, label, checked) in [
            ("window.artcraft.shortcutPad.toggle", "Show Shortcut Pad", Some(super::artcraft_pad_visible())),
            ("window.artcraft.shortcutPad.left", "On the Left", Some(super::artcraft_pad_left())),
            ("window.artcraft.shortcutPad.right", "On the Right", Some(!super::artcraft_pad_left())),
        ] {
            items.insert(at, MenuItem {
                id: id.into(), label: label.into(), path: path.clone(),
                shortcut: None, enabled: true, checked, color: None,
            });
        }
    }
''',
    )
    replace_once(
        invoke,
        '        return Some(Ok(json!({"visible": visible})));\n    }\n',
        '''        return Some(Ok(json!({"visible": visible})));
    }
    #[cfg(target_os = "android")]
    if id.starts_with("window.artcraft.shortcutPad.") {
        match id {
            "window.artcraft.shortcutPad.toggle" =>
                super::artcraft_pad_set_visible(!super::artcraft_pad_visible()),
            "window.artcraft.shortcutPad.left" => {
                super::artcraft_pad_set_left(true);
                super::artcraft_pad_set_visible(true);
            }
            "window.artcraft.shortcutPad.right" => {
                super::artcraft_pad_set_left(false);
                super::artcraft_pad_set_visible(true);
            }
            _ => return Some(Err("Unknown Shortcut Pad command".into())),
        }
        ctx.request_repaint();
        return Some(Ok(Value::Null));
    }
    #[cfg(target_os = "android")]
    if id == "help.checkForUpdates" {
        super::ARTCRAFT_UPDATE_REQUESTED.store(true, std::sync::atomic::Ordering::Relaxed);
        ctx.request_repaint();
        return Some(Ok(json!({"android": "checkUpdate"})));
    }
''',
    )
    replace_once(host, 'mod ui_touch_scroll;\n', 'mod ui_touch_scroll;\nmod shortcut_pad;\n')
    replace_once(
        host,
        '    touch_scroll: ui_touch_scroll::UiTouchScroll,\n',
        '    touch_scroll: ui_touch_scroll::UiTouchScroll,\n    shortcut_pad: shortcut_pad::ShortcutPad,\n',
    )
    replace_once(
        host,
        '                touch_scroll: ui_touch_scroll::UiTouchScroll::default(),\n',
        '                touch_scroll: ui_touch_scroll::UiTouchScroll::default(),\n                shortcut_pad: shortcut_pad::ShortcutPad::new(files_dir.join("PhotoCraft")),\n',
    )
    replace_once(
        host,
        '        self.inner.logic(ctx, frame);\n',
        '''        if photocraft_ui_egui::menus::artcraft_take_update_request() {
            if let Err(error) = self.bridge.request_update_check() {
                log::warn!("Check for updates failed to launch: {error}");
            }
        }
        self.inner.logic(ctx, frame);
''',
    )
    replace_once(
        host,
        '        self.inner.ui(ui, _frame);\n',
        '''        self.inner.ui(ui, _frame);
        self.shortcut_pad.show(ui.ctx(), &mut self.inner);
''',
    )
    replace_once(
        host,
        '    fn request_open(&self, id: u64, multiple: bool) -> Result<(), String> {\n',
        '''    fn request_update_check(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
            env.call_method(&*activity, jni_str!("pcCheckUpdates"), jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn request_open(&self, id: u64, multiple: bool) -> Result<(), String> {
''',
    )
    activity = adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"
    replace_once(
        activity,
        '    private final ExecutorService io = Executors.newSingleThreadExecutor();\n',
        '''    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private Updater updater;

    // In-app updater uses the ArtCraft release feed, never the unrelated fork.
    public void pcCheckUpdates() {
        runOnUiThread(() -> {
            if (updater != null) updater.check(true);
        });
    }
''',
    )
    replace_once(
        activity,
        '        handleIncomingFiles(getIntent());\n',
        '''        handleIncomingFiles(getIntent());
        updater = new Updater(this);
        if (updater.checkAtStartup()) updater.check(false);
''',
    )
    replace_once(
        activity,
        '    @Override\n    protected void onNewIntent(Intent intent) {\n',
        '''    @Override
    protected void onResume() {
        super.onResume();
        if (updater != null) updater.resumePendingInstall();
    }

    @Override
    protected void onNewIntent(Intent intent) {
''',
    )
    # cargo-apk2 generates the manifest from this staging-only Cargo.toml.
    replace_once(
        adapter / "Cargo.toml",
        '[package.metadata.android.sdk]\n',
        '''[[package.metadata.android.uses_permission]]
name = "android.permission.INTERNET"

[[package.metadata.android.uses_permission]]
name = "android.permission.REQUEST_INSTALL_PACKAGES"

[package.metadata.android.sdk]
''',
    )


    # === Android.3 owner-tested feature parity: no edits to published Android sources ===
    fonts = upstream / "crates/text/src/fonts.rs"
    replace_once(
        fonts,
        '    /// Registers font data (TTF/OTF, or every face of a TTC/OTC). Returns the family names added.',
        '''    /// Register Android SAF font files lazily from validated app-private paths.
    /// A 4 GiB library is indexed on disk rather than loaded entirely into RAM.
    pub fn register_font_paths(&mut self, paths: &[std::path::PathBuf]) -> usize {
        use std::io::Read as _;
        let mut accepted = Vec::new();
        let mut bytes = 0u64;
        for path in paths.iter().take(5000) {
            let Ok(metadata) = std::fs::metadata(path) else { continue };
            if !metadata.is_file() || metadata.len() < 4 || metadata.len() > 32 * 1024 * 1024 {
                continue;
            }
            if metadata.len() > 4u64 * 1024 * 1024 * 1024 - bytes { break; }
            let Ok(mut file) = std::fs::File::open(path) else { continue };
            let mut magic = [0; 4];
            if file.read_exact(&mut magic).is_err() { continue; }
            if !matches!(magic,
                [0, 1, 0, 0] | [b'O', b'T', b'T', b'O'] |
                [b't', b'r', b'u', b'e'] | [b't', b't', b'c', b'f']) {
                continue;
            }
            accepted.push(path.as_path());
            bytes += metadata.len();
        }
        if accepted.is_empty() { return 0; }
        self.fcx.collection.load_fonts_from_paths(accepted.iter().copied());
        self.ps_cache.clear();
        self.face_cache.clear();
        self.traits_cache.clear();
        self.refresh_generics();
        GENERATION.fetch_add(1, Ordering::Relaxed);
        if self.shared { SHARED_GENERATION.fetch_add(1, Ordering::Relaxed); }
        accepted.len()
    }

    /// Registers font data (TTF/OTF, or every face of a TTC/OTC). Returns the family names added.''',
    )

    # Explicit Android menu rows: the earlier .2 UI had no Import Font and
    # the upstream generic update row did not communicate with our Activity.
    replace_once(
        menus,
        'pub fn artcraft_take_update_request() -> bool {\n    ARTCRAFT_UPDATE_REQUESTED.swap(false, std::sync::atomic::Ordering::Relaxed)\n}\n',
        '''pub fn artcraft_take_update_request() -> bool {
    ARTCRAFT_UPDATE_REQUESTED.swap(false, std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
static ARTCRAFT_FONT_REQUEST: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);
#[cfg(target_os = "android")]
pub fn artcraft_take_font_request() -> u8 {
    ARTCRAFT_FONT_REQUEST.swap(0, std::sync::atomic::Ordering::Relaxed)
}
''',
    )
    replace_once(
        items,
        'id.starts_with("window.artcraft.shortcutPad.")))\n',
        'id.starts_with("window.artcraft.shortcutPad.") || id.starts_with("file.artcraftImportFont") || id == "help.artcraftCheckUpdates"))\n',
    )
    replace_once(
        items,
        '    if let Some(mask) = app.session.active().and_then(|s| s.active_layer.and_then(|id| s.doc.layer(id))).and_then(|l| l.mask.as_ref())\n',
        '''    #[cfg(target_os = "android")]
    {
        for (id, label, top) in [
            ("file.artcraftImportFonts", "Import Font…", "File"),
            ("file.artcraftImportFontFolder", "Import Font Folder…", "File"),
            ("help.artcraftCheckUpdates", "Check for Updates…", "Help"),
        ] {
            if !items.iter().any(|i| i.id == id) {
                // Keep Android commands near the TOP, not below hundreds of
                // Photoshop catalogue rows in File/Help.
                let after = match id {
                    "file.artcraftImportFonts" => "file.open",
                    "file.artcraftImportFontFolder" => "file.artcraftImportFonts",
                    _ => "help.checkForUpdates",
                };
                let at = items.iter().position(|i| i.id == after)
                    .map(|pos| pos + 1)
                    .or_else(|| items.iter().position(|i| i.path.first().map(String::as_str) == Some(top)))
                    .unwrap_or(items.len());
                items.insert(at, MenuItem {
                    id: id.into(), label: label.into(), path: vec![top.into()],
                    shortcut: None, enabled: true, checked: None, color: None,
                });
            }
        }
    }
    if let Some(mask) = app.session.active().and_then(|s| s.active_layer.and_then(|id| s.doc.layer(id))).and_then(|l| l.mask.as_ref())
''',
    )
    replace_once(
        invoke,
        '    if id == "help.checkForUpdates" {\n        return Some(crate::updates_ui::check(app, ctx, params.clone()));\n',
        '''    #[cfg(target_os = "android")]
    if id == "help.artcraftCheckUpdates" {
        super::ARTCRAFT_UPDATE_REQUESTED.store(true, std::sync::atomic::Ordering::Relaxed);
        ctx.request_repaint();
        return Some(Ok(json!({"android": "checkUpdate"})));
    }
    #[cfg(target_os = "android")]
    if id == "file.artcraftImportFonts" || id == "file.artcraftImportFontFolder" {
        let kind = if id == "file.artcraftImportFontFolder" { 2 } else { 1 };
        super::ARTCRAFT_FONT_REQUEST.store(kind, std::sync::atomic::Ordering::Relaxed);
        ctx.request_repaint();
        return Some(Ok(json!({"android": "importFont", "folder": kind == 2})));
    }
    if id == "help.checkForUpdates" {
        return Some(crate::updates_ui::check(app, ctx, params.clone()));
''',
    )

    replace_once(host, 'mod shortcut_pad;\n', 'mod shortcut_pad;\nmod android_fonts;\n')
    replace_once(
        host, '    shortcut_pad: shortcut_pad::ShortcutPad,\n',
        '    shortcut_pad: shortcut_pad::ShortcutPad,\n    android_fonts: android_fonts::AndroidFonts,\n',
    )
    replace_once(
        host,
        '                shortcut_pad: shortcut_pad::ShortcutPad::new(files_dir.join("PhotoCraft")),\n',
        '                shortcut_pad: shortcut_pad::ShortcutPad::new(files_dir.join("PhotoCraft")),\n                android_fonts: android_fonts::AndroidFonts::new(&files_dir),\n',
    )
    replace_once(
        host,
        '        self.picker.poll(&self.bridge, ctx);\n',
        '''        self.picker.poll(&self.bridge, ctx);
        self.android_fonts.poll(&self.bridge);
        match photocraft_ui_egui::menus::artcraft_take_font_request() {
            1 => { if let Err(e) = self.bridge.request_font_import(false) { log::warn!("Import Font: {e}"); } },
            2 => { if let Err(e) = self.bridge.request_font_import(true) { log::warn!("Import Font Folder: {e}"); } },
            _ => {},
        }
''',
    )
    replace_once(
        host,
        '        self.shortcut_pad.show(ui.ctx(), &mut self.inner);\n',
        '        self.shortcut_pad.show(ui.ctx(), &mut self.inner);\n        self.android_fonts.show(ui.ctx());\n',
    )
    replace_once(
        host,
        '        if self.ai_menu.show(ui, &mut self.inner.session) {\n',
        '''        let clipboard_bridge = self.bridge.clone_for_services();
        if self.ai_menu.show(ui, &mut self.inner.session, || clipboard_bridge.clipboard_text().ok().flatten()) {
''',
    )
    replace_once(
        host,
        '        self.inner.raw_input_hook(ctx, raw);\n',
        '''        // Native Android clipboard is not automatically connected to egui on
        // NativeActivity. Only read it on explicit Ctrl+V, never poll or log it.
        let paste_pressed = raw.events.iter().any(|e| matches!(e,
            egui::Event::Key { key: egui::Key::V, pressed: true, modifiers, .. }
                if modifiers.ctrl || modifiers.command));
        if paste_pressed {
            if let Ok(Some(text)) = self.bridge.clipboard_text() {
                raw.events.push(egui::Event::Paste(text));
            }
        }
        self.inner.raw_input_hook(ctx, raw);
''',
    )
    replace_once(
        host,
        '    fn request_update_check(&self) -> Result<(), String> {\n',
        '''    fn request_font_import(&self, folder: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pcRequestFontImport"), jni_sig!("(Z)V"),
                &[JValue::Bool(folder)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn poll_font_import(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pcPollFontImport"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            let value: String = value.try_to_string(env)?;
            Ok(Some(value))
        }).map_err(|e| e.to_string())
    }

    fn clipboard_text(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pcClipboardText"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            let value: String = value.try_to_string(env)?;
            Ok(Some(value))
        }).map_err(|e| e.to_string())
    }

    fn request_update_check(&self) -> Result<(), String> {
''',
    )

    replace_once(
        adapter / "Cargo.toml",
        'photocraft-engine = { path = "../../crates/engine" }\n',
        'photocraft-engine = { path = "../../crates/engine" }\nphotocraft-text = { path = "../../crates/text" }\n',
    )

    replace_once(
        activity,
        'import android.content.ClipData;\n',
        'import android.content.ClipData;\nimport android.content.ClipboardManager;\n',
    )
    replace_once(
        activity,
        '    private Updater updater;\n',
        '''    private Updater updater;
    private PhotoCraftFontImport fontImport;

    public void pcRequestFontImport(boolean folder) {
        if (fontImport != null) fontImport.request(folder);
    }
    public String pcPollFontImport() {
        return fontImport == null ? null : fontImport.poll();
    }
    // Sensitive token text is read only on explicit paste and never persisted.
    public String pcClipboardText() {
        try {
            ClipboardManager manager = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (manager == null || !manager.hasPrimaryClip()) return null;
            ClipData clip = manager.getPrimaryClip();
            if (clip == null || clip.getItemCount() < 1) return null;
            CharSequence value = clip.getItemAt(0).coerceToText(this);
            if (value == null) return null;
            String text = value.toString();
            return text.length() > 8192 ? text.substring(0, 8192) : text;
        } catch (Exception e) {
            Log.w(TAG, "Android clipboard is not currently accessible");
            return null;
        }
    }
''',
    )
    replace_once(
        activity,
        '        updater = new Updater(this);\n',
        '        fontImport = new PhotoCraftFontImport(this);\n        updater = new Updater(this);\n',
    )
    replace_once(
        activity,
        '        super.onActivityResult(requestCode, resultCode, data);\n        if (requestCode != REQ_OPEN && requestCode != REQ_SAVE) return;\n',
        '''        super.onActivityResult(requestCode, resultCode, data);
        if (fontImport != null && fontImport.result(requestCode, resultCode, data)) return;
        if (requestCode != REQ_OPEN && requestCode != REQ_SAVE) return;
''',
    )

    ai_menu = adapter / "src/ai_menu.rs"
    replace_once(
        ai_menu,
        '    pub(crate) fn show(&mut self, ui: &mut egui::Ui, session: &mut Session) -> bool {\n',
        '    pub(crate) fn show(&mut self, ui: &mut egui::Ui, session: &mut Session, clipboard: impl Fn() -> Option<String>) -> bool {\n',
    )
    replace_once(
        ai_menu,
        '''                    ui.add(egui::TextEdit::singleline(&mut self.cpu_token)
                        .password(true).hint_text("Temporary session token"));
''',
        '''                    ui.add(egui::TextEdit::singleline(&mut self.cpu_token)
                        .password(true).hint_text("Temporary session token"));
                    if ui.button("Paste token from Android clipboard").clicked() {
                        if let Some(value) = clipboard().filter(|text| !text.trim().is_empty()) {
                            self.cpu_token = value.trim().to_owned();
                            self.cpu_status = "Token pasted from Android clipboard (not stored).".into();
                        } else {
                            self.cpu_status = "Android clipboard is empty or unavailable. Copy the token on this device.".into();
                        }
                    }
''',
    )


    # NativeActivity's IME host delivers text, but device keyboards on some
    # tablets don't deliver the matching egui::Key to upstream shortcut dispatch.
    # Queue only a minimal allowlist of physical key events and let the native
    # input system continue to receive each original event. No text/tokens logged.
    replace_once(host, 'mod android_fonts;\n', 'mod android_fonts;\nmod hardware_keys;\n')
    replace_once(
        host,
        '        apply_android_modifiers(&mut self.modifiers, raw);\n',
        '        apply_android_modifiers(&mut self.modifiers, raw);\n        hardware_keys::inject(&self.bridge, raw);\n',
    )
    replace_once(
        host,
        '    fn poll_font_import(&self) -> Result<Option<String>, String> {\n',
        '''    fn poll_hardware_key(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pcHardwareKeyPoll"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

    fn poll_font_import(&self) -> Result<Option<String>, String> {
''',
    )
    replace_once(
        activity,
        '    private PhotoCraftFontImport fontImport;\n',
        '''    private PhotoCraftFontImport fontImport;
    private final ConcurrentLinkedQueue<String> artcraftHardwareKeys = new ConcurrentLinkedQueue<>();

    // Hardware keys that upstream egui needs for tool, close, and type editing
    // actions. All other keys stay on the normal native/IME path. NEVER log
    // typed keys or read/retain secure text, including U2NetP tokens.
    public String pcHardwareKeyPoll() { return artcraftHardwareKeys.poll(); }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        int code = event.getKeyCode();
        int action = event.getAction();
        if ((action == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0)
                || action == KeyEvent.ACTION_UP) {
            if (code == KeyEvent.KEYCODE_ESCAPE || code == KeyEvent.KEYCODE_V
                    || code == KeyEvent.KEYCODE_T || code == KeyEvent.KEYCODE_B
                    || code == KeyEvent.KEYCODE_Y || code == KeyEvent.KEYCODE_N
                    || code == KeyEvent.KEYCODE_C || code == KeyEvent.KEYCODE_W
                    || code == KeyEvent.KEYCODE_D || code == KeyEvent.KEYCODE_S
                    || code == KeyEvent.KEYCODE_ENTER) {
                int flags = (event.isAltPressed() ? 1 : 0)
                    | (event.isCtrlPressed() ? 2 : 0)
                    | (event.isShiftPressed() ? 4 : 0);
                // Encoded physical key, modifiers, and whether this is DOWN.
                artcraftHardwareKeys.offer(code + "," + flags + ","
                    + (action == KeyEvent.ACTION_DOWN ? "1" : "0"));
            }
        }
        return super.dispatchKeyEvent(event);
    }
''',
    )

    print("PhotoCraft v0.19.0-android.4: docked pad, popup scroll, menu prominence and hardware shortcuts staged (runner only).")


if __name__ == "__main__":
    main()
