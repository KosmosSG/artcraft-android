#!/usr/bin/env python3
"""PDFCraft Android.6: guarded, CI-runner-only eframe close -> loop exit patch.

Applies ONLY when explicitly requested by a PDFCraft disposable APK workflow,
to the exact pinned eframe checkout in the isolated GitHub Actions job.
No changes to other ArtCraft apps, original repo, or production keys.

Source: storytold/egui at 6d518fc799681571963842f95b55a6b68431b15a.
The pinned eframe run.rs saves/destroys on CloseRequested, but only Exit calls
event_loop.exit(). Android run_app_on_demand can retain a stale native loop
after the Activity has gone, preventing relaunch until force-stop.
"""
from pathlib import Path
import os
import subprocess
import sys

PINNED = "6d518fc799681571963842f95b55a6b68431b15a"
OLD = '''            EventResult::CloseRequested => {
                // The windows need to be dropped whilst the event loop is running to allow for proper cleanup.
                self.winit_app.save_and_destroy();
                event_result
            }'''
NEW = '''            EventResult::CloseRequested => {
                // The windows need to be dropped whilst the event loop is running to allow for proper cleanup.
                self.winit_app.save_and_destroy();
                // PDFCRAFT_ANDROID6_EFRAME_CLOSE_EXITS_LOOP: eframe's CloseRequested
                // normally saves and destroys without setting exit=true. On Android
                // that leaves run_app_on_demand running after finishAndRemoveTask.
                // Explicitly exit the native loop AFTER on_exit/persistence, so
                // the NativeActivity thread can unwind for the next launch.
                #[cfg(target_os = "android")]
                {
                    log::info!("PDFCraftLifecycle: CloseRequested -> native event loop exit");
                    exit = true;
                }
                event_result
            }'''

def patch(source: str) -> str:
    if "PDFCRAFT_ANDROID6_EFRAME_CLOSE_EXITS_LOOP" in source:
        if source.count("PDFCRAFT_ANDROID6_EFRAME_CLOSE_EXITS_LOOP") != 1 or NEW not in source:
            raise ValueError("Partial or duplicate Android6 eframe patch")
        return source
    if source.count(OLD) != 1:
        raise ValueError("Pinned eframe CloseRequested handler changed; refuse to guess")
    if 'if exit {' not in source or 'event_loop.exit();' not in source:
        raise ValueError("Pinned eframe exit path is missing")
    return source.replace(OLD, NEW, 1)

def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit("usage: eframe_android_close_exit_patch.py")
    cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))).expanduser()
    candidates = list(cargo_home.glob("git/checkouts/egui-*/*/crates/eframe/src/native/run.rs"))
    verified = []
    for p in candidates:
        checkout = p.parents[4]
        sha = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        if sha == PINNED:
            verified.append(p)
    if len(verified) != 1:
        raise SystemExit(f"Expected one verified pinned eframe git checkout; found {len(verified)}. Fetch dependencies first.")
    dest = verified[0]
    old = dest.read_text()
    updated = patch(old)
    if updated != old:
        dest.write_text(updated)
    assert dest.read_text() == updated
    print(f"PASS: PDFCraft Android6 patched pinned eframe CloseRequested -> loop exit at {dest}")

if __name__ == "__main__":
    main()
