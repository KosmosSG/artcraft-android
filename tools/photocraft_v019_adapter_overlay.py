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
        'version = "0.19.0-android.2"\n',
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

    print("PhotoCraft v0.19.0-android.2: owner updater, show/hide Shortcut Pad, UI scroll staged (runner only).")


if __name__ == "__main__":
    main()
