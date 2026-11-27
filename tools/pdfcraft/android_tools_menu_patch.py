#!/usr/bin/env python3
"""Guarded, Android-only PDFCraft View > Android tools menu patch.

This adds a View menu check item in the *real* upstream craft-menu bar, not a
second navigation row. It lives outside the PDF editing core and never alters
desktop builds. Run against the exact pinned official PDFCraft v0.17 source.
"""
from pathlib import Path
import base64
import hashlib
import sys

src = Path(sys.argv[1])
path = src / "crates/ui-egui/src/menus.rs"
text = path.read_text()
marker = "ARTCRAFT_ANDROID_TOOLS_VISIBLE"

def install_approved_brand_module():
    """Add the missing Android-only Pc painter to the upstream UI crate."""
    ui_src = src / "crates/ui-egui/src"
    lib_path = ui_src / "lib.rs"
    brand_path = ui_src / "android_approved_brand.rs"
    lib_text = lib_path.read_text()
    declaration = '#[cfg(target_os = "android")]\nmod android_approved_brand;'
    if "mod android_approved_brand;" not in lib_text:
        anchor = "mod menus;\n"
        assert lib_text.count(anchor) == 1, "PDFCraft UI crate module anchor changed"
        lib_path.write_text(lib_text.replace(anchor, declaration + "\n" + anchor, 1))

    icon_path = Path(__file__).with_name("pc-icon.b64")
    icon_bytes = base64.b64decode(icon_path.read_text().strip(), validate=True)
    expected_sha256 = "690439cf43b99f6d5e5f233f2cbb55877cfbe089e823ae2de600035884d5a3f8"
    assert hashlib.sha256(icon_bytes).hexdigest() == expected_sha256, "Protected Android.10 Pc icon asset changed"
    icon_png_path = ui_src / "android_pc_icon.png"
    if icon_png_path.exists():
        assert icon_png_path.read_bytes() == icon_bytes, "Unexpected existing PDFCraft Pc menu artwork"
    else:
        icon_png_path.write_bytes(icon_bytes)

    # The upstream crate already has image as a dev dependency. Promote the same
    # PNG-only decoder to a runtime dependency for the Android Pc menu texture.
    cargo_path = src / "crates/ui-egui/Cargo.toml"
    cargo_text = cargo_path.read_text()
    if 'image = { version = "0.25", default-features = false, features = ["png"] }' not in cargo_text:
        anchor = 'egui = { workspace = true, features = ["bytemuck", "default_fonts", "monochrome_emoji_fonts"] }'
        assert cargo_text.count(anchor) == 1, "PDFCraft UI dependency anchor changed"
        cargo_path.write_text(cargo_text.replace(
            anchor,
            anchor + '\nimage = { version = "0.25", default-features = false, features = ["png"] }',
            1,
        ))

    brand_source = """// PDFCRAFT_ANDROID_APPROVED_PC_BRAND
// Render the exact Pc artwork shipped by the protected Android.10 release.
use egui::{Color32, Painter, Rect, TextureHandle};

pub(crate) fn paint(ctx: &egui::Context, painter: &Painter, rect: Rect) {
    let texture_id = egui::Id::new("pdfcraft.android.approved_pc_icon");
    let texture = ctx.data_mut(|data| data.get_temp::<TextureHandle>(texture_id))
        .unwrap_or_else(|| {
            let rgba = match image::load_from_memory(include_bytes!("android_pc_icon.png")) {
                Ok(image) => image.to_rgba8(),
                Err(_) => return,
            };
            let size = [rgba.width() as usize, rgba.height() as usize];
            let image = egui::ColorImage::from_rgba_unmultiplied(size, rgba.as_raw());
            let texture = ctx.load_texture(
                "pdfcraft-protected-pc-icon",
                image,
                egui::TextureOptions::LINEAR,
            );
            ctx.data_mut(|data| data.insert_temp(texture_id, texture.clone()));
            texture
        });
    painter.image(
        texture.id(),
        rect,
        Rect::from_min_max(egui::pos2(0.0, 0.0), egui::pos2(1.0, 1.0)),
        Color32::WHITE,
    );
}
"""
    if brand_path.exists():
        assert brand_path.read_text() == brand_source, "Unexpected existing Android Pc brand module"
    else:
        brand_path.write_text(brand_source)


install_approved_brand_module()

if "fn menu_item(&self, id: &'static str, label: Option<&str>, mac: bool)" in text:
    menu_item_call = "self.menu_item(ANDROID_TOOLS, None, false)"
elif "fn menu_item(&self, id: &'static str, label: Option<&str>)" in text:
    menu_item_call = "self.menu_item(ANDROID_TOOLS, None)"
else:
    raise SystemExit("Unsupported PDFCraft menu_item signature; refusing an unreviewed menu patch")
if marker in text:
    expected = [
        'const ANDROID_TOOLS: &str = "view.android_tools";',
        'PDFCRAFT_ANDROID_ICON_MENU',
        menu_item_call,
        "pub fn android_tools_visible(&self) -> bool",
        "pub fn set_android_tools_visible(&self, visible: bool)",
        "ANDROID_TOOLS => cfg!(target_os = \"android\")",
        "ANDROID_TOOLS => Some(ARTCRAFT_ANDROID_TOOLS_VISIBLE.load(",
    ]
    assert all(x in text for x in expected), "Incomplete existing PDFCraft tools menu patch"
    assert "PDFCRAFT_ANDROID_HELP_REQUEST" in text, "Approved Help menu bridge missing"
    print("PASS: approved PDFCraft Help menu and optional View tool menu patched")
    sys.exit(0)

def replace(old: str, new: str):
    global text
    count = text.count(old)
    assert count == 1, f"PDFCraft 0.17 menus changed: expected one anchor {old!r}, found {count}"
    text = text.replace(old, new, 1)

replace('    pub fn run_menu_command(&mut self, ctx: &egui::Context, command: &CommandRef) {',
        '    pub fn android_wheel_action(&mut self, ctx: &egui::Context, id: &\'static str) {\n'
        '        if self.active_ids().is_some() && !self.modal_open() && !self.palette_open && !ctx.text_edit_focused() {\n'
        '            self.dispatch_command(ctx, id);\n'
        '        }\n    }\n'
        '    pub fn run_menu_command(&mut self, ctx: &egui::Context, command: &CommandRef) {')

replace('const PANEL: &str = "view.panel";',
        'const PANEL: &str = "view.panel";\n'
        'const ANDROID_TOOLS: &str = "view.android_tools";')

replace('    (NO_RECENT, "No recent files", None),',
        '    (NO_RECENT, "No recent files", None),\n'
        '    (ANDROID_TOOLS, "Android tools panel", None),')

replace('        view.extend(list(PANES, &mut used));',
        '        #[cfg(target_os = "android")]\n'
        '        view.push(' + menu_item_call + ');\n'
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

# Move PDFCraft Android actions from Help into clickable top-left approved icon.
# Keep standard upstream Help and existing View toolbar fallback.
replace('        let ctx = ui.ctx().clone();',
        '''        // PDFCRAFT_ANDROID_ICON_MENU: approved logo at top-left, before File.
        #[cfg(target_os = "android")]
        {
            let mut theme_choice: Option<ThemePreference> = None;
            let (rect, response) = ui.allocate_exact_size(
                egui::vec2(28.0, 28.0), egui::Sense::click());
            crate::android_approved_brand::paint(ui.ctx(), ui.painter(), rect.shrink(2.0));
            let response = response.on_hover_text("PDFCraft Android settings");
            let _ = egui::Popup::menu(&response).show(|ui| {
                ui.set_min_width(230.0);
                // Keep advanced diagnostics accessible through View > Android
                // tools panel, but not in the streamlined Pc menu.
                for (name, action) in [
                    ("Import Fonts…", 1u8),
                    ("Select Shared Font Folder…", 2),
                    ("Refresh Fonts Folder", 3),
                ] {
                    if ui.button(name).clicked() {
                        PDFCRAFT_ANDROID_HELP_REQUEST.store(
                            action, std::sync::atomic::Ordering::Release);
                        ui.close();
                    }
                }
                ui.separator();
                // PDFCRAFT_ANDROID_PC_APPEARANCE: the Pc launcher menu is
                // where Android users choose Light/Dark. Reuse upstream
                // theme preferences so the choice persists across relaunches.
                ui.menu_button("Stylus Wheel", |ui| {
                    // A real checked checkbox communicates whether the
                    // persisted wheel is enabled (not just a selected row).
                    let mut enabled = ui.ctx().data(|d|
                        d.get_temp::<bool>(egui::Id::new("pdfcraft.wheel.enabled")).unwrap_or(false));
                    if ui.checkbox(&mut enabled, "Stylus Wheel On").changed() {
                        ui.ctx().data_mut(|d|
                            d.insert_temp(egui::Id::new("pdfcraft.wheel.request"), 1u8));
                        ui.close();
                    }
                    if ui.button("Customization…").clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("pdfcraft.wheel.request"), 2u8)); ui.close();
                    }
                });
                ui.menu_button("Appearance", |ui| {
                    if ui.selectable_label(
                        self.theme_preference == ThemePreference::Light, "Light"
                    ).clicked() {
                        theme_choice = Some(ThemePreference::Light);
                        ui.close();
                    }
                    if ui.selectable_label(
                        self.theme_preference == ThemePreference::Dark, "Dark"
                    ).clicked() {
                        theme_choice = Some(ThemePreference::Dark);
                        ui.close();
                    }
                });
                ui.separator();
                // PDFCRAFT_ANDROID_DECKCRAFT_APP_UPDATES:
                // Group updater commands like DeckCraft Dk > App Updates.
                // The checked indicator reflects the actual saved Java
                // preference, mirrored each frame by the Android wrapper.
                ui.menu_button("App Updates", |ui| {
                    if ui.button("Check for Updates…").clicked() {
                        PDFCRAFT_ANDROID_HELP_REQUEST.store(
                            4u8, std::sync::atomic::Ordering::Release);
                        ui.close();
                    }
                    let enabled = ui.ctx().data(|data| data.get_temp::<bool>(
                        egui::Id::new("pdfcraft.android.startup.enabled")).unwrap_or(true));
                    let label = if enabled {
                        "✓  Toggle Update Check at Startup"
                    } else {
                        "    Toggle Update Check at Startup"
                    };
                    if ui.button(label).clicked() {
                        PDFCRAFT_ANDROID_HELP_REQUEST.store(
                            5u8, std::sync::atomic::Ordering::Release);
                        ui.close();
                    }
                });
                ui.separator();
                if ui.button("About PDFCraft").clicked() {
                    PDFCRAFT_ANDROID_HELP_REQUEST.store(
                        9, std::sync::atomic::Ordering::Release);
                    ui.close();
                }
            });
            if let Some(preference) = theme_choice {
                self.set_theme_preference(preference);
            }
        }
        let ctx = ui.ctx().clone();''')
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
