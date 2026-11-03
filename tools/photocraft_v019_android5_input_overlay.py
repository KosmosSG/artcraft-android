#!/usr/bin/env python3
"""Temporary-only PhotoCraft v0.19 NativeActivity tablet input compatibility.

Run after photocraft_v019_adapter_overlay.py has staged the existing v0.19
compatibility fixes. Do not edit the published signed PhotoCraft runtime.
All anchors must be present exactly once or fail closed.
"""
from pathlib import Path
import argparse
import subprocess

OFFICIAL_SHA = "2df9f807702a935184041355a86405380bda8274"


def patch(path: Path, before: str, after: str) -> None:
    content = path.read_text(encoding="utf-8")
    count = content.count(before)
    if count != 1:
        raise RuntimeError(f"{path}: expected a single verified Android input anchor, got {count}")
    path.write_text(content.replace(before, after, 1), encoding="utf-8")
    print(f"staged Android tablet input: {path}")


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--upstream", type=Path, required=True)
    args.add_argument("--adapter", type=Path, required=True)
    opts = args.parse_args()
    pinned = subprocess.check_output(
        ["git", "-C", str(opts.upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    if pinned != OFFICIAL_SHA:
        raise SystemExit(f"Unreviewed upstream source {pinned}: input overlay refused.")
    adapter = opts.adapter
    host = adapter / "src/lib.rs"
    activity = adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"

    patch(host, "mod hardware_keys;\n", "mod hardware_keys;\nmod trackpad_wheel;\n")
    patch(
        host,
        "        hardware_keys::inject(&self.bridge, raw);\n",
        """        hardware_keys::inject(&self.bridge, raw);
        hardware_keys::recover_text_keys(
            raw, ctx, self.inner.ui.text_edit.is_some(),
        );
        trackpad_wheel::route(&self.bridge, ctx, raw);
""",
    )
    patch(
        host,
        '    fn poll_hardware_key(&self) -> Result<Option<String>, String> {\n',
        '''    fn poll_trackpad_scroll(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pcTrackpadScrollPoll"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

    fn poll_hardware_key(&self) -> Result<Option<String>, String> {
''',
    )
    patch(
        activity,
        '    public String pcHardwareKeyPoll() { return artcraftHardwareKeys.poll(); }\n',
        '''    public String pcHardwareKeyPoll() { return artcraftHardwareKeys.poll(); }
    private final ConcurrentLinkedQueue<String> artcraftTrackpadScroll = new ConcurrentLinkedQueue<>();
    public String pcTrackpadScrollPoll() { return artcraftTrackpadScroll.poll(); }

    // Some external trackpads send ACTION_SCROLL directly to NativeActivity's
    // Activity dispatch, bypassing winit's mouse-wheel conversion.
    @Override
    public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        if (event.getActionMasked() == android.view.MotionEvent.ACTION_SCROLL
                && (event.getSource() & android.view.InputDevice.SOURCE_CLASS_POINTER) != 0) {
            float vertical = event.getAxisValue(android.view.MotionEvent.AXIS_VSCROLL);
            float horizontal = event.getAxisValue(android.view.MotionEvent.AXIS_HSCROLL);
            if (Math.abs(vertical) > 0.0001f || Math.abs(horizontal) > 0.0001f) {
                View decor = getWindow().getDecorView();
                if (artcraftTrackpadScroll.size() < 32) {
                    artcraftTrackpadScroll.offer(horizontal + "," + vertical + ","
                        + event.getX() + "," + event.getY() + ","
                        + decor.getWidth() + "," + decor.getHeight());
                }
            }
        }
        // Let NativeActivity and winit receive the original event as usual;
        // Rust drops our fallback if it got the native wheel already.
        return super.dispatchGenericMotionEvent(event);
    }

    private long artcraftLastKeyTime = -1L;
    private int artcraftLastKeyCode = -1;
    private int artcraftLastKeyAction = -1;
    private void pcRememberHardwareKey(KeyEvent event) {
        int code = event.getKeyCode(), action = event.getAction();
        if (action != KeyEvent.ACTION_DOWN && action != KeyEvent.ACTION_UP) return;
        if (action == KeyEvent.ACTION_DOWN && event.getRepeatCount() != 0) return;
        if (code != KeyEvent.KEYCODE_ESCAPE && code != KeyEvent.KEYCODE_V
                && code != KeyEvent.KEYCODE_T && code != KeyEvent.KEYCODE_B
                && code != KeyEvent.KEYCODE_Y && code != KeyEvent.KEYCODE_N
                && code != KeyEvent.KEYCODE_C && code != KeyEvent.KEYCODE_W
                && code != KeyEvent.KEYCODE_D && code != KeyEvent.KEYCODE_S
                && code != KeyEvent.KEYCODE_ENTER) return;
        // Activity.dispatchKeyEvent and the hidden IME EditText may both see
        // the same physical KeyEvent; enqueue it only once.
        if (event.getEventTime() == artcraftLastKeyTime
                && code == artcraftLastKeyCode && action == artcraftLastKeyAction) return;
        artcraftLastKeyTime = event.getEventTime();
        artcraftLastKeyCode = code;
        artcraftLastKeyAction = action;
        int flags = (event.isAltPressed() ? 1 : 0)
            | (event.isCtrlPressed() ? 2 : 0)
            | (event.isShiftPressed() ? 4 : 0);
        artcraftHardwareKeys.offer(code + "," + flags + ","
            + (action == KeyEvent.ACTION_DOWN ? "1" : "0"));
    }
''',
    )
    patch(
        activity,
        '''                artcraftHardwareKeys.offer(code + "," + flags + ","
                    + (action == KeyEvent.ACTION_DOWN ? "1" : "0"));
''',
        '''                pcRememberHardwareKey(event);
''',
    )
    patch(
        activity,
        '''                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    // Let hardware key events fall through''',
        '''                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    pcRememberHardwareKey(event);
                    // Let hardware key events fall through''',
    )
    patch(
        activity,
        '''                public boolean onKeyUp(int keyCode, KeyEvent event) {
                    return false;
''',
        '''                public boolean onKeyUp(int keyCode, KeyEvent event) {
                    pcRememberHardwareKey(event);
                    return false;
''',
    )
    print("Android.5 temporary trackpad ACTION_SCROLL and hardware-key routing prepared.")


if __name__ == "__main__":
    main()
