#!/usr/bin/env python3
"""Guarded, Android-only PDFCraft View > Android tools menu patch.

This adds a View menu check item in the *real* upstream craft-menu bar, not a
second navigation row. It lives outside the PDF editing core and never alters
desktop builds. Run against the exact pinned official PDFCraft v0.17 source.
"""
from pathlib import Path
import sys

src = Path(sys.argv[1])
path = src / "crates/ui-egui/src/menus.rs"
text = path.read_text()
marker = "ARTCRAFT_ANDROID_TOOLS_VISIBLE"
if marker in text:
    expected = [
        'const ANDROID_TOOLS: &str = "view.android_tools";',
        "self.menu_item(ANDROID_TOOLS, None)",
        "pub fn android_tools_visible(&self) -> bool",
        "pub fn set_android_tools_visible(&self, visible: bool)",
        "ANDROID_TOOLS => cfg!(target_os = \"android\")",
        "ANDROID_TOOLS => Some(ARTCRAFT_ANDROID_TOOLS_VISIBLE.load(",
    ]
    assert all(x in text for x in expected), "Incomplete existing PDFCraft tools menu patch"
    print("PASS: PDFCraft Android tools View menu already patched")
    sys.exit(0)

def replace(old: str, new: str):
    global text
    count = text.count(old)
    assert count == 1, f"PDFCraft 0.17 menus changed: expected one anchor {old!r}, found {count}"
    text = text.replace(old, new, 1)

replace('const PANEL: &str = "view.panel";',
        'const PANEL: &str = "view.panel";\n'
        'const ANDROID_TOOLS: &str = "view.android_tools";')

replace('    (NO_RECENT, "No recent files", None),',
        '    (NO_RECENT, "No recent files", None),\n'
        '    (ANDROID_TOOLS, "Android tools panel", None),')

replace('        view.extend(list(PANES, &mut used));',
        '        #[cfg(target_os = "android")]\n'
        '        view.push(self.menu_item(ANDROID_TOOLS, None));\n'
        '        view.extend(list(PANES, &mut used));')

replace('                PANEL => panel(command).is_some(),',
        '                PANEL => panel(command).is_some(),\n'
        '                ANDROID_TOOLS => cfg!(target_os = "android"),')

replace('            PANEL => Some(panel(command).is_some_and(|p| self.right == Some(p))),',
        '            PANEL => Some(panel(command).is_some_and(|p| self.right == Some(p))),\n'
        '            #[cfg(target_os = "android")]\n'
        '            ANDROID_TOOLS => Some(ARTCRAFT_ANDROID_TOOLS_VISIBLE.load('
        'std::sync::atomic::Ordering::Relaxed)),')

replace('            PANEL => self.choose_right_panel(panel(command)),',
        '            PANEL => self.choose_right_panel(panel(command)),\n'
        '            #[cfg(target_os = "android")]\n'
        '            ANDROID_TOOLS => {\n'
        '                ARTCRAFT_ANDROID_TOOLS_VISIBLE.fetch_xor('
        'true, std::sync::atomic::Ordering::AcqRel);\n'
        '            },')

text += """
// PDFCraft Android-only native View menu toggle. No desktop menu changes.
#[cfg(target_os = "android")]
static ARTCRAFT_ANDROID_TOOLS_VISIBLE: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(true);

#[cfg(target_os = "android")]
impl PdfCraftApp {
    pub fn android_tools_visible(&self) -> bool {
        ARTCRAFT_ANDROID_TOOLS_VISIBLE.load(std::sync::atomic::Ordering::Acquire)
    }
    pub fn set_android_tools_visible(&self, visible: bool) {
        ARTCRAFT_ANDROID_TOOLS_VISIBLE.store(visible, std::sync::atomic::Ordering::Release);
    }
}
"""
assert "ARTCRAFT_ANDROID_TOOLS_VISIBLE" in text
path.write_text(text)
print("PASS: PDFCraft View > Android tools panel, toggle and checked state patched")
