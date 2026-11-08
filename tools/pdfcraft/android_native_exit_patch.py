#!/usr/bin/env python3
"""PDFCraft-only Android NativeActivity final Destroy -> winit loop exit guard.

Why: the pinned winit Android backend currently logs MainEvent::Destroy as TODO.
After egui Close triggers eframe save_and_destroy / AndroidShell::on_exit and
Java finishAndRemoveTask, the native event loop can keep waiting instead of
returning from run_app_on_demand. The old Rust AndroidApp then remains alive in
the process and MagicOS may relaunch into a stale native loop. A force stop
kills this abandoned loop; clearing user data is NOT necessary.

This is deliberately applied only to the staged PDFCraft v0.19.0 vendor/winit,
never to the repository's shared vendor/winit or other ArtCraft apps.
Fail closed if pinned upstream backend changes.
"""
from pathlib import Path
import sys

ORIGINAL = '''                MainEvent::Destroy => {
                    // XXX: maybe exit mainloop to drop things before being
                    // killed by the OS?
                    warn!("TODO: forward onDestroy notification to application");
                },'''

REPLACEMENT = '''                MainEvent::Destroy => {
                    // PDFCRAFT_ANDROID5_DESTROY_EXITS_NATIVE_LOOP:
                    // Android's Java Activity is being destroyed. The native
                    // event loop must return so android_main can finish and
                    // a subsequent launcher/document intent starts fresh.
                    // Do NOT call std::process::exit or delete user data.
                    log::info!("PDFCraftLifecycle: Android Destroy -> exit winit native loop");
                    self.running = false;
                    self.window_target.p.exit();
                },'''

def patch(source: str) -> str:
    if "PDFCRAFT_ANDROID5_DESTROY_EXITS_NATIVE_LOOP" in source:
        if source.count("PDFCRAFT_ANDROID5_DESTROY_EXITS_NATIVE_LOOP") != 1:
            raise ValueError("Duplicate PDFCraft lifecycle patches; refusing")
        if REPLACEMENT not in source:
            raise ValueError("Partial PDFCraft native exit patch; refusing")
        return source
    if source.count(ORIGINAL) != 1:
        raise ValueError("Pinned Android winit Destroy handler changed; review required")
    return source.replace(ORIGINAL, REPLACEMENT, 1)

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: android_native_exit_patch.py <staged_vendor_winit>")
    root = Path(sys.argv[1]).resolve()
    src = root / "src/platform_impl/android/mod.rs"
    if not src.is_file() or "vendor/winit" not in src.as_posix():
        raise SystemExit("Expected staged vendor/winit Android backend only")
    original = src.read_text()
    updated = patch(original)
    if updated != original:
        src.write_text(updated)
    print("PASS: PDFCraft Android Destroy exits native winit loop; user data unchanged")

if __name__ == "__main__":
    main()
