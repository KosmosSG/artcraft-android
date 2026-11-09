"""Android.23: fast native boot, true PhotoCraft wheel path and bounded trackpad steps.

Android.22 device test: black NativeActivity startup ~5-6s; menu/trackpad
stutter. Android.20 keyboard shortcut path passed and MUST NOT change.

No forced FPS, Vulkan quality downgrade, or edits to production keys.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    # Black for 5 seconds is worse than a responsive boot indicator. Keep
    # NativeActivity's unobstructed OS splash and present a lightweight,
    # dismissible Java progress view while the Rust/Vulkan editor initializes.
    # It is never used to gate Rust drawing or to wait on PixelCopy.
    s=once(s,'''        startupStage("photocraft_direct_native_launch");
        applyImmersiveFullscreen();''',
    '''        startupStage("photocraft_direct_native_launch");
        if (!nativeEditorReady) showStartupCover();
        applyImmersiveFullscreen();''')
    s=once(s,'''            nativeEditorReady = true;
            startupStage("native_editor_ui_ready");
            getWindow().getDecorView().postInvalidateOnAnimation();''',
    '''            nativeEditorReady = true;
            startupStage("native_editor_ui_ready");
            getWindow().getDecorView().postInvalidateOnAnimation();
            // The second Rust UI traversal precedes presentation. Give the
            // Vulkan swapchain a single frame and dismiss the loading layer,
            // never wait on an unreliable SurfaceView / PixelCopy probe.
            splashHandler.postDelayed(this::dismissStartupCover, 120);''')
    # Do not bring a static splash screen or 15s app-blocking gate back.
    assert "SplashScreen.installSplashScreen(this);" not in s
    assert "splash.setKeepOnScreenCondition" not in s
    java.write_text(s)

    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    # PhotoCraft leaves native wheel source classifications to egui. VectorCraft
    # labeled *every* point wheel as Trackpad, changing egui's physics for
    # popups AND the canvas. Keep original source/phase exactly as delivered.
    s=once(s,'''        classify_android_precision_scroll(raw);
        // Trigger high-refresh redraws only during actual gestures''',
    '''        // PhotoCraft parity: do NOT rewrite Android native wheel sources
        // into Trackpad. Let egui-winit deliver original wheel phase/delta;
        // this avoids competing inertial scroll paths on MagicOS.
        // Trigger high-refresh redraws only during actual gestures''')
    # The Android.22 scheduled 6.06ms wake on every gesture input in addition
    # to egui's own repaint. On devices struggling to present at 165Hz this
    # overworks the compositor and can increase variable frame latency.
    s=once(s,'''            ctx.request_repaint_after(std::time::Duration::from_micros(6060));
        }
        // The long Window/Effect popup lists''',
    '''            // Native input already caused a repaint. Do not queue another
            // artificial 165Hz frame; Vulkan and Android choose real cadence.
        }
        // The long Window/Effect popup lists''')
    # Keep egui font fallbacks, but don't re-check 20+ script families for every
    # single 165Hz UI frame. First pass is intentionally retained for proper
    # multilingual glyphs; subsequent checks are once / 350ms, and a triggered
    # Refresh Fonts forces one immediately.
    s=once(s,'''    vc_prune_last: Option<std::time::Instant>,''',
    '''    vc_prune_last: Option<std::time::Instant>,
    vc_font_fallback_last: Option<std::time::Instant>,''')
    s=once(s,'''                vc_prune_last: None,''',
    '''                vc_prune_last: None,
                vc_font_fallback_last: None,''')
    s=once(s,'''        system_fonts::install_system_fonts(ui.ctx());
        vectorcraft_ui_egui::menus::set_android_preferences''',
    '''        let vc_now=std::time::Instant::now();
        if self.vc_font_fallback_last.is_none_or(|last|
            vc_now.duration_since(last) >= std::time::Duration::from_millis(350))
            || self.font_reindex_pending {
            self.vc_font_fallback_last=Some(vc_now);
            system_fonts::install_system_fonts(ui.ctx());
        }
        vectorcraft_ui_egui::menus::set_android_preferences''')
    rust.write_text(s)

    dropdown=root/"source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
    s=dropdown.read_text()
    s=once(s,'''ui.ctx().request_repaint_after(std::time::Duration::from_micros(6060));''',
    '''// One immediate repaint is enough for new wheel input; egui handles
            // subsequent inertial frames without a fixed 165Hz wake loop.
            ui.ctx().request_repaint();''')
    dropdown.write_text(s)
    print("PASS: Android.23 responsive boot indicator; original native wheel events; no synthetic 165Hz redraw loop; cached font fallbacks")

if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
