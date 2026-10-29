#!/usr/bin/env python3
"""Add Window > Show AI Tools to the verified, ephemeral v0.14 Android menu port.

Only patches source/photocraft/crates/ui-egui/src/menus.rs in the temporary CI
checkout AFTER the owner-tested menu port has completed. Never modifies official
upstream, the production APK, signing keys or other ArtCraft apps.
"""
from pathlib import Path
import sys

ID = "window.artcraftAiToolsVisibility"
MARKER = "ARTCRAFT_PR93_WINDOW_AI_TOOLS_TOGGLE_V1"


def once(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise ValueError(f"Upstream v0.14 menu port drift: {count} matches for {before[:90]!r}")
    return text.replace(before, after, 1)


def patch(text: str) -> str:
    if MARKER in text or ID in text:
        raise ValueError("AI Tools toggle already patched; refuse duplicate menu entries")
    if "window.artcraftTouchShortcutPad" not in text or "artcraft.check_updates_requested" not in text:
        raise ValueError("Expected tested Android menu port was not installed")
    # Android-only visibility state is shared across the upstream Window menu and
    # the Android-owned AI Tools strip. No desktop command or workspace preference
    # is modified. The Android shell persists the value in its private files dir.
    text = once(text,
        'const SHORTCUT_PAD_ID: &str = "window.artcraftTouchShortcutPad";',
        '''const SHORTCUT_PAD_ID: &str = "window.artcraftTouchShortcutPad";
#[cfg(target_os = "android")]
const AI_TOOLS_ID: &str = "window.artcraftAiToolsVisibility";
// ARTCRAFT_PR93_WINDOW_AI_TOOLS_TOGGLE_V1
#[cfg(target_os = "android")]
static AI_TOOLS_VISIBLE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(true);

#[cfg(target_os = "android")]
pub fn artcraft_ai_tools_visible() -> bool {
    AI_TOOLS_VISIBLE.load(std::sync::atomic::Ordering::Relaxed)
}

#[cfg(target_os = "android")]
pub fn artcraft_set_ai_tools_visible(visible: bool) {
    AI_TOOLS_VISIBLE.store(visible, std::sync::atomic::Ordering::Relaxed);
}''')
    text = once(text,
        '''        if id == SHORTCUT_PAD_ID {
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.shortcut_pad_toggle"), true));''',
        '''        if id == AI_TOOLS_ID {
            artcraft_set_ai_tools_visible(!artcraft_ai_tools_visible());
            ctx.request_repaint();
            return Ok(Value::Null);
        }
        if id == SHORTCUT_PAD_ID {
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.shortcut_pad_toggle"), true));''')
    old = '''if matches!(id, CUSTOM_FONTS_ID | FONT_CATALOG_ID | SHARED_SELECT_ID | SHARED_REFRESH_ID |
                     SHORTCUT_PAD_ID | UPDATE_SETTINGS_ID | CHECK_UPDATES_ID)'''
    new = '''if matches!(id, CUSTOM_FONTS_ID | FONT_CATALOG_ID | SHARED_SELECT_ID | SHARED_REFRESH_ID |
                     SHORTCUT_PAD_ID | AI_TOOLS_ID | UPDATE_SETTINGS_ID | CHECK_UPDATES_ID)'''
    if text.count(old) != 2:
        raise ValueError("Expected exact original Android is_live and is_enabled menu guards")
    text = text.replace(old, new)
    text = once(text,
        '''            (SHORTCUT_PAD_ID, "Touch Shortcut Pad", "Window"),''',
        '''            (SHORTCUT_PAD_ID, "Touch Shortcut Pad", "Window"),
            (AI_TOOLS_ID, "Show AI Tools", "Window"),''')
    text = once(text,
        '''                shortcut: None, enabled: true, checked: None, color: None,
            };
            let at = items.iter().rposition''',
        '''                shortcut: None, enabled: true,
                checked: if id == AI_TOOLS_ID { Some(artcraft_ai_tools_visible()) } else { None },
                color: None,
            };
            let at = items.iter().rposition''')
    for expected in ("Show AI Tools", "artcraft_ai_tools_visible()", "artcraft_set_ai_tools_visible(",
                     "checked: if id == AI_TOOLS_ID", MARKER):
        if expected not in text:
            raise ValueError("Menu toggle integration incomplete: " + expected)
    return text


def test_fixture() -> None:
    # The core invariants can be asserted without a device. The actual v0.14
    # owner-tested menu source is patched and guarded in the ARM64 CI build.
    example = """const SHORTCUT_PAD_ID: &str = "window.artcraftTouchShortcutPad";
        if id == SHORTCUT_PAD_ID {
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.shortcut_pad_toggle"), true));
pub fn is_live(id: &str) -> bool {
    if matches!(id, CUSTOM_FONTS_ID | FONT_CATALOG_ID | SHARED_SELECT_ID | SHARED_REFRESH_ID |
                     SHORTCUT_PAD_ID | UPDATE_SETTINGS_ID | CHECK_UPDATES_ID) {
    }
}
pub fn is_enabled(app: &PhotocraftApp, id: &str) -> bool {
    if matches!(id, CUSTOM_FONTS_ID | FONT_CATALOG_ID | SHARED_SELECT_ID | SHARED_REFRESH_ID |
                     SHORTCUT_PAD_ID | UPDATE_SETTINGS_ID | CHECK_UPDATES_ID) {
    }
}
            (SHORTCUT_PAD_ID, "Touch Shortcut Pad", "Window"),
                shortcut: None, enabled: true, checked: None, color: None,
            };
            let at = items.iter().rposition"""
    result = patch(example)
    assert result.count('"Show AI Tools"') == 1
    assert result.count('AI_TOOLS_ID | UPDATE_SETTINGS_ID') == 2
    assert result.count('checked: if id == AI_TOOLS_ID') == 1
    assert 'ctx.request_repaint();' in result
    try:
        patch(result)
    except ValueError:
        pass
    else:
        raise AssertionError("Second invocation should fail closed")
    print("PASS: Window AI Tools toggle command, checked state, and duplicate guard")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        test_fixture()
        return
    if len(sys.argv) != 2:
        raise SystemExit("usage: photocraft_ai_window_patch.py PATH_TO_V014_MENUS | --self-test")
    path = Path(sys.argv[1])
    before = path.read_text(encoding="utf-8")
    updated = patch(before)
    path.write_text(updated, encoding="utf-8")
    print("PASS: Window > Show AI Tools checkbox added to the isolated Android UI")


if __name__ == "__main__":
    main()
