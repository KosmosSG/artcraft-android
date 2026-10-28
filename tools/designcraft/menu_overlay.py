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
    ("window.artcraftAndroidToolbar", "Show/Hide Android Toolbar", None, "{}"),
    #[cfg(target_os = "android")]
    ("window.artcraftInputDiagnostics", "Trackpad Input Diagnostics…", None, "{}"),''')
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
        #[cfg(target_os = "android")]
        "window.artcraftInputDiagnostics" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(128, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
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
            "Window" => &["window.artcraftShortcutPad", "window.artcraftAndroidToolbar", "window.artcraftInputDiagnostics"],
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
    # Synthetic wheel events are now confirmed by HONOR MagicPad 4 diagnostics:
    # 23 Java gesture-scroll and 23 egui MouseWheel events, but no menu movement.
    # The stock egui scroll-area path requires rect_contains_pointer, which can
    # reject the popup's hovering pointer when a separate diagnostics window is
    # open. Use the raw egui wheel event (already normalized by the Android
    # bridge), then apply an explicitly bounded per-popup offset.
    text = replace_once(text,
        """        scroll.show(ui, add_contents).inner
    };""",
        """        #[cfg(target_os = "android")]
        {
            // Temp state is scoped to this popup, not shared between menus.
            // Keep the previous visible viewport for a direct geometry test;
            // ui.rect_contains_pointer() can return false for a popup layered
            // above the canvas or beside another diagnostics window.
            let menu_id = ui.id().with("designcraft-menu-trackpad-offset");
            let previous = ui.data(|d| d.get_temp::<(f32, f32, egui::Rect, Option<egui::Pos2>, Option<egui::Pos2>, Option<egui::Pos2>)>(menu_id));
            let (mut offset, previous_limit, previous_rect, last_pointer,
                 mut touch_last, mut mouse_last) = previous.unwrap_or((
                0.0, 0.0, egui::Rect::NOTHING, None, None, None,
            ));
            // MagicOS can issue HOVER_EXIT when a two-finger gesture starts,
            // clearing hover_pos while the gesture wheel event still arrives.
            // Remember the last pointer position, but replace it whenever
            // another live pointer location is reported.
            let pointer_now = ui.input(|i| i.pointer.hover_pos());
            let pointer = pointer_now.or(last_pointer);
            let wheel = ui.input(|input| {
                let Some(pointer) = pointer else { return 0.0; };
                // First show: the popup has no measured viewport yet.
                let inside = previous_rect.contains(pointer) ||
                    (previous.is_none() && ui.max_rect().contains(pointer));
                if !inside { return 0.0; }
                input.raw.events.iter().filter_map(|event| {
                    if let egui::Event::MouseWheel { unit, delta, modifiers, .. } = event {
                        if modifiers.ctrl || modifiers.command { return None; }
                        Some(match unit {
                            egui::MouseWheelUnit::Line => delta.y * 40.0,
                            egui::MouseWheelUnit::Page => delta.y * max_height,
                            egui::MouseWheelUnit::Point => delta.y,
                        })
                    } else { None }
                }).sum::<f32>()
            });
            // On MagicPad, direct screen drags arrive as Touch and/or
            // emulated PointerMoved/PointerButton events, not MouseWheel.
            // Process the raw deltas before menu rows can capture a drag.
            // A finger must START inside this popup's clipped viewport, so
            // moving on the document canvas cannot scroll a menu.
            let touch_events = ui.input(|input| input.raw.events.clone());
            let has_touch = touch_events.iter().any(|event|
                matches!(event, egui::Event::Touch { .. }));
            let mut finger_delta_y = 0.0_f32;
            for event in &touch_events {
                match event {
                    egui::Event::Touch { phase: egui::TouchPhase::Start, pos, .. } => {
                        if touch_last.is_none() && previous_rect.contains(*pos) {
                            touch_last = Some(*pos);
                        }
                    }
                    egui::Event::Touch { phase: egui::TouchPhase::Move, pos, .. } => {
                        if let Some(last) = touch_last {
                            let dy = pos.y - last.y;
                            if dy.is_finite() {
                                finger_delta_y += dy.clamp(-110.0, 110.0);
                            }
                            touch_last = Some(*pos);
                        }
                    }
                    egui::Event::Touch {
                        phase: egui::TouchPhase::End | egui::TouchPhase::Cancel, ..
                    } => touch_last = None,
                    // Some Android environments send pointer emulation only.
                    // Do not double-count it when the real Touch stream exists.
                    egui::Event::PointerButton { pressed: true, pos, .. } if !has_touch => {
                        if previous_rect.contains(*pos) { mouse_last = Some(*pos); }
                    }
                    egui::Event::PointerMoved(pos) if !has_touch => {
                        if let Some(last) = mouse_last {
                            let dy = pos.y - last.y;
                            if dy.is_finite() {
                                finger_delta_y += dy.clamp(-110.0, 110.0);
                            }
                            mouse_last = Some(*pos);
                        }
                    }
                    egui::Event::PointerButton { pressed: false, .. } if !has_touch => {
                        mouse_last = None;
                    }
                    _ => {}
                }
            }
            if finger_delta_y.abs() > 0.01 {
                // Natural movement: dragging UP reveals lower menu commands.
                offset = (offset - finger_delta_y).clamp(0.0, previous_limit.max(0.0));
                ARTCRAFT_MENU_TOUCH_SCROLL_EVENTS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                ui.ctx().request_repaint();
            }
            if wheel.is_finite() && wheel.abs() > 0.01 {
                // Positive wheel moves content down and scroll offset up;
                // do not reapply stale wheel deltas on frames without input.
                let requested_scroll = -wheel;
                ARTCRAFT_MENU_LAST_REQUEST_BITS.store(
                    requested_scroll.to_bits(), std::sync::atomic::Ordering::Relaxed,
                );
                let before_wheel = offset;
                offset = (offset + requested_scroll).clamp(0.0, previous_limit.max(0.0));
                if (offset - before_wheel).abs() < 0.01 {
                    ARTCRAFT_MENU_EDGE_BLOCKED.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                }
                ARTCRAFT_MENU_SCROLL_EVENTS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                ui.ctx().request_repaint();
            }
            // Do not enable a second wheel consumer or add paging controls.
            scroll = scroll
                .scroll_source(egui::containers::scroll_area::ScrollSource {
                    scroll_bar: true,
                    drag: egui::containers::scroll_area::DragScroll::Never,
                    mouse_wheel: false,
                })
                .scroll_bar_visibility(egui::containers::scroll_area::ScrollBarVisibility::VisibleWhenNeeded)
                .vertical_scroll_offset(offset);
            let rendered = scroll.show(ui, add_contents);
            let limit = (rendered.content_size.y - rendered.inner_rect.height()).max(0.0);
            let new_offset = offset.clamp(0.0, limit);
            ui.data_mut(|d| d.insert_temp(menu_id, (
                new_offset, limit, rendered.inner_rect, pointer, touch_last, mouse_last,
            )));
            ARTCRAFT_MENU_SCROLL_OFFSET_BITS.store(
                new_offset.to_bits(), std::sync::atomic::Ordering::Relaxed,
            );
            ARTCRAFT_MENU_SCROLL_LIMIT_BITS.store(
                limit.to_bits(), std::sync::atomic::Ordering::Relaxed,
            );
            rendered.inner
        }
        #[cfg(not(target_os = "android"))]
        {
            scroll.show(ui, add_contents).inner
        }
    };""")
    text = replace_once(text,
        """#[cfg(target_os = "android")]
pub fn artcraft_take_android_actions() -> u32 {""",
        """#[cfg(target_os = "android")]
static ARTCRAFT_MENU_SCROLL_EVENTS: std::sync::atomic::AtomicU64 =
    std::sync::atomic::AtomicU64::new(0);
#[cfg(target_os = "android")]
static ARTCRAFT_MENU_TOUCH_SCROLL_EVENTS: std::sync::atomic::AtomicU64 =
    std::sync::atomic::AtomicU64::new(0);
#[cfg(target_os = "android")]
static ARTCRAFT_MENU_EDGE_BLOCKED: std::sync::atomic::AtomicU64 =
    std::sync::atomic::AtomicU64::new(0);
#[cfg(target_os = "android")]
static ARTCRAFT_MENU_LAST_REQUEST_BITS: std::sync::atomic::AtomicU32 =
    std::sync::atomic::AtomicU32::new(0);
#[cfg(target_os = "android")]
static ARTCRAFT_MENU_SCROLL_OFFSET_BITS: std::sync::atomic::AtomicU32 =
    std::sync::atomic::AtomicU32::new(0);
#[cfg(target_os = "android")]
static ARTCRAFT_MENU_SCROLL_LIMIT_BITS: std::sync::atomic::AtomicU32 =
    std::sync::atomic::AtomicU32::new(0);

#[cfg(target_os = "android")]
pub fn artcraft_menu_scroll_diagnostics() -> (u64, u64, f32, f32, f32, u64) {
    use std::sync::atomic::Ordering;
    (ARTCRAFT_MENU_SCROLL_EVENTS.load(Ordering::Relaxed),
     ARTCRAFT_MENU_TOUCH_SCROLL_EVENTS.load(Ordering::Relaxed),
     f32::from_bits(ARTCRAFT_MENU_SCROLL_OFFSET_BITS.load(Ordering::Relaxed)),
     f32::from_bits(ARTCRAFT_MENU_SCROLL_LIMIT_BITS.load(Ordering::Relaxed)),
     f32::from_bits(ARTCRAFT_MENU_LAST_REQUEST_BITS.load(Ordering::Relaxed)),
     ARTCRAFT_MENU_EDGE_BLOCKED.load(Ordering::Relaxed))
}

#[cfg(target_os = "android")]
pub fn artcraft_take_android_actions() -> u32 {""")
    # The Android trackpad wheel may be delivered alongside pointer samples.
    # Even if the native adapter filters the moving pointer, egui holds the
    # previous hover position in InputState, which can activate nested menus.
    # Prevent opening submenu popups only during the 180ms scroll gesture.
    text = replace_once(text,
        """    let id = SubMenu::id_from_widget_id(ui.next_auto_id());
    let open = MenuState::from_ui(ui, |state, _| state.open_item == Some(id));""",
        """    let id = SubMenu::id_from_widget_id(ui.next_auto_id());
    #[cfg(target_os = "android")]
    let suppress_hover = ui.ctx().data(|data|
        data.get_temp::<bool>(egui::Id::new("artcraft.trackpad_menu_scrolling"))
            .unwrap_or(false));
    #[cfg(not(target_os = "android"))]
    let suppress_hover = false;
    if suppress_hover {
        // Keep the top-level popup open; only close its hover-triggered child.
        MenuState::from_ui(ui, |state, _| state.open_item = None);
    }
    let open = !suppress_hover &&
        MenuState::from_ui(ui, |state, _| state.open_item == Some(id));""")
    text = replace_once(text,
        """    let response = ui.add(button.button);
    ui.style_mut().visuals.widgets.inactive = inactive;
    let clip = ui.clip_rect();""",
        """    let response = ui.add(button.button);
    ui.style_mut().visuals.widgets.inactive = inactive;
    if suppress_hover { return (response, None); }
    let clip = ui.clip_rect();""")
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
    # Long menus are already rendered inside egui::ScrollArea. The previous
    # Android patch accidentally disabled wheel handling (mouse_wheel:false)
    # and forced a per-frame scroll offset, so a mouse could not scroll it.
    # Return wheel/trackpad scrolling to egui's own persistent ScrollArea state,
    # preserve bounded menu height, and remove both paging buttons.
    text = replace_once(text,
        """        let mut scroll = egui::ScrollArea::vertical().max_height(max_height).min_scrolled_height(1.0);
        if ui.is_sizing_pass() {""",
        """        let mut scroll = egui::ScrollArea::vertical().max_height(max_height).min_scrolled_height(1.0);
        #[cfg(target_os = "android")]
        {
            // Input only while hovering the popup's scrollable list, not the canvas.
            // The scroll area owns its offset; do not overwrite it every frame.
            scroll = scroll
                .scroll_source(egui::containers::scroll_area::ScrollSource {
                    scroll_bar: true,
                    drag: egui::containers::scroll_area::DragScroll::OnTouch,
                    mouse_wheel: true,
                })
                .scroll_bar_visibility(egui::containers::scroll_area::ScrollBarVisibility::VisibleWhenNeeded);
        }
        #[cfg(not(target_os = "android"))]
        if ui.is_sizing_pass() {""")
    path.write_text(text)

if __name__ == "__main__":
    import sys
    apply(Path(sys.argv[1]))

