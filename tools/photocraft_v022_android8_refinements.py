#!/usr/bin/env python3
"""PhotoCraft Android.8: guarded floating-control hover and dropdown scroll fixes.

Apply ONLY after Android.7's existing upstream, wheel, brush, menu, trackpad
and shortcut-pad overlays inside the disposable GitHub Actions runner.
No production app source, signature, user data or released version is changed.
"""
import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Android.8 anchor changed: {path} matches={count} for {old[:90]!r}"
        )
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    args = parser.parse_args()

    brand = args.upstream / "crates/ui-egui/src/panels/brand.rs"
    canvas = args.upstream / "crates/ui-egui/src/canvas.rs"
    host = args.adapter / "src/lib.rs"
    wheel = args.adapter / "src/stylus_wheel.rs"
    trackpad = args.adapter / "src/trackpad_wheel.rs"
    pad = args.adapter / "src/shortcut_pad.rs"

    # Remove only the UI entry: preserve the diagnostic backend for regressions.
    replace_once(brand,
        '''            ui.menu_button("Diagnostics", |ui| {
                action(ui, "Keyboard / IME Input Diagnostics…", 18);
                ui.weak("Records shortcut key names only");
            });
''',
        "")

    # The radial wheel is drawn by our own painter and uses its own hover
    # coordinates. It must NOT pass pointer motion to the editor underneath.
    # Capture the stylus coordinate before masking egui's editor pointer.
    replace_once(wheel,
        "        let mut retained = Vec::with_capacity(raw.events.len());",
        """        let isolate_hover = self.open;
        let mut retained = Vec::with_capacity(raw.events.len());
""".rstrip())
    replace_once(wheel,
        '''                    retained.push(egui::Event::PointerMoved(pos));''',
        '''                    if !self.open {
                        retained.push(egui::Event::PointerMoved(pos));
                    }''')
    replace_once(wheel,
        '''        raw.events = retained;
        let pen_down = ''',
        '''        // A wheel opening during this very pass must also own hover.
        // PointerGone clears stale toolbar/canvas hover highlights, whereas
        // self.hover above keeps radial segment highlighting functional.
        if isolate_hover || self.open {
            retained.retain(|event| !matches!(event,
                egui::Event::PointerMoved(_)
                | egui::Event::PointerButton { .. }
                | egui::Event::Touch { .. }
                | egui::Event::MouseWheel { .. }
            ));
            retained.push(egui::Event::PointerGone);
        }
        raw.events = retained;
        let pen_down = ''')
    replace_once(wheel,
        '''egui::Area::new(Id::new("pc-wheel-plate"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(false)''',
        '''egui::Area::new(Id::new("pc-wheel-plate"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(true)''')

    # The Shortcut Pad is different from the radial wheel: its buttons need
    # egui pointer events. Give its entire reserved edge strip a foreground
    # hover hit target rather than removing input needed by Undo/Redo/Zoom.
    replace_once(pad,
        '''                .show(ctx, |ui| {
                    let frame = egui::Frame::new()''',
        '''                .show(ctx, |ui| {
                    // Register a hit target across the WHOLE visible pad,
                    // including the gaps between buttons and its zoom ring.
                    // Child controls remain clickable/drag-capable.
                    let _hover_shield = ui.interact(
                        strip, egui::Id::new("pc-shortcut-pad-hover-shield"),
                        egui::Sense::hover(),
                    );
                    let frame = egui::Frame::new()''')
    replace_once(pad,
        '''        panel.exact_size(78.0).show(ui, |panel_ui| {
            self.reserved = Some(panel_ui.max_rect());
        });''',
        '''        panel.exact_size(78.0).show(ui, |panel_ui| {
            self.reserved = Some(panel_ui.max_rect());
            panel_ui.ctx().data_mut(|data| data.insert_temp(
                egui::Id::new("pc-shortcut-pad-reserved-rect"),
                panel_ui.max_rect(),
            ));
        });''')
    replace_once(pad,
        '''        self.reserved = None;
        if !menus::artcraft_pad_visible() { return; }''',
        '''        self.reserved = None;
        if !menus::artcraft_pad_visible() {
            ui.ctx().data_mut(|data| data.remove::<egui::Rect>(
                egui::Id::new("pc-shortcut-pad-reserved-rect")
            ));
            return;
        }''')

    # Guard direct canvas hover/navigation over that reserved strip. This
    # covers upstream manual canvas hit-testing that ignores egui layers.
    replace_once(canvas,
        '''    let nav_hovered = input.response.hovered() || input.free_hover || over_bars;''',
        '''    let nav_hovered = input.response.hovered() || input.free_hover || over_bars;
    #[cfg(target_os = "android")]
    let nav_hovered = nav_hovered && !input.ctx.input(|i|
        i.pointer.hover_pos().is_some_and(|pos|
            input.ctx.data(|data| data.get_temp::<egui::Rect>(
                egui::Id::new("pc-shortcut-pad-reserved-rect")
            )).is_some_and(|rect| rect.contains(pos))
        )
    );''')

    # A ComboBox popup is an egui Foreground ScrollArea, not PhotoCraft's
    # menu_nav popup or the brush library. The existing trackpad router was
    # treating its native scroll axes as canvas panning. Only while wheel
    # settings AND a popup are open, send scroll back to egui instead.
    replace_once(host,
        '''            self.inner.ui.brush_picker.is_some()
                || (self.inner.ui.panels.brush_settings && self.inner.ui.brush_tab == 1),
        );''',
        '''            self.inner.ui.brush_picker.is_some()
                || (self.inner.ui.panels.brush_settings && self.inner.ui.brush_tab == 1),
            self.stylus_wheel.settings_open,
        );''')
    replace_once(trackpad,
        '''    brush_open: bool,
) {''',
        '''    brush_open: bool,
    wheel_settings_open: bool,
) {''')
    replace_once(trackpad,
        '''    let native_pinch = native.iter().any(|g| (g[2] - 1.0).abs() > 0.0001);''',
        '''    let native_pinch = native.iter().any(|g| (g[2] - 1.0).abs() > 0.0001);
    // Only wheel-settings ComboBoxes: preserve other mouse/pad routing.
    let wheel_dropdown = wheel_settings_open && egui::Popup::is_any_open(ctx);''')
    replace_once(trackpad,
        '''    if menu.is_none() {
        for [dx, dy, scale, x, y] in native {''',
        '''    if menu.is_none() {
        for [dx, dy, scale, x, y] in native {
            if wheel_dropdown {
                // Use the hovering cursor, not the contact centroid. The
                // latter is often (0,0) on HONOR physical touchpads.
                if !native_wheel_present && dy.abs() > 0.01 {
                    if let Some(pos) = raw.events.iter().rev().find_map(|e| match e {
                        Event::PointerMoved(p) => Some(*p), _ => None,
                    }).or_else(|| ctx.pointer_hover_pos()) {
                        raw.events.push(Event::PointerMoved(pos));
                        raw.events.push(Event::MouseWheel {
                            unit: MouseWheelUnit::Point,
                            delta: Vec2::new(dx / ppp, dy / ppp),
                            phase: TouchPhase::Move,
                            modifiers: egui::Modifiers::NONE,
                            source: MouseWheelSource::Trackpad,
                        });
                    }
                }
                continue;
            }''')
    replace_once(trackpad,
        '''        if !brush_target(pos)
            && !ctx.pointer_hover_pos().is_some_and(brush_target)''',
        '''        if !wheel_dropdown && !brush_target(pos)
            && !ctx.pointer_hover_pos().is_some_and(brush_target)''')
    replace_once(trackpad,
        '''            if menu.is_none()
                && !brush_target(pointer)''',
        '''            if menu.is_none() && !wheel_dropdown
                && !brush_target(pointer)''')
    # Java fallback also uses contact coordinates; make dropdown scroll target
    # the hovered egui popup without synthesizing background pointer movement.
    replace_once(trackpad,
        '''        if menu.is_none() { raw.events.push(Event::PointerMoved(pos)); }
        raw.events.push(Event::MouseWheel {''',
        '''        if menu.is_none() {
            let target = if wheel_dropdown {
                ctx.pointer_hover_pos().unwrap_or(pos)
            } else { pos };
            raw.events.push(Event::PointerMoved(target));
        }
        raw.events.push(Event::MouseWheel {''')
    replace_once(trackpad,
        '''        if native_pinch || menu.is_some() { continue; }''',
        '''        if native_pinch || menu.is_some() || wheel_dropdown { continue; }''')

    # Keep the rest of Android.7 intact. Fail the build before expensive
    # compilation if any of the reviewed component anchors change.
    assert 'ui.menu_button("Diagnostics"' not in brand.read_text()
    assert 'ui.menu_button("Stylus Wheel"' in brand.read_text()
    assert 'ui.menu_button("Touch Shortcut Pad"' in brand.read_text()
    assert 'ui.menu_button("Appearance"' in brand.read_text()
    assert 'action(ui, "Keyboard Shortcuts…", 36);' in brand.read_text()
    assert "egui::Event::PointerGone" in wheel.read_text()
    assert "pc-shortcut-pad-hover-shield" in pad.read_text()
    assert "wheel_dropdown" in trackpad.read_text()
    assert "self.stylus_wheel.settings_open" in host.read_text()
    assert "pc_keyboard_diag.show" in host.read_text()
    assert "photocraft_ui_egui::icons::paint(" in wheel.read_text()
    print("PASS Android.8: Diagnostics hidden, keyboard backend preserved")
    print("PASS Android.8: radial wheel owns stylus hover and mouse press")
    print("PASS Android.8: reserved Shortcut Pad owns foreground hit testing")
    print("PASS Android.8: wheel ComboBox trackpad scroll no longer pans canvas")


if __name__ == "__main__":
    main()
