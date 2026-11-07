"""VectorCraft Android.12 startup: never show an unpainted native black frame.

The Android.11 splash proved that the native buffer can exist before the editor
is painted. Keep the branded opaque cover on top; remove it only on verified
UI paint. A long timeout exposes a nonblack retry/tap affordance rather than
automatically dismissing the cover onto a black surface.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    p=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=p.read_text()
    s=once(s,'        cover.postDelayed(this::dismissStartupCover, 15000);',
    '''        cover.setElevation(splashDp(48));
        cover.bringToFront();
        // A failed GPU initialization must not reveal a black SurfaceView.
        // A user may tap to inspect the native window after a slow startup.
        cover.postDelayed(() -> {
            if (!nativeEditorReady && startupCover == cover) {
                label.setText("VectorCraft is still loading… Tap to show editor");
                cover.setOnClickListener(v -> {
                    Log.w(TAG, "Startup cover bypassed by user after slow render");
                    dismissStartupCover();
                });
            }
        }, 15000);''')
    s=once(s,'''                nativeEditorReady = true;
                dismissStartupCover();
            }
        }, 20000);''',
    '''                // Keep a visible branded window rather than exposing an
                // unpainted black surface. The cover provides a manual bypass.
                startupStage("renderer_watchdog_active");
            }
        }, 20000);''')
    s=once(s,'''            if (verifiedNativeFrames >= 2) {
                startupStage("first_painted_editor");
                nativeEditorReady = true;
                dismissStartupCover();''',
    '''            // Two samples can include the partially initialized backdrop.
            // Wait for a third painted native frame then remove the cover
            // on the next UI traversal, with the renderer running underneath.
            if (verifiedNativeFrames >= 3) {
                startupStage("first_painted_editor");
                nativeEditorReady = true;
                splashHandler.postDelayed(this::dismissStartupCover, 180);''')
    s=once(s,'''        startupCover = cover;
        getWindow().addContentView(cover, new ViewGroup.LayoutParams(''',
    '''        startupCover = cover;
        getWindow().addContentView(cover, new ViewGroup.LayoutParams(''')
    # NativeActivity may attach its SurfaceView after the cover. Restore the
    # top overlay z-order after the first native traversal (once only).
    s=once(s,'        imeSetup();\n        handleIncomingFiles(getIntent());',
    '''        if (startupCover != null) {
            getWindow().getDecorView().post(() -> {
                if (startupCover != null) startupCover.bringToFront();
            });
        }
        imeSetup();
        handleIncomingFiles(getIntent());''')
    p.write_text(s)
    print("PASS: opaque startup cover held until 3 presented editor frames, never auto-black")


if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
