"""Android.25: restore the exact gesture router from published reference v0.5.0.

The pinned MostafaXS1 builder 52308fb already contains the same
vendor/winit/src/platform_impl/android/mod.rs as published v0.5.0.
Android.23 changed that path by adding unclassified fallback dispatch and
per-packet clipping, and Android.24 changed the clipping thresholds.
Restore only the released pad gesture block. Retain lifecycle, hardware
keyboard, IME, Ctrl+W / D/S/C and all other owner customizations.

Fail closed if source anchors, release reference, or ordering drift.
"""
from pathlib import Path
import shutil
import sys

START_PATCHED = "                let reported_pad_gesture = match motion_event.classification() {"
START_RELEASE = "                let pad_gesture = match motion_event.classification() {"
END = "\n                match motion_event.action() {\n                    // Hover:"


def once(s: str, old: str, new: str) -> str:
    matches=s.count(old)
    if matches != 1:
        raise ValueError(f"Android.25 stale anchor ({matches} matches): {old[:90]!r}")
    return s.replace(old, new, 1)


def restore_winit(winit_root: Path, pinned_reference: Path) -> None:
    target=winit_root/"src/platform_impl/android/mod.rs"
    current=target.read_text()
    reference=pinned_reference.read_text()
    if reference.count(START_RELEASE)!=1 or reference.count(END)!=1:
        raise ValueError("Pinned published gesture reference changed")
    if current.count(START_PATCHED)!=1 or current.count(END)!=1:
        raise ValueError("Final vendored gesture implementation has drifted")
    a=current.index(START_PATCHED)
    b=current.index(END, a)
    ra=reference.index(START_RELEASE)
    rb=reference.index(END,ra)
    existing=current[a:b]
    published=reference[ra:rb]
    for required in (
        "unclassified_pad",
        "pad_fallback_gesture",
        "clamp(-160.0, 160.0)",
        "factor.clamp(0.75, 1.33)",
        "return input_status;",
    ):
        if required not in existing:
            raise ValueError(f"Expected prior experimental gesture path missing: {required}")
    if "PadGesture::Pinch" not in published or "PadGesture::Scroll" not in published:
        raise ValueError("Published reference has no scroll/pinch router")
    current=current[:a]+published+current[b:]
    current=once(current,"    pad_fallback_gesture: PadGesture,\n","")
    current=once(current,"            pad_fallback_gesture: PadGesture::None,\n","")
    if "unclassified_pad" in current or "pad_fallback_gesture" in current:
        raise ValueError("Experimental fallback remains outside restored block")
    if published not in current:
        raise ValueError("Reference gesture implementation not preserved")
    target.write_text(current)
    print("PASS: Android.25 exact v0.5.0 published trackpad pan/pinch router restored")


def patch_staged(root: Path) -> None:
    # Source uses explicit egui wheel handling for the popup, without a second
    # artificial integrator or wheel attenuation. Android.24 still reduced
    # wheel deltas to 90% and installed a popup-specific scroll state.
    dropdown=root/"source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
    s=dropdown.read_text()
    start='        let area = egui::ScrollArea::vertical().scroll_source('
    end='        area.show(ui, add_contents).inner'
    if s.count(start)!=1 or s.count(end)!=1:
        raise ValueError("Android.25 popup ScrollArea source drift")
    a=s.index(start)
    b=s.index(end,a)+len(end)
    existing=s[a:b]
    for required in ("vectorcraft-android-smooth-menu","wheel_scroll_multiplier(egui::vec2(1.0, 0.90))","request_repaint"):
        if required not in existing:
            raise ValueError(f"Expected Android.24 popup override missing: {required}")
    release_style='''        egui::ScrollArea::vertical()
            .scroll_source(egui::containers::scroll_area::ScrollSource::ALL)
            .max_height(room)
            .min_scrolled_height(room)
            .show(ui, add_contents).inner'''
    s=s[:a]+release_style+s[b:]
    dropdown.write_text(s)

    # Report precise startup boundaries without changing the startup-cover
    # behavior again. Stage logs are strictly timing metadata, no user data.
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    j=java.read_text()
    j=once(j,'        super.onCreate(savedInstanceState);\n        showStartupCover();',
        '        startupStage("android25_before_native_onCreate");\n'
        '        super.onCreate(savedInstanceState);\n'
        '        startupStage("android25_after_native_onCreate");\n'
        '        showStartupCover();')
    java.write_text(j)
    rust=root/"adapters/vectorcraft/src/lib.rs"
    r=rust.read_text()
    r=once(r,'    install_persist_env(&android_app);\n    system_fonts::install_font_env(&android_app);',
        '    log::info!("VC_BOOT25 before_font_environment={}ms", startup_instant.elapsed().as_millis());\n'
        '    install_persist_env(&android_app);\n'
        '    system_fonts::install_font_env(&android_app);\n'
        '    log::info!("VC_BOOT25 after_font_environment={}ms", startup_instant.elapsed().as_millis());')
    rust.write_text(r)
    print("PASS: Android.25 direct popup scrolling and startup-stage instrumentation")


def install_build_hook(builder_root: Path) -> None:
    tools=builder_root/"tools"
    tools.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__),tools/"vectorcraft_android25.py")
    sh=builder_root/"lib/build-common.sh"
    s=sh.read_text()
    anchor='python3 "$ROOT/tools/vectorcraft_android24.py" "$SRC/vendor/winit" --winit'
    s=once(s,anchor,anchor+'\n    python3 "$ROOT/tools/vectorcraft_android25.py" "$SRC/vendor/winit" --restore-reference')
    sh.write_text(s)
    print("PASS: Android.25 published-reference restore hooked after Android.24, final vendored winit")


if __name__=="__main__":
    path=Path(sys.argv[1])
    if "--restore-reference" in sys.argv[2:]:
        builder=Path(__file__).resolve().parent.parent
        restore_winit(path,builder/"vendor/winit/src/platform_impl/android/mod.rs")
    elif "--install-hook" in sys.argv[2:]:
        install_build_hook(path)
    else:
        patch_staged(path)
