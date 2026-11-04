#!/usr/bin/env python3
"""PhotoCraft v0.19 Android.7 input fixes: copied API semantics from official
Android trackpad MotionEvent docs and menu/dialog routing from v0.19 upstream.

Always applied to disposable CI checkout after android6_ui_overlay.py.
Published stable PhotoCraft's native sources remain byte-identical.
"""
import argparse
from pathlib import Path
import subprocess

UPSTREAM="327c4cc82e737a3e0af7c147a477126d77525495"

def patch(path,old,new):
    data=path.read_text(encoding="utf-8")
    count=data.count(old)
    if count!=1: raise RuntimeError(f"Android.7 unreviewed anchor in {path}: {count}")
    path.write_text(data.replace(old,new,1),encoding="utf-8")
    print(f"Android.7 adapted: {path}")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--upstream",type=Path,required=True)
    a.add_argument("--adapter",type=Path,required=True)
    opt=a.parse_args()
    actual=subprocess.check_output(["git","-C",str(opt.upstream),"rev-parse","HEAD"],text=True).strip()
    if actual!=UPSTREAM: raise RuntimeError(f"Unexpected upstream {actual}")
    host=opt.adapter/"src/lib.rs"
    act=opt.adapter/"java/com/artcraft/photocraft/PhotoCraftActivity.java"
    menus=opt.upstream/"crates/ui-egui/src/menus.rs"
    dialog=opt.upstream/"crates/ui-egui/src/dialogs/discard_ui.rs"

    # The reference's Pad::reserve uses this dedicated strip. Upstream UI
    # respects edge_strip and lays the panels out to the side; the previous
    # floating Area obscured the Properties panel.
    patch(host,
'''        self.inner.ui(ui, _frame);
''',
'''        self.shortcut_pad.reserve(ui);
        self.inner.ui(ui, _frame);
''')

    # The upstream discard UI consumes Key::Y/N/C from egui, but the Android
    # IME keyboard may never produce it. An explicit one-frame dialog-only
    # command queue preserves modal isolation without stealing typed text.
    patch(menus,
'''pub fn artcraft_take_pc_menu_action() -> u8 {
    ARTCRAFT_PC_MENU_ACTION.swap(0, std::sync::atomic::Ordering::Relaxed)
}
''',
'''pub fn artcraft_take_pc_menu_action() -> u8 {
    ARTCRAFT_PC_MENU_ACTION.swap(0, std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
static ARTCRAFT_DIALOG_KEY: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);
#[cfg(target_os = "android")]
pub fn artcraft_queue_dialog_key(key: u8) {
    ARTCRAFT_DIALOG_KEY.store(key, std::sync::atomic::Ordering::Relaxed);
}
#[cfg(target_os = "android")]
pub fn artcraft_take_dialog_key() -> u8 {
    ARTCRAFT_DIALOG_KEY.swap(0, std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
pub fn artcraft_discard_active(app: &crate::PhotocraftApp) -> bool {
    app.discard.is_some()
}
''')
    patch(host,
'''        hardware_keys::recover_text_keys(
            raw, ctx, self.inner.ui.text_edit.is_some(),
        );
''',
'''        hardware_keys::recover_text_keys(
            raw, ctx, self.inner.ui.text_edit.is_some(),
        );
        if photocraft_ui_egui::menus::artcraft_discard_active(&self.inner) {
            // The modal owns these keys; even an IME Text("n") should
            // dismiss the modal instead of being consumed by old focus.
            for event in &raw.events {
                let key = match event {
                    egui::Event::Key { key: egui::Key::Y, pressed: true, .. } => 1,
                    egui::Event::Key { key: egui::Key::N, pressed: true, .. } => 2,
                    egui::Event::Key { key: egui::Key::C, pressed: true, .. } => 3,
                    egui::Event::Text(txt) if txt.eq_ignore_ascii_case("y") => 1,
                    egui::Event::Text(txt) if txt.eq_ignore_ascii_case("n") => 2,
                    egui::Event::Text(txt) if txt.eq_ignore_ascii_case("c") => 3,
                    _ => 0,
                };
                if key != 0 {
                    photocraft_ui_egui::menus::artcraft_queue_dialog_key(key);
                }
            }
        } else {
            // Ensure a key from an older prompt cannot answer a new one.
            let _ = photocraft_ui_egui::menus::artcraft_take_dialog_key();
        }
''')
    patch(dialog,
'''    let mut answer = ctx.input_mut(|i| buttons.iter().find(|b| b.2.is_some_and(|k| i.consume_key(egui::Modifiers::NONE, k))).map(|b| b.4));
''',
'''    let mut answer = ctx.input_mut(|i| buttons.iter().find(|b| b.2.is_some_and(|k| i.consume_key(egui::Modifiers::NONE, k))).map(|b| b.4));
    #[cfg(target_os = "android")]
    {
        let direct = match crate::menus::artcraft_take_dialog_key() {
            1 => Some(Answer::Save), 2 => Some(Answer::Discard),
            3 => Some(Answer::Cancel), _ => None,
        };
        if direct.is_some() { answer = direct; }
    }
''')

    # Android API 34+: physical touchpad 2-finger ACTION_MOVE scroll can be
    # SOURCE_MOUSE with pointerCount=1; unlike AXIS_VSCROLL, the effective
    # distance is AXIS_GESTURE_SCROLL_X/Y_DISTANCE in pixels.
    # Under Android 15 the old code completely ignored these events.
    patch(act,
'''            float vertical = event.getAxisValue(android.view.MotionEvent.AXIS_VSCROLL);
            float horizontal = event.getAxisValue(android.view.MotionEvent.AXIS_HSCROLL);
''',
'''            float vertical = event.getAxisValue(android.view.MotionEvent.AXIS_VSCROLL);
            float horizontal = event.getAxisValue(android.view.MotionEvent.AXIS_HSCROLL);
            if (android.os.Build.VERSION.SDK_INT >= 34
                    && Math.abs(vertical) < 0.0001f && Math.abs(horizontal) < 0.0001f) {
                // Android gesture axes are in DISPLAY PIXELS, not wheel steps.
                horizontal = event.getAxisValue(
                    android.view.MotionEvent.AXIS_GESTURE_SCROLL_X_DISTANCE) / 42.0f;
                vertical = -event.getAxisValue(
                    android.view.MotionEvent.AXIS_GESTURE_SCROLL_Y_DISTANCE) / 42.0f;
            }
''')
    # Some OEMs dispatch these trackpad axes as ACTION_MOVE, not ACTION_SCROLL.
    patch(act,
'''        return super.dispatchGenericMotionEvent(event);
''',
'''        if (android.os.Build.VERSION.SDK_INT >= 34
                && event.getActionMasked() == android.view.MotionEvent.ACTION_MOVE) {
            float dx = event.getAxisValue(
                android.view.MotionEvent.AXIS_GESTURE_SCROLL_X_DISTANCE);
            float dy = event.getAxisValue(
                android.view.MotionEvent.AXIS_GESTURE_SCROLL_Y_DISTANCE);
            if ((Math.abs(dx) > 0.01f || Math.abs(dy) > 0.01f)
                    && artcraftTrackpadScroll.size() < 32) {
                View decor = getWindow().getDecorView();
                artcraftTrackpadScroll.offer(dx / 42.0f + "," + (-dy / 42.0f) + ","
                    + event.getX() + "," + event.getY() + ","
                    + decor.getWidth() + "," + decor.getHeight());
            }
        }
        return super.dispatchGenericMotionEvent(event);
''')
    print("Android.7: dedicated Shortcut Pad strip, Android 14+ gesture axes and modal dialog hotkeys staged")

if __name__=="__main__":
    main()
