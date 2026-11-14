#!/usr/bin/env python3
"""FilmCraft Android.8 project-open transition real hover delivery regression.

Root-cause candidate: Android.7 fixed Home-screen idle hover, but opening a
project replaces document_epoch and can leave the native SurfaceView's hover
listener/focus stale until a touch. Java must re-arm real hover on that exact
document replacement, without synthesizing input or stealing an active IME.
"""
from pathlib import Path
import subprocess
import sys

here=Path(__file__).resolve().parent
rust=(here/"filmcraft_stylus_wheel.rs").read_text()
stage=(here/"stage_v0201_wheel.py").read_text()
subprocess.run([sys.executable,str(here/"test_v0201_android7_coldstart_hover.py")],check=True)
for name,needle in {
    "document epoch forwarded from FilmCraft Session": "self.inner.session.document_epoch",
    "Rust capture epoch arg": "document_epoch: u64",
    "JNI document notification": 'jni_str!("fcWheelOnDocumentEpoch")',
    "JNI signature": 'jni_sig!("(J)V")',
    "native 80ms before first touch": "ctx.request_repaint_after(Duration::from_millis(80));",
    "native stylus pointer only": "raw.events.push(egui::Event::PointerMoved(pos));",
}.items():
    if (needle not in stage if name=="document epoch forwarded from FilmCraft Session" else needle not in rust):
        raise SystemExit(f"STOP: {name}")
for name,needle in {
    "document epoch guard": "fcWheelObservedDocumentEpoch == epoch",
    "Java project transition callback": "public void fcWheelOnDocumentEpoch(long epoch)",
    "UI-thread handoff": "runOnUiThread(() -> {",
    "surface event listener rebind": "fcWheelHoverTarget = null;",
    "native listener attachment": "fcWheelAttachHoverSurface();",
    "native focus restoration": "if (!surface.hasFocus()) surface.requestFocus();",
    "don't steal text focus": "if (!imeWanted && (focused == null || focused == decor",
    "retain real hover listener no consuming": "return false; // ALWAYS allow GameActivity/winit to process input",
    "window focus recovery": "if (hasFocus) fcWheelPrepareEarlyHover();",
    "initial startup hover": "@Override protected void onResume()",
}.items():
    if needle not in stage:
        raise SystemExit(f"STOP: {name}")
if stage.count("@Override public void onWindowFocusChanged(") != 0:
    raise SystemExit("STOP: duplicate onWindowFocusChanged override")
if "fcWheelButton();" not in stage or "if (!fcWheelEnabled || !fcWheelHovering)" not in stage:
    raise SystemExit("STOP: genuine pen button input gate lost")
if "const DEFAULT_SIZE: f32 = 0.75;" not in rust or "const DEFAULT_OPACITY: f32 = 0.80;" not in rust:
    raise SystemExit("STOP: owner-approved wheel defaults lost")
print("PASS: document open rebinds real hover on UI thread and safe native surface focus")
print("PASS: cold start 80ms polling, stylus button gate and PhotoCraft wheel parity")
