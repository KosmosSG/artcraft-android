# VectorCraft v0.23.0-android.5 — HONOR MagicPad 4 TEST ONLY

Baseline: v0.23.0-android.4 on draft PR #153, including published-owner Android features. Pinned upstream and Android builder remain unchanged. This is a disposable-key-signed, separate-install ARM64 `com.artcraft.vectorcraft.test` APK; NOT a production release.

## Scoped change

1. Android.18 already handles touch pinch when egui canvas hover is lost after first contact. Android.5 adds a stricter **hoverless native trackpad Zoom event** fallback so initial pinch works before any scroll or pointer hover arrives. Use canvas center only when a document is open, no popup/dialog/palette, no touch multitouch, and no pointer hover position. The fallback is **zoom only**, never canvas pan/selection.
2. In open popup/dropdown lists, normalize Android trackpad vertical PixelDelta to egui content-motion coordinates: two-finger swipe UP reveals later rows (scroll DOWN), swipe DOWN reveals earlier rows (scroll UP). Do not rewrite the canvas, horizontal axis or keyboard. Skip touchscreen-contact frames.
3. Intermittent ANR on Ctrl+Q relaunch is **not claimed resolved**, because system ANR traces were unavailable. Preserve Android.4 native-loop-first quit and persisted `VC_QUIT4` diagnostics; repeat the relaunch stress test and capture logcat/ANR traces if warning recurs.

## Cheap safety gates before compilation

- Python patch syntax, exact once-only overlay anchors, generated Rust/Java guard assertions.
- Existing Python/Rust pointer tests, Android stability unit tests.
- Full builder code verifies version, package ID and disposable-only signing; emits verification.json and SHA256SUMS.txt.
- One-shot branch/path workflow; no runs on ordinary source edits.

## Device acceptance

- Cold-open a document; pinch immediately before any two-finger scrolling.
- Lift both fingers completely; pinch again.
- Scroll with two fingers; pinch.
- Two-finger canvas and popup menus without selection; natural vertical menu directions UP->later and DOWN->earlier.
- Type tool, V/T/H, ESC after typing; Ctrl+W D/S/C repeatedly.
- Five cold starts, fonts, shared folder, in-app updater.
- Ctrl+Q then reopen 10x without clearing data, noting any temporary Android 'not responding' warning and capturing a fresh Diagnostic Session.
- If pinch still fails: fresh Start/Reset -> repro -> Stop/Copy Report native counters; compare to successful after-scroll trace.

STOP before merge, permanent signing, GitHub Release, or publication.
