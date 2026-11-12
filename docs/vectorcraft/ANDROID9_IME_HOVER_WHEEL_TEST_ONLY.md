# VectorCraft v0.23.0-android.9 — isolated ARM64 test-only candidate

Base: successful isolated Android.8 branch commit `3d9c03b83c0e5e8f791be9791f24c5e2efee38e4`.
Official upstream: pinned v0.23.0; original published `vectorcraft-v0.23.0-android.7` is protected and unchanged.

## Owner-confirmed defects
1. Imported `.ai` (Crafticon V2.ai): Type tool can appear to be editing but existing live text does not accept keystrokes. Android.8 selected-live-text fallback and IME reset fences were insufficient on device.
2. Close the imported `.ai`, create a new empty document: text entry becomes unreliable or cannot type properly. New-document entry must recover without force-stopping or restarting the app.
3. Adaptive cursor must work with a trackpad; pen hovering must visibly indicate the hover position before touch.
4. Vc icon menu should contain a subcategory: **Stylus Wheel → Stylus Wheel On / Customization**.

## Android.9 source-only overlay
- Keep Android.8 Proposal A, user-customizable persisted 8-slot layout, wheel artwork/shadow/padding, native stylus buttons, reverse-free touchscreen panning, trackpad/pinch, font library, existing tests and compact native APK.
- Guard delayed `imeShow`, `imeHide`, `vcEndTypeEditing` and `vcResetIme` with a monotonic focus epoch. Recheck pending cleanup after SAF return; do not let an old callback hide a newly activated Type field.
- Detect the actual `DocState.uid` transition in native frame input BEFORE delivering IME events; clear old queued text, invalidate outstanding IME reset ID and prepare a clean keyboard host on the UI thread, while letting a newer show override delayed cleanup.
- Restart the new InputConnection on fresh focus; keep queued committed text on ordinary reset rather than discarding unrelated typed characters. Do not alter desktop editor input.
- Reuse the existing Android `PointerIcon` adaptive cursor bridge. Install a passive stylus-only hover listener on the native SurfaceView (returns `false` to preserve winit input), draw a small orange hover indicator in egui, and suppress it over the wheel and popups.
- Nest the existing menu action bits (256 toggle, 512 customization) in the actual tapped top-left Vc popup; keep the persisted SharedPreferences unchanged.

## Device acceptance — HONOR MagicPad 4
1. Cold start: new blank document → Type → input with physical keyboard and Gboard; save/reopen.
2. Open previously failing `Crafticon V2.ai` → select a **live Text** node with Type, tap inside its layout bounds → caret and text edits actually work; save/reopen. Outlined/converted paths are not live editable Text, and must not be silently converted.
3. **Without force-stop**, close the imported document → create new blank document → enter text immediately. Repeat 10×, including Ctrl+W with D/S/C, ESC, switching tabs and re-opening the same `.ai`. Verify no stale composition or lost first character.
4. Test V/T/P tool shortcuts after typing and document switching; Ctrl+Q relaunch ten times.
5. Real pen: hover marker follows the stylus, disappears when touching/moving away; no phantom strokes, no menu tap interception, no mouse/trackpad duplicate marker. Wheel continues to use approved Proposal A highlights and UI.
6. Trackpad adaptive pointers change for Text/Selection/Hand/resize; touch input and pinch/scroll stay unchanged.
7. Vc → Stylus Wheel → checked Stylus Wheel On and Customization: toggle persistence, customize all eight slots, close/reopen and Reset to Proposal A.
8. Fonts, SAF import, updates, startup/relaunch, pinch, touchscreen pan and trackpad menu scrolling must pass regression.

## Release gates
One `com.artcraft.vectorcraft.test` ARM64-only **disposable-key** signed test APK; never production sign, merge, tag or publish. Keep ZIP/native-library compression, aapt/apksigner checks, original signing-cert inequality, SHA256 file and exact measured APK bytes. If source guards fail, do not rebuild repeatedly; diagnose the first error and correct source first.
