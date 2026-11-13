#!/usr/bin/env python3
"""LightCraft-only Android native stylus hover/button and installer lifecycle hooks.

Edits ONLY the disposable builder's Java template. Do not overwrite upstream,
the published production APK, or the suite's protected Android baseline.
"""
import argparse
from pathlib import Path

def once(s: str, old: str, new: str) -> str:
    count = s.count(old)
    if count != 1:
        raise RuntimeError(f"STOP: LightCraft Android Java hook drift ({count}): {old[:90]}")
    return s.replace(old, new, 1)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    path = args.builder / "templates/android/SafActivity.java"
    source = path.read_text(encoding="utf-8")
    source = once(source,
        '    public boolean dispatchGenericMotionEvent(MotionEvent event) {',
        '''    public boolean dispatchGenericMotionEvent(MotionEvent event) {
        // LightCraft only: observe physical pen hover before forwarding to
        // winit; never convert a regular two-finger gesture into a stylus click.
        if (lcRecordStylusMotion(event)) return true;''')
    source = once(source,
        '    protected void onDestroy() {',
        '''    protected void onDestroy() {''') if False else source
    source = once(source,
        '    protected void onDestroy() {',
        '''    protected void onDestroy() {''') if False else source
    source = once(source,
        '    @Override\n    protected void onDestroy() {',
        '''    @Override
    protected void onResume() {
        super.onResume();
        // Finish a user-approved APK install after Android's permission sheet.
        lcResumeDownloadedUpdate();
    }

    @Override
    protected void onDestroy() {''')
    if args.apply:
        path.write_text(source, encoding="utf-8")
        print("Applied LightCraft-specific pen hover and Android installer resume hooks.")
    else:
        print("PASS: pinned LightCraft native stylus/installer Java hooks are valid.")

if __name__ == "__main__":
    main()
