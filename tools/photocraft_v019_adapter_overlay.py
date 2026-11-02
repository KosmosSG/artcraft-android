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
        'version = "0.19.0-android.1"\n',
    )
    print("PhotoCraft v0.19.0-android.1 compatibility, AI and two-finger UI scrolling staged (runner only).")


if __name__ == "__main__":
    main()
