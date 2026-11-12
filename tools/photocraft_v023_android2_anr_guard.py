#!/usr/bin/env python3
"""PhotoCraft v0.23.0 Android.2 — isolated first-document ANR compositor guard.

Only touches the checked-out upstream source on the disposable CI runner.
The release branch, native Android adapter, signing keys and published APK
are not modified. This is a diagnostic, device-test-only mitigation:
keep wgpu canvas drawing/upload enabled, but use the CPU layer compositor
on Android so the first document cannot synchronously compile GPU pipelines.
"""
import argparse
from pathlib import Path

ANCHOR = "            compositor_build: Default::default(),"
REPLACEMENT = """            // PHOTOCRAFT_ANDROID2_FIRST_DOCUMENT_ANR_GUARD
            // Test-only Android isolation: do not compile the GPU *layer*
            // compositor on the UI thread while opening the first document.
            // The existing wgpu *canvas* and its GPU-accelerated display
            // remain enabled, and layer blending falls back to CPU.
            compositor_build: {
                let slot: compositor_build::Slot = Default::default();
                #[cfg(target_os = "android")]
                {
                    *slot.lock().unwrap_or_else(std::sync::PoisonError::into_inner) =
                        compositor_build::BuildState::Failed(
                            photocraft_gpu::Unsupported(
                                "Android.2 first-document ANR isolation: CPU layer compositor".into(),
                            ),
                        );
                }
                slot
            },"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    file = args.upstream / "crates/ui-egui/src/canvas/gpu_canvas.rs"
    source = file.read_text(encoding="utf-8")

    if source.count(ANCHOR) != 1:
        raise SystemExit("REJECT: v0.23 compositor initialization anchor changed")
    if "PHOTOCRAFT_ANDROID2_FIRST_DOCUMENT_ANR_GUARD" in source:
        raise SystemExit("REJECT: duplicate Android.2 compositor isolation")
    if "match std::mem::replace(&mut *state, compositor_build::BuildState::Adopted)" not in source:
        raise SystemExit("REJECT: upstream composite fallback state machine changed")
    if "compositor_build::BuildState::Failed(error) =>" not in source:
        raise SystemExit("REJECT: upstream CPU compositor fallback disappeared")
    if "pub fn start_compositor(&self, ctx: &egui::Context)" not in source:
        raise SystemExit("REJECT: asynchronous compositor preparation changed")
    file.write_text(source.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")

    updated = file.read_text(encoding="utf-8")
    assert updated.count("PHOTOCRAFT_ANDROID2_FIRST_DOCUMENT_ANR_GUARD") == 1
    assert updated.count(ANCHOR) == 0
    assert "pub fn gpu_view_ok(" in updated
    assert "pub fn refresh_with(" in updated
    assert "#[cfg(target_os = \"android\")]" in updated
    print("PASS: Android-only initial GPU compositor failure state avoids UI-thread pipeline compilation")
    print("PASS: existing GPU canvas, background redraw, document and tool paths unchanged")
    print("NOTE: runtime ANR fix remains unverified until HONOR MagicPad 4 test")


if __name__ == "__main__":
    main()
