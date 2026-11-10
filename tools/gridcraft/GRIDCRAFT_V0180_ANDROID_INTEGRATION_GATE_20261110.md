# GridCraft v0.18.0 Android integration — compatibility gate (2026-11-10)

## Immutable inputs (verified through GitHub)
- Published protected baseline tag: `gridcraft-v0.16.1-android.4` at `7bd2151903ea8025eb96841c1d1a5bff1a02bbcb`.
- Official Storytold upstream tag: `v0.18.0` at `17cb3c83d9e73df6a88ed174cec612f1de2e8244`.
- Integration branch was created from the protected baseline; no upstream source has yet been compiled into an Android v0.18.0 APK.
- Official upstream `Cargo.toml`: workspace version `0.18.0`, Rust minimum `1.95`, egui/eframe `0.37`.

## Blocking source compatibility issues (do NOT bypass)
1. `tools/gridcraft/install_overlay.py` currently allows only upstream `0.11.1`, `0.15.0`, `0.16.1`; the v0.18.0 source correctly fails closed. Port against actual v0.18.0 APIs before enabling that source version.
2. Existing `port_v0150_ui.py`, `port_v0150_save_dcs.py`, `port_v0150_touch_selection.py` patch UI, SAF save/close and touch selection with exact anchors. Verify every anchor and maintain the behavior; do not blindly suppress failures.
3. Existing side-by-side workflow `gridcraft-v0161-side-by-side.yml` is pinned to older v0.16.1 source and an unrelated branch. It MUST NOT be represented as a v0.18.0 test build.
4. Upstream `v0.16.1...v0.18.0` comparison has hundreds of changes, including calculation, chart, formula, UI/grid, update components and dependencies. Port selectively; do not replace the tested Android overlay.

## Mandatory preservation / regression checks before the sole test build
- Keep production app ID `com.artcraft.gridcraft`, published release assets, signing identity, user data and versionCode untouched. Use `com.artcraft.gridcraft.candidate` for side-by-side disposable-key testing.
- Gc launcher/menu, Appearance, updates and manual/startup controls.
- TTF/OTF SAF import, shared folder and recursive refresh up to 5,000 files / 4 GiB; font rendering after app restart.
- Keyboard focus after cell editing; ESC, Ctrl+W D/C/S repeatedly, Ctrl+Q relaunch, clipboard, Ctrl+A, Shift+Arrow, save / save-as / unsaved recovery.
- Two-finger touchscreen and hardware trackpad vertical/horizontal scroll must pan without cell selection, drawing or Android system gesture conflicts; retain previously approved one-finger behavior.
- Workbook XLSX/CSV open, edit, save, reopen, formulas, formats and data recovery.
- Investigate HONOR Pad X7 Android 15 startup: verify minSdk, ABI, native library loading, graphics capability / renderer fallback, and capture logcat on device. ARM64-only APK will not run on a 32-bit-only device; inspect Pad X7 supported ABIs before attributing failures to software.
- MagicPad 4 ARM64 must not regress as a tradeoff.

## Build gate / operator instructions
- First port exact upstream APIs with a source compatibility test and Android-specific regression assertions.
- Run source-only tests before CI. Trigger at most one temporary-key ARM64 build once all checks pass.
- Validate APK manifest/package, arm64-v8a native libs, installer signature, approved icon, reproducible SHA256 and isolated installation.
- Optimize APK by excluding unused ABIs, native debug symbols and unnecessary resources; do not strip required app functionality.
- Provide APK link and checklist for both tablets. Device tests remain unverified until performed by owner.
- NO production signing; NO merge; NO publication; NO deletion or modification of protected historical releases.

**Status:** Source integration not complete; CI not triggered; APK not built. This audit is not a claim of integration completion.
