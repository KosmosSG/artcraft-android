# EffectCraft 0.21.0-android.4 isolated quit/relaunch candidate

Rollback reference: `8a7080624ca71d96baa6cbb68b8fc6ab53a486ca` (android.3).
Only EffectCraft tooling and its isolated build workflow change. Production signing,
shared vendor sources, other apps, stable releases and app data are untouched.

## Evidence and limits

The exact pinned winit `a517b3846ee8457d84ee4975110bfda6797c44dc`
sets `EVENT_LOOP_CREATED` in `EventLoopBuilder::build`, returning
`EventLoopError::RecreationAttempt` on every later build in that process. Only web
has a reset. Android's GameActivity glue calls `android_main` again for a new
Activity in the same process. Eframe's event loop cache is thread-local, so it
cannot reuse the old loop on the new Activity thread. Thus a quit followed by
same-process Activity recreation has a concrete source-level failure path.
The backend also ignores `MainEvent::Destroy`, leaving native teardown running.

These are confirmed source defects, not a captured MagicPad exception trace.
No adb, emulator, or physical Android device is available in this workspace.
A successful APK build and host Rust tests do not establish the observed tablet
failure's complete cause or prove Activity, IME, GPU, or save-picker behavior.

## Change

A scoped Android-only lifetime guard permits one live event loop, then releases
its reservation after the platform loop's fields drop. Desktop's original rule
is preserved. Failed construction releases its reservation too. Android Destroy
requests native-loop exit, allowing eframe's existing `exiting` callback to save
and destroy its app. No process kill, forced exit, or app-data reset is added.
The patch runs on the isolated CI vendor checkout, never the committed shared
vendor tree. Host Rust tests exercise 100 lifetimes, overlapping-loop rejection,
resource-drop order and failed-construction recovery.

Physical Ctrl+W/Q commits active text before the guarded command decides whether
the project is dirty. A failed commit leaves the editor open. D/S/C retain the
upstream save/discard/cancel workflow; physical Escape is intercepted as Cancel
while the unsaved dialog is active. Activity destruction is logged without document
contents. Existing native startup errors are logged by the launcher.

Android persistence here loads settings and keymaps via the upstream lenient
readers. It does not restore an editor project/session snapshot. There is no
basis for deleting session files or unrelated settings/fonts; this candidate
performs no such deletion.

## MagicPad verification (pending)

Install the separate `com.artcraft.effectcraft.v021test4` package. Its first-run
fonts/preferences are isolated; stable app data is not migrated into this test.
Create text and quit with each of D, S, C and Escape. Check no shortcut letters
enter text, and typing continues after cancel. Test saved/clean and untitled/dirty
projects, cancel the Save picker, and retry it. Verify the saved file can reopen.
Repeat quit/relaunch at least 10 times without Clear Data. Force-stop/reopen and
restart the tablet/reopen. Recheck Ctrl+W, ESC, normal physical typing, touchscreen,
trackpad, Android launcher menu, updater, imported/shared recursive fonts and
persistence of test-app preferences/fonts. Capture logcat around the entire
quit and next launch if any freeze occurs, particularly `EffectCraftLifecycle`,
`RecreationAttempt`, `Android exited with an error`, AndroidRuntime and native
crash/tombstone entries. Do not clear data before collecting the failure logs.

The artifact remains test-only. Stop before permanent signing/publication.
