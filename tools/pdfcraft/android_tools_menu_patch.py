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
    assert "PDFCRAFT_ANDROID_HELP_REQUEST" in text, "Approved Help menu bridge missing"\n    print("PASS: approved PDFCraft Help menu and optional View tool menu patched")
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

replace('    (ANDROID_TOOLS, "Android tools panel", None),',
        '    (ANDROID_TOOLS, "Android tools panel", None),\n'
        '    ("android.import_fonts", "Import Fonts…", None),\n'
        '    ("android.shared_folder", "Shared fonts folder…", None),\n'
        '    ("android.refresh_fonts", "Refresh shared fonts", None),\n'
        '    ("android.tools_dialog", "Android tools…", None),')
replace('        let help = list(HELP, &mut used);',
        '        let mut help = list(HELP, &mut used);\n'
        '        #[cfg(target_os = "android")] {\n'
        '            help.push(Node::Separator);\n'
        '            for id in ["android.import_fonts", "android.shared_folder", "android.refresh_fonts", "android.tools_dialog"] {\n'
        '                help.push(self.menu_item(id, None));\n'
        '            }\n'
        '        }')
replace('                NO_RECENT => false,',
        '                NO_RECENT => false,\n'
        '                "android.import_fonts" | "android.shared_folder" | "android.refresh_fonts" | "android.tools_dialog" => cfg!(target_os = "android"),')
replace('            "file.open_recent" if index.is_some() => {',
        '            #[cfg(target_os = "android")]\n'
        '            "android.import_fonts" => { PDFCRAFT_ANDROID_HELP_REQUEST.store(1, std::sync::atomic::Ordering::Release); },\n'
        '            #[cfg(target_os = "android")]\n'
        '            "android.shared_folder" => { PDFCRAFT_ANDROID_HELP_REQUEST.store(2, std::sync::atomic::Ordering::Release); },\n'
        '            #[cfg(target_os = "android")]\n'
        '            "android.refresh_fonts" => { PDFCRAFT_ANDROID_HELP_REQUEST.store(3, std::sync::atomic::Ordering::Release); },\n'
        '            #[cfg(target_os = "android")]\n'
        '            "android.tools_dialog" => { PDFCRAFT_ANDROID_HELP_REQUEST.store(4, std::sync::atomic::Ordering::Release); },\n'
        '            "file.open_recent" if index.is_some() => {')
text += """
// PDFCraft Android-only native View menu toggle. No desktop menu changes.
#[cfg(target_os = "android")]
static ARTCRAFT_ANDROID_TOOLS_VISIBLE: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);

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
text += """
// Android Help menu actions from owner-approved stable PDFCraft v0.12.1-android.3.
#[cfg(target_os = "android")]
static PDFCRAFT_ANDROID_HELP_REQUEST: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);
#[cfg(target_os = "android")]
impl PdfCraftApp {
    pub fn take_android_tools_request(&self) -> u8 {
        PDFCRAFT_ANDROID_HELP_REQUEST.swap(0, std::sync::atomic::Ordering::AcqRel)
    }
}
"""
assert "ARTCRAFT_ANDROID_TOOLS_VISIBLE" in text
assert "PDFCRAFT_ANDROID_HELP_REQUEST" in text
path.write_text(text)
print("PASS: PDFCraft View > Android tools panel, toggle and checked state patched")
