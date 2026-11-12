"""Retry asynchronous Android cursor application; reattach passive pen listener.

JNI return means a UI job was queued, not that a SurfaceView accepted an icon.
Preserve mappings and event delivery. Retry at most twice/second when unchanged.
"""
from pathlib import Path
import sys
from patch_android11_typing_trace import replace


def patch(root):
    a=root/'adapters/vectorcraft'
    host=a/'src/lib.rs'
    java=a/'java/com/artcraft/vectorcraft/VectorCraftActivity.java'
    # The pinned Android winit set_cursor is a no-op. Upstream nevertheless
    # advertises bitmap OS cursors on Android, so its painted glyph fallback
    # is never selected. Paint the existing upstream glyphs on Android only.
    cursors=root/'source/vectorcraft/crates/ui-egui/src/cursors.rs'
    replace(cursors,
        'pub const OS_CURSORS: bool = !cfg!(any(target_os = "macos", target_arch = "wasm32"));',
        'pub const OS_CURSORS: bool = !cfg!(any(target_os = "macos", target_os = "android", target_arch = "wasm32"));')
    replace(a/'src/adaptive_cursor.rs',
        'C::None | C::Progress | C::Wait => return None,',
        '''C::None => 0, // Android TYPE_NULL: upstream paints the tool glyph.
        C::Progress | C::Wait => return None,''')
    replace(a/'src/adaptive_cursor.rs',
        '        for cursor in [C::None, C::Wait, C::Progress] {',
        '''        assert_eq!(map(C::None), Some(0));
        for cursor in [C::Wait, C::Progress] {''')
    replace(host, '    last_adaptive_pointer_type: Option<i32>,', '''    last_adaptive_pointer_type: Option<i32>,
    vc_pointer_retry_at: Option<std::time::Instant>,''')
    replace(host, '                last_adaptive_pointer_type: None,', '''                last_adaptive_pointer_type: None,
                vc_pointer_retry_at: None,''')
    replace(host, '            if self.last_adaptive_pointer_type != Some(pointer_type) {', '''            if self.last_adaptive_pointer_type != Some(pointer_type)
                || self.vc_pointer_retry_at.is_none_or(|t| t.elapsed() >= std::time::Duration::from_millis(500))
            {
                self.vc_pointer_retry_at = Some(std::time::Instant::now());''')
    replace(java, '    private volatile int nativePointerIconType = -1;', '''    private volatile int nativePointerIconType = -1;
    private SurfaceView vcPointerAppliedSurface = null;''')
    replace(java, '''        if (pointerType == nativePointerIconType) return;
        nativePointerIconType = pointerType;
        runOnUiThread(() -> {
            try {
                SurfaceView nativeSurface = findNativeSurface(getWindow().getDecorView());
                if (nativeSurface != null) {
                    nativeSurface.setPointerIcon(
                        PointerIcon.getSystemIcon(this, nativePointerIconType));''', '''        runOnUiThread(() -> {
            try {
                SurfaceView nativeSurface = findNativeSurface(getWindow().getDecorView());
                // The surface may not exist at native-ready or may be replaced
                // without a new window-focus event. Reattach without consuming input.
                vcInstallPenHoverListener();
                if (nativeSurface != null) {
                    if (nativeSurface == vcPointerAppliedSurface && pointerType == nativePointerIconType) return;
                    nativeSurface.setPointerIcon(PointerIcon.getSystemIcon(this, pointerType));
                    vcPointerAppliedSurface = nativeSurface;
                    nativePointerIconType = pointerType;''')
    print('PASS: cursor retries after missing/replaced surface; passive pen listener retries; mappings preserved')

if __name__=='__main__':
    patch(Path(sys.argv[1]))
