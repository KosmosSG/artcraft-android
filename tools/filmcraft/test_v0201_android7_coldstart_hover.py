#!/usr/bin/env python3
"""Android.7: regression guards for genuine hover before any first touch.

Reference: DeckCraft Android.7/8 early hover wakeup at 80ms, adapted to
FilmCraft's JNI GameActivity/SufaceView bridge. This is a source-level
regression, not a replacement for MagicPad hardware validation.
"""
from pathlib import Path
import subprocess
import sys

here=Path(__file__).resolve().parent
wheel=(here/"filmcraft_stylus_wheel.rs").read_text()
stage=(here/"stage_v0201_wheel.py").read_text()
# Retain the Android.6 wheel, updater, artwork, and hardened isolated wrapper.
subprocess.run([sys.executable,str(here/"test_v0201_android6_hover_icons_size.py")],
               check=True)
marker="ctx.request_repaint_after(Duration::from_millis(80));"
capture=wheel.split("pub fn capture(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput,\n        document_epoch: u64) {",1)
if len(capture) != 2: raise SystemExit("STOP: FilmCraft wheel capture entry missing")
prefix=capture[1].split("if let Some((button, hover)) = self.poll_java(document_epoch)",1)
if len(prefix)!=2 or prefix[0].count(marker)!=1:
    raise SystemExit("STOP: 80ms poll must precede first native hover read")
if "if !self.enabled" in prefix[0] or "if self.open" in prefix[0]:
    raise SystemExit("STOP: early polling cannot depend on enable/open state")
for label,expected in (
    ("genuine stylus-only hover", "e.getToolType(0)"),
    ("hover-enter handling", "android.view.MotionEvent.ACTION_HOVER_ENTER"),
    ("native SurfaceView listener", "surface.setOnHoverListener(fcWheelSurfaceHover);"),
    ("first-resume hook", "fcWheelPrepareEarlyHover();"),
    ("non-consuming native hover", "return false; // ALWAYS allow GameActivity/winit to process input"),
    ("edge-safe hover exit", "fcWheelHover.set(-1L);"),
):
    if expected not in stage:
        raise SystemExit(f"STOP: missing FilmCraft cold-start hover input: {label}")
if stage.count("@Override public void onWindowFocusChanged("):
    raise SystemExit("STOP: never duplicate GameActivity window-focus override")
if "raw.events.push(egui::Event::PointerMoved(pos));" not in wheel:
    raise SystemExit("STOP: genuine pointer movement not inserted")
if "self.pen_hover = Some(pos)" not in wheel:
    raise SystemExit("STOP: genuine hover cursor source not stored")
print("PASS: pre-touch real stylus hover polled from first native frame at 80ms")
print("PASS: no simulated pointer, wheel default 75/80, secure updater and input isolation preserved")
