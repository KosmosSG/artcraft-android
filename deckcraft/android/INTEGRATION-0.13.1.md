# DeckCraft Android integration candidate

Continues suite PR #84 from the latest DeckCraft D/C/S development source in PR #91
(`42310d8c1699f9f6384ec4be6091664af6dd2781`), preserving that branch rather than
replacing it. Existing releases and permanently signed APKs are unchanged.

Pinned official source: Storytold DeckCraft v0.14.1,
`ee39ff67816d0039143ec7c98ea604cefe0cd2e5` (checked 2026-11-02).
Pinned Android builder: MostafaXS1/artcraft-android
`fbb4f66fcc868afdd8303d5227aa81db6a21d7fa`.
Candidate: `DeckCraft v0.14.1-android.3`, package `com.artcraft.deckcraft`,
versionCode `100000007`. The workflow retains only an **unsigned** ARM64 APK.

Changes staged:
- Updated to official v0.14.1 (released 2026-11-01), preserving all compatible improvements from v0.13.1; upstream includes safer print-preview handling, PPTX fidelity, animation and update-dialog improvements.
- Fixed Android arm64 dependency resolution by pinning crates.io android-activity to the available 0.6.1 series (formerly unavailable ^0.6.4). Verify Android API compatibility in CI before candidate use.
- Adapt existing Android fonts, legacy family aliases, menu controls, approved
  branding and D/C/S acknowledgement to upstream's split UI modules.
- Enable upstream AutoRecover on Android. Restore saved presentations separately
  from dirty-document recovery, preserving recovered edits over older disk files.
- Store session metadata atomically and keep upstream UI/preferences persistence.
- Add read-only SAF shared-folder selection and refresh. Stream up to 4 GiB into a
  persistent private cache; enforce 20 MiB per font, bounded traversal, content
  hashes and a 4 GiB cache cap. Partial/unreadable results retain prior fonts.
  Fonts use the upstream lazy catalog instead of loading the entire cache into RAM.
- Preserve original-certificate/package/version/hash checks in the Android updater;
  add persisted, OFF-by-default startup checks and Stable + Preview selection.
- Use the newer Android builder's mobile scaling, gesture and rendering support.
  GPU compatibility and physical-device behavior are not yet verified.
- Build automatically on this branch's relevant commits with no permanent signing
  secret, publication job or release upload.

Validation gates:
- Patch application and generated Android host must succeed against exact pins.
- Java scan-budget tests cover 64-bit arithmetic, exact exhaustion and overrun.
- Rust tests cover D/C/S cancel/failure/late responses, font rendering and document
  round-trip, session restoration and corrupt metadata.
- CI must compile ARM64, verify APK metadata/ABI, strip disposable packaging
  signatures, verify alignment and record the unsigned SHA-256.
- No signing-ready, publication-ready, or device-verified claim until the relevant
  checks have passed. This draft is not a replacement production release.

Scope still open: suite-wide app-by-app ports in PR #84, Android device acceptance,
and signing/publication. PhotoCraft remains last; LightCraft is excluded from the
font-scanner work. This DeckCraft branch does not change those applications.

## v0.14.1-android.3 UI / modal regression fix (2026-11-02)

The owner device-tested Android.2: Escape now stays inside DeckCraft, but D/C/S
shortcuts failed; the Format dropdown centered its items and no theme choice was visible.
Android.3 restores the published Android.4 Java keyboard focus/physical key transport,
eagerly drains egui shortcut events, uses egui::Modal to block the canvas behind the
unsaved dialog, exposes the existing persistent View > Dark Theme preference, and
left-justifies all Android top-menu entries. Esc stays inside the app.

No production signing or release. CI, temporary test signature, and HONOR MagicPad 4
repeated-dialog / Escape tests remain required before approving the changes.

## v0.14.1-android.4 touchscreen canvas pinch zoom (2026-11-02)

Owner accepts current Android.3 interface and asks to enlarge/shrink the
slide canvas using two fingers on the HONOR MagicPad 4 touch screen. The pinned
MostafaXS1 winit backend emits PinchGesture -> egui Event::Zoom but cancels
touch/pointer hover when the second finger joins; upstream DeckCraft canvas
requires resp.hovered() and can ignore the zoom. Scope the Android fallback to
touch gestures originating inside the editing canvas, use the touch origin to
anchor zoom, retain normal mouse/trackpad hover checks, preserve 10%-400%
zoom range and existing slide document size/contents. Do not hijack ribbon,
menus or D/C/S modal. Keep released Android.4 DCS fix, dark theme and Esc
behaviour. Next APK is a disposable-cert testing build: no permanent signing,
merge or publication until owner validates pinch inward/outward and all
previously working behaviours on the tablet.
