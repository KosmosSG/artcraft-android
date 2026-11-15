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
    # Android.9 native-null-cursor candidate already maps egui None to
    # Android TYPE_NULL. Avoid trying to reapply the old reference patch.
    pointer_map=a/'src/adaptive_cursor.rs'
    pointer_source=pointer_map.read_text()
    if 'C::None => 0' not in pointer_source:
        replace(pointer_map,
            'C::None | C::Progress | C::Wait => return None,',
            '''C::None => 0, // Android TYPE_NULL: upstream paints the tool glyph.
        C::Progress | C::Wait => return None,''')
        replace(pointer_map,
            '        for cursor in [C::None, C::Wait, C::Progress] {',
            '''        assert_eq!(map(C::None), Some(0));
        for cursor in [C::Wait, C::Progress] {''')
    else:
        assert 'assert_eq!(map(C::None), Some(0));' in pointer_source
        assert 'C::Progress | C::Wait => return None' in pointer_source
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
    # Both the previous reference pointer host and the Android.9 TYPE_NULL
    # candidate need this asynchronous surface-replacement recovery. The
    # candidate already captures pointerType for its UI callback.
    candidate_java = '''        if (pointerType == nativePointerIconType) return;
        nativePointerIconType = pointerType;
        final int requestedPointerType = pointerType;
        runOnUiThread(() -> {
            try {
                SurfaceView nativeSurface = findNativeSurface(getWindow().getDecorView());
                if (nativeSurface != null) {
                    // TYPE_NULL (0) is an actual transparent OS pointer, not
                    // "ignore this request". Capture the requested type to
                    // avoid asynchronous UI dispatch applying a later type.
                    nativeSurface.setPointerIcon(
                        PointerIcon.getSystemIcon(this, requestedPointerType));'''
    reference_java = '''        if (pointerType == nativePointerIconType) return;
        nativePointerIconType = pointerType;
        runOnUiThread(() -> {
            try {
                SurfaceView nativeSurface = findNativeSurface(getWindow().getDecorView());
                if (nativeSurface != null) {
                    nativeSurface.setPointerIcon(
                        PointerIcon.getSystemIcon(this, nativePointerIconType));'''
    java_source = java.read_text()
    if candidate_java in java_source:
        before = candidate_java
    elif reference_java in java_source:
        before = reference_java
    else:
        raise RuntimeError("Unrecognized native pointer retry host; refuse unsafe rewrite")
    replace(java, before, '''        runOnUiThread(() -> {
            try {
                SurfaceView nativeSurface = findNativeSurface(getWindow().getDecorView());
                // The surface may not exist at native-ready or may be replaced
                // without a new window-focus event. Reattach without consuming input.
                vcInstallPenHoverListener();
                if (nativeSurface != null) {
                    if (nativeSurface == vcPointerAppliedSurface && pointerType == nativePointerIconType) return;
                    // TYPE_NULL is an actual OS cursor; never ignore pointerType=0.
                    nativeSurface.setPointerIcon(PointerIcon.getSystemIcon(this, pointerType));
                    vcPointerAppliedSurface = nativeSurface;
                    nativePointerIconType = pointerType;''')
    assert 'nativeSurface.setPointerIcon(PointerIcon.getSystemIcon(this, pointerType));' in java.read_text()
    assert 'vcPointerAppliedSurface = nativeSurface;' in java.read_text()
    print('PASS: cursor retries after missing/replaced surface; passive pen listener retries; mappings preserved')

if __name__=='__main__':
    patch(Path(sys.argv[1]))
