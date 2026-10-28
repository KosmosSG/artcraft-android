"""Stage Android-specific Type / Help menu integration into the reviewed source checkout."""
from pathlib import Path

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("DesignCraft menu API drift: " + old[:70])
    return text.replace(old, new)

def apply(path: Path):
    text = path.read_text()
    text = replace_once(text,
        'pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[',
        '''pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[
    #[cfg(target_os = "android")]
    ("app.artcraftImportFont", "Custom Font Import (TTF/OTF)…", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftSelectSharedFonts", "Select Shared Font Folder…", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftRefreshSharedFonts", "Refresh Shared Fonts", None, "{}"),
    #[cfg(target_os = "android")]
    ("help.artcraftCheckUpdates", "Check for Updates…", None, "{}"),
    #[cfg(target_os = "android")]
    ("help.artcraftUpdateSettings", "Startup Update Settings…", None, "{}"),
    #[cfg(target_os = "android")]
    ("window.artcraftShortcutPad", "Toggle Touch Shortcut Pad", None, "{}"),
    #[cfg(target_os = "android")]
    ("window.artcraftAndroidToolbar", "Show/Hide Android Toolbar", None, "{}"),''')
    text = replace_once(text, 'pub fn ui_label(id: &str) -> Option<(&',
        '''#[cfg(target_os = "android")]
static ARTCRAFT_ANDROID_ACTIONS: std::sync::atomic::AtomicU32 =
    std::sync::atomic::AtomicU32::new(0);

#[cfg(target_os = "android")]
pub fn artcraft_take_android_actions() -> u32 {
    ARTCRAFT_ANDROID_ACTIONS.swap(0, std::sync::atomic::Ordering::Relaxed)
}

pub fn ui_label(id: &str) -> Option<(&''')
    text = replace_once(text,
        '    Some(match id {\n        "window.minimize" => {',
        '''    Some(match id {
        #[cfg(target_os = "android")]
        "app.artcraftImportFont" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(1, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "app.artcraftSelectSharedFonts" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(2, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "app.artcraftRefreshSharedFonts" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(4, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "help.artcraftCheckUpdates" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(8, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "help.artcraftUpdateSettings" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(16, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "window.artcraftShortcutPad" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(32, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "window.artcraftAndroidToolbar" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(64, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        "window.minimize" => {''')
    text = replace_once(text,
        """pub fn menu_tree() -> Vec<(&'static str, Vec<Item>)> {
    MENUS.iter().map(|(m, e)| (*m, parse_entries(e))).collect()
}""",
        """pub fn menu_tree() -> Vec<(&'static str, Vec<Item>)> {
    let mut tree: Vec<(&'static str, Vec<Item>)> =
        MENUS.iter().map(|(m, e)| (*m, parse_entries(e))).collect();
    #[cfg(target_os = "android")]
    for (menu, entries) in &mut tree {
        let ids: &[&str] = match *menu {
            "Type" => &["app.artcraftImportFont", "app.artcraftSelectSharedFonts", "app.artcraftRefreshSharedFonts"],
            "Help" => &["help.artcraftCheckUpdates", "help.artcraftUpdateSettings"],
            "Window" => &["window.artcraftShortcutPad", "window.artcraftAndroidToolbar"],
            _ => &[],
        };
        if !ids.is_empty() {
            // Keep upstream menu order and append a separated Android-only section.
            // About DesignCraft is a dialog action; update controls follow it in Help.
            if !entries.is_empty() && !matches!(entries.last(), Some(Item::Sep)) {
                entries.push(Item::Sep);
            }
            entries.extend(ids.iter().map(|id| cmd_item(id, Value::Null)));
        }
    }
    tree
}""")
    # Android's GameActivity touch input is sometimes exposed to egui without
    # has_touch_screen=true, causing ScrollArea's default DragScroll::OnTouch
    # to reject swipes. Menu popups are already scrollable upstream, but long
    # lists need an explicit Android drag source and a bounded viewport.
    text = replace_once(text,
        """    let max_height = menu_max_height(ui, button);
    let contents = |ui: &mut egui::Ui| {""",
        """    let max_height = menu_max_height(ui, button);
    // Make long dropdowns a genuinely scrollable viewport on Android tablets.
    // Keep native desktop menu sizing/interaction entirely unchanged.
    #[cfg(target_os = "android")]
    let max_height = max_height.min((ui.ctx().content_rect().height() * 0.72).max(180.0));
    let contents = |ui: &mut egui::Ui| {""")
    # The first attempt switched egui's built-in DragScroll::Always, but
    # that still did not move the long Type menu in HONOR MagicPad testing.
    # Drive vertical touch movement explicitly from egui pointer deltas.
    # Provide tap-operated page controls as a reliable accessibility fallback.
    text = replace_once(text,
        """        scroll.show(ui, add_contents).inner
    };""",
        """        #[cfg(target_os = "android")]
        {
            // Per popup (and per submenu) state: no cross-menu scroll leakage.
            // A touch drag on a menu row may be captured by that row before
            // ScrollArea's drag recognizer runs, so read the raw pointer delta.
            let nav_id = ui.id().with("designcraft-android-menu-scroll");
            let prior = ui.data(|d| d.get_temp::<(f32, f32, egui::Rect)>(nav_id));
            let (mut target, _available, previous_rect) =
                prior.unwrap_or((0.0, 0.0, egui::Rect::NOTHING));
            let overflow = prior.is_some_and(|(_, max, _)| max > 2.0);
            if ui.is_sizing_pass() { target = 0.0; }

            // Navigation buttons stay outside the scrolling region. They work
            // with touch, pen and mouse even when Android sends no drag delta.
            if overflow {
                ui.horizontal(|ui| {
                    if ui.add_enabled(target > 1.0, egui::Button::new("▲ Scroll up")).clicked() {
                        target = (target - max_height * 0.58).max(0.0);
                    }
                });
            }
            if !ui.is_sizing_pass() {
                let swipe = ui.input(|i| {
                    let inside = i.pointer.interact_pos().is_some_and(|p| previous_rect.contains(p));
                    if inside && i.pointer.primary_down() && i.pointer.is_decidedly_dragging() {
                        i.pointer.delta().y
                    } else { 0.0 }
                });
                if swipe.abs() > 0.01 {
                    // Drag finger upwards => reveal lower menu commands.
                    target = (target - swipe).max(0.0);
                    ui.ctx().request_repaint();
                }
            }
            // Control menu viewport height separately from the header/footer,
            // so the whole popup remains within MagicPad's visible content.
            scroll = scroll
                .max_height((max_height - if overflow { 62.0 } else { 0.0 }).max(105.0))
                .scroll_source(egui::containers::scroll_area::ScrollSource {
                    scroll_bar: true,
                    drag: egui::containers::scroll_area::DragScroll::Never,
                    mouse_wheel: true,
                })
                .scroll_bar_visibility(egui::containers::scroll_area::ScrollBarVisibility::AlwaysVisible)
                .vertical_scroll_offset(target);
            let rendered = scroll.show(ui, add_contents);
            let max_offset = (rendered.content_size.y - rendered.inner_rect.height()).max(0.0);
            let mut next = rendered.state.clamped_offset().y;
            if overflow {
                ui.horizontal(|ui| {
                    if ui.add_enabled(next < max_offset - 1.0, egui::Button::new("▼ More items")).clicked() {
                        next = (next + max_height * 0.58).min(max_offset);
                    }
                });
            }
            ui.data_mut(|d| d.insert_temp(nav_id, (next, max_offset, rendered.inner_rect)));
            if !overflow && max_offset > 2.0 {
                // Show the page buttons after this first measurement.
                ui.ctx().request_repaint();
            }
            rendered.inner
        }
        #[cfg(not(target_os = "android"))]
        {
            scroll.show(ui, add_contents).inner
        }
    };""")
    path.write_text(text)

if __name__ == "__main__":
    import sys
    apply(Path(sys.argv[1]))

