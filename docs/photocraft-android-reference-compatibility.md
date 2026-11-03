# PhotoCraft Android — approved reference code and preservation rule

Reference: https://github.com/morte2437/photocraft-android (default branch `android-port`). Owner approved selective merging of compatible source on 2026-11-03.

## License / attribution

The reference repo currently declares `MIT OR Apache-2.0` for original code and includes both `LICENSE-MIT` and `LICENSE-APACHE`, plus `NOTICE` and `ATTRIBUTION.md`. Before copying substantial source, retain the applicable license/attribution and inspect any third-party files/assets independently. No visual assets or third-party fonts are authorized for blind copying. This suite's existing art/icon identity is the owner's blue Pc.

## Porting boundary

The reference uses a more comprehensive custom touch/input router around its Android runtime; ArtCraft's stable Android uses the preserved `NativeActivity`, JNI keyboard and file-picker bridge. **Do not replace the Activity, Android package, the user's production signing key, SAF font library, update feed, UI input handling or AI consent logic.** Test input changes in the isolated `feature/photocraft-v019-android-preservation-20261102` branch (draft PR #113) and retain the production-preservation gate.

### Reference implementation anchors

- `apps/photocraft-android/src/pad/router.rs`: custom first-finger vs multi-finger ownership, isolated pad touch targets, in-menu scroll behavior, swipe inertia and canvas pan/pinch/twist.
- `apps/photocraft-android/src/touch/mod.rs`: `moved_view` uses `ViewXform::to_doc` to keep an image pixel under the gesture's anchor while changing the zoom/rotation/center, and handles flipped canvas rotation. No document pixels are modified.
- `apps/photocraft-android/src/pad/trackpad.rs`: specific *on-screen trackpad mode* with multi-finger scroll; distinguish this from MagicOS physical trackpad ACTION_SCROLL or ACTION_MOVE devices.
- Pad layout includes rotary ring Zoom and held Alt/Pan controls; preserve owner-tested device screenshot/video behavior rather than merely resembling the reference.

### Owner's Android.5 device test

- One-finger **touchscreen** menu swiping works. Keep it.
- Two-finger **physical trackpad** menu scrolling does not work. Must validate MagicPad 4 hardware before claiming a fix.
- Escape to commit/exit Type editing, V/T/B tools and repeated Y/N/C confirmation shortcuts remain broken. Compare to proven production `photocraft-v0.14.0-android.4`; prioritize keyboard focus/reset and duplicate input events.
- Font import and folder import work; add `Refresh Fonts` to Pc/Type menu; background scan limited to 5,000 font files or 4 GiB.
- Move AI dialogs, Fonts, Check/Startup Updates and Appearance/Shortcut Pad switches into blue Pc top-left menu with no loss of existing safety checks.

**No automatic merge to main, production signing, or publishing** until actual ARM64 APK build succeeds and owner validates input, AI, fonts, updater and adaptive icon.