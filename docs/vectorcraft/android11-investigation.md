# Android.11 investigation checkpoint

Status: typing root cause is NOT CONFIRMED. No Android.11 APK built. Device typing,
stylus hover and adaptive cursor behavior are NOT VERIFIED. This branch is not a
production release or an approved correction of the typing failure.

Baseline: Android.10 commit eeff65019de99cca5b11a03df880a70a5c685fe3,
run 43165163258. The latest published VectorCraft production release verified at
investigation start was vectorcraft-v0.23.0-android.7, target
65056bbe58acc8ab60a83b5d3ccbdda5e5745491. Upstream remains pinned to
5d0e892e2419f63bc0ea3c743ddff2e81e15fd3a.

## Evidence and remaining investigation

Android.10's patch only expands selected-live-text hit recovery. It does not
change the commit-to-model route. The existing keyboard receipt diagnostics are
suppressed while Type is editing, so those receipts cannot prove TypeTool delivery.
The elapsed timer is zero if capture was not started; new reports explicitly say
whether capture was started and label the aggregate counters as since-launch.

The user supplied an 11-page PDF-compatible AI file containing live text operators
and an embedded Montserrat Extra Bold subset. This is not proof that the importer
retains every object as live text. The original file stays local and is not included
in source, fixtures, logs, artifacts or CI. A local engine probe is pending.

Routes inspected at the pinned upstream:

- Java InputConnection -> queued commit/preedit -> ime_bridge RawInput events.
- Native physical keys -> winit KeyboardInput -> egui text/key input.
- shortcuts/typing.rs filters stale/deferred IME events before TypeTool delivery.
- Session::tool_typed_text -> tool_text -> TypeTool::text_input -> text.editRange.
- Engine tooling.rs applies previews; preview errors were logged while the tool
  could remain active. The new trace separates command generation, acceptance,
  rejection and deferred preview, rather than interpreting tool return as success.
- textedit.rs changes runs and refresh_bounds rebuilds text layout.

No typing lifecycle guard has been weakened, no hit-test recovery expanded, and
no locked/path object conversion added by these investigation overlays.

## Cursor source defects

1. ui-egui/src/cursors.rs enables OS bitmap cursors on Android. The pinned Android
   winit set_cursor implementation is a no-op, so this selects an unavailable
   cursor backend instead of the existing painted-glyph fallback. The overlay
   excludes Android from OS_CURSORS and maps egui None to Android TYPE_NULL while
   the native canvas paints the original upstream cursor glyph.
2. Rust cached successful JNI return even though Java only queued application of
   the icon. A missing surface cleared the Java cache but not the Rust cache.
   Retry unchanged requests at most twice per second; cache Java success only
   after applying the icon, keyed by the actual SurfaceView as well as icon type.
3. The passive pen-hover listener is retried alongside pointer application so a
   missing/replaced surface is not dependent solely on another focus callback.

These source corrections still need generated-code compilation and tablet tests.

## Validation so far

- Replayed the complete Android.10 staging overlays on fresh pinned sources.
- Applied both Android.11 overlays successfully to generated sources.
- Python syntax checks passed.
- Android.9 tests: 6 passed. Android.10 source-overlay check passed.
- Android.11 tests: 4 passed, including generated routes/privacy and cursor backend
  and retry checks. These are source checks, not end-to-end behavioral tests.
- Generated standalone Rust counters module compiled with rustc.
- Full engine probe, Java/Rust adapter compilation, behavioral regression tests,
  pre-NDK gates and ARM64 APK verification are pending.

The two new overlays are deliberately not wired into an APK-triggering workflow
at this checkpoint. Finish the investigation and behavioral gates before the
single authorized disposable-key ARM64 build. Never use production keys, merge,
tag, or publish a release. Preserve com.artcraft.vectorcraft.test.
