//! Android adaptive cursor bridge, selectively ported from
//! MostafaXS1/artcraft-android v0.2.0 vendor/egui-winit/src/pointer_icon.rs.
//!
//! Preserve the user's existing mouse/trackpad, touchscreen, GPU and keyboard
//! implementation. Only translate egui's resolved CursorIcon into the Android
//! framework's native PointerIcon constant (API 24+). No custom APK assets or
//! touch input replacement is necessary.

/// Native android.view.PointerIcon types. These have been available since API 24.
pub fn native_pointer_icon(cursor: egui::CursorIcon) -> Option<i32> {
    use egui::CursorIcon as C;
    Some(match cursor {
        C::Default => 1000,                  // TYPE_ARROW
        C::ContextMenu => 1001,
        C::PointingHand => 1002,
        C::Help => 1003,
        C::Cell => 1006,
        C::Crosshair => 1007,
        C::Text | C::VerticalText => 1008,  // TYPE_TEXT
        C::Alias => 1010,
        C::Copy => 1011,
        C::NoDrop => 1012,
        C::NotAllowed => 1013,
        C::ResizeHorizontal | C::ResizeColumn |
        C::ResizeEast | C::ResizeWest => 1014,
        C::Move | C::AllScroll => 1015,
        C::Grab => 1016,
        C::Grabbing => 1017,
        C::ZoomIn => 1018,
        C::ZoomOut => 1019,
        C::ResizeVertical | C::ResizeRow |
        C::ResizeNorth | C::ResizeSouth => 1021,
        C::ResizeNwSe | C::ResizeNorthWest |
        C::ResizeSouthEast => 1022,
        C::ResizeNeSw | C::ResizeNorthEast |
        C::ResizeSouthWest => 1023,
        // No Android framework equivalent: preserve the current pointer.
        C::None | C::Progress | C::Wait => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::native_pointer_icon as map;
    use egui::CursorIcon as C;

    #[test]
    fn text_links_and_precision_match_reference_release() {
        assert_eq!(map(C::Text), Some(1008));
        assert_eq!(map(C::VerticalText), Some(1008));
        assert_eq!(map(C::PointingHand), Some(1002));
        assert_eq!(map(C::Crosshair), Some(1007));
        assert_eq!(map(C::Default), Some(1000));
    }

    #[test]
    fn resize_tools_and_drag_shapes_preserve_orientation() {
        assert_eq!(map(C::ResizeHorizontal), Some(1014));
        assert_eq!(map(C::ResizeVertical), Some(1021));
        assert_eq!(map(C::ResizeNwSe), Some(1022));
        assert_eq!(map(C::ResizeNeSw), Some(1023));
        assert_eq!(map(C::Grabbing), Some(1017));
        assert_eq!(map(C::Move), Some(1015));
    }

    #[test]
    fn no_equivalent_does_not_change_native_pointer() {
        for cursor in [C::None, C::Wait, C::Progress] {
            assert_eq!(map(cursor), None);
        }
    }
}
