//! Native Android pointer mapping, adapted from MostafaXS1/artcraft-android v0.2.0
//! vendor/egui-winit/src/pointer_icon.rs. Use SDK names instead of fork numeric IDs.
pub fn android_icon(cursor: egui::CursorIcon) -> &'static str {
    use egui::CursorIcon as C;
    match cursor {
        C::None => "TYPE_NULL",
        C::Text => "TYPE_TEXT", C::VerticalText => "TYPE_VERTICAL_TEXT",
        C::PointingHand => "TYPE_HAND", C::Crosshair => "TYPE_CROSSHAIR",
        C::ContextMenu => "TYPE_CONTEXT_MENU", C::Help => "TYPE_HELP",
        C::Cell => "TYPE_CELL", C::Alias => "TYPE_ALIAS", C::Copy => "TYPE_COPY",
        C::NoDrop | C::NotAllowed => "TYPE_NO_DROP",
        C::Grab => "TYPE_GRAB", C::Grabbing => "TYPE_GRABBING",
        C::ZoomIn => "TYPE_ZOOM_IN", C::ZoomOut => "TYPE_ZOOM_OUT",
        C::AllScroll | C::Move => "TYPE_ALL_SCROLL",
        C::ResizeHorizontal | C::ResizeColumn | C::ResizeEast | C::ResizeWest => "TYPE_HORIZONTAL_DOUBLE_ARROW",
        C::ResizeVertical | C::ResizeRow | C::ResizeNorth | C::ResizeSouth => "TYPE_VERTICAL_DOUBLE_ARROW",
        C::ResizeNwSe | C::ResizeNorthWest | C::ResizeSouthEast => "TYPE_TOP_LEFT_DIAGONAL_DOUBLE_ARROW",
        C::ResizeNeSw | C::ResizeNorthEast | C::ResizeSouthWest => "TYPE_TOP_RIGHT_DIAGONAL_DOUBLE_ARROW",
        C::Wait | C::Progress => "TYPE_WAIT",
        C::Default => "TYPE_ARROW",
    }
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn text_resize_hidden_and_default_do_not_keep_a_stale_icon() {
        use egui::CursorIcon as C;
        assert_eq!(android_icon(C::Text), "TYPE_TEXT");
        assert_eq!(android_icon(C::ResizeVertical), "TYPE_VERTICAL_DOUBLE_ARROW");
        assert_eq!(android_icon(C::ResizeNwSe), "TYPE_TOP_LEFT_DIAGONAL_DOUBLE_ARROW");
        assert_eq!(android_icon(C::None), "TYPE_NULL");
        assert_eq!(android_icon(C::Default), "TYPE_ARROW");
    }
}
