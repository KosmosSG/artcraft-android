# DeckCraft Android integration candidate

Continues suite PR #84 from the latest DeckCraft D/C/S development source in PR #91
(`42310d8c1699f9f6384ec4be6091664af6dd2781`), preserving that branch rather than
replacing it. Existing releases and permanently signed APKs are unchanged.

Pinned official source: Storytold DeckCraft v0.14.1,
`ee39ff67816d0039143ec7c98ea604cefe0cd2e5` (checked 2026-11-02).
Pinned Android builder: MostafaXS1/artcraft-android
`fbb4f66fcc868afdd8303d5227aa81db6a21d7fa`.
Candidate: `DeckCraft v0.14.1-android.3`, package `com.artcraft.deckcraft`,
versionCode `100000010`. The workflow retains only an **unsigned** ARM64 APK.

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

## v0.14.1-android.5 Android two-finger canvas pan follow-up (2026-11-02)

Owner tested device v0.14.1-android.4: pinch out/in WORK, D/C/S and Escape WORK,
Dark Theme WORK, but two-finger canvas scrolling/panning NOT WORKING. A winit
Android two-finger PanGesture is routed to egui::MouseWheel Point; winit drops
normal touch hover on the second finger, so upstream DeckCraft canvas ignores
wheel scrolling unless resp.hovered(). Android.5 adds a canvas-origin-scoped
point-wheel fallback to the same existing touch-anchor logic as pinch zoom,
permitting offset scroll only when the canvas overflows after zoom. It also
prevents two-finger swipe over a fitted slide from being mistaken for page
navigation. The modal, ribbon, existing pointer selection, pinch, D/C/S,
Escape, zoom constraints, dark theme and approved icon are preserved.

Device test: after pinch zooming past fit (e.g. 180%-250%), place two fingers
on the slide and move them together to pan horizontally/vertically; confirm
no object selection, no unwanted slide changes, and existing pinch in/out,
D/C/S and Esc still work. Generate temporary-key test APK from successful
unsigned build, with no additional production GitHub signing run and no release.

## v0.14.1-android.6 active-editor Ctrl+W + trackpad pan sensitivity (2026-11-02)

On HONOR MagicPad 4 the owner reported Android.5 touchscreen pinch-out, pinch-in,
two-finger panning, D/C/S, Escape, and dark theme all WORK. Trackpad two-finger
panning works but has low movement; Ctrl+W DOES NOT open the D/C/S dialog while
a text box remains in text-edit mode (after Escape, Ctrl+W and D/C/S work).
Official DeckCraft app/keys.rs returns early when egui focused editor owns keys,
before menus::ui_shortcut can route W to close_presentation. Android.6 adds
an Android-only focused-text Ctrl+W pre-route to the EXISTING native
close_presentation() dirty-document confirmation, without broadening other
editor shortcuts. Added Rust matching/dirty-modal regression assertions.
Android-only Point MouseWheel events use 1.65 canvas panning gain when zoomed
beyond fit; ordinary scroll, wheel-line events and slide content are preserved.
Retest with active text cursor WITHOUT pressing Esc: Ctrl+W should open the
existing Save/Don't Save/Cancel dialog; D/C/S must work repeatedly. Confirm
Esc stays inside app, no unsaved text lost, pinch zoom, two-finger
touchscreen/trackpad pan, dark theme and import fonts still work. Release
and permanent signing blocked pending device testing. No new GitHub
Actions signing job: local temporary-key test-signing only.

## v0.14.1-android.7 — reliable focused-editor keyboard + font menu clean-up (2026-11-02)

Owner on Android.6 reported Ctrl+W while typing still fails; D/C/S responds after
leaving text, Ctrl+C and Ctrl+X also fail while in text editing, asks for Ctrl+V;
trackpad pan works but is not smooth; File has duplicate Import Font alongside
Help. Keep Help > Import Font with SAF import intact; remove just File duplicate.

Official egui keyboard shortcut path returns early with editor focus, and raw
Ctrl+W may be filtered before app.keyboard sees events. Android.7 records
Ctrl+W at eframe RawInput boundary and in Activity hardware event dispatch,
then polls the one-shot Java transport to trigger DeckCraft's existing safe
close_presentation D/C/S dialog even while canvas text has focus. Android
clipboard events Copy/Cut/Paste use existing builder synthetic events and are
routed to the custom slide text editor only, preserving stock widgets and
Android clipboard semantics. Preserve text-selection, IME, and Ctrl+V in
foreign apps. Trackpad point-wheel non-touch gain changed 1.65 -> 1.25 for
less jitter; direct touchscreen pan retains 1.65.

No merge, permanent signing or release. Build with disposable test signing
outside GitHub. Device test: type with caret active, Ctrl+W opens D/C/S without
Esc, then D/C/S repeatedly; Ctrl+C, Ctrl+X, Ctrl+V while text selected;
shape object clipboard; touchscreen pinch/pan, trackpad smoothness, Esc, dark
mode, and font importer reachable once under Help. CI alone is not proof.

## v0.14.1-android.8 — Ctrl+A/C/X/V hardware clipboard and trackpad refinement (2026-11-02)

HONOR MagicPad 4 owner tested Android.7: Ctrl+W directly while typing WORKED; D/C/S,
Escape, touchscreen pinch/pan, Dark Theme and Help-only Import Font WORKED.
Ctrl+C, Ctrl+X, Ctrl+V failed while text editing; the Home Paste tooltip
incorrectly displayed hard-coded macOS `⌘V` instead of Android `Ctrl+V`.
Ctrl+A was requested to select all text inside the active shape. Trackpad
scroll was improved but still weak. Android.8 adds the same one-shot RawInput
and Java hardware keyboard handling that fixed Ctrl+W, for A/C/X/V, then
routes it to text.selectAll, publish_clipboard copy/cut, and edit.paste,
respectively; clipboard strings come from the Android ClipboardManager JNI
and existing shell synthetic Paste events. Stock text fields and modals retain
their own normal clipboard shortcuts. Home's Android-specific tooltip now
reads Paste (Ctrl+V). Trackpad point-wheel gain becomes 1.95 (previous 1.25),
while working two-finger touchscreen pan stays 1.65. No edits to DCS/Escape,
theme, font import or published releases. Re-test with active text caret:
Ctrl+A selects all text, Ctrl+C copies selected text, Ctrl+X cuts and Ctrl+V
pastes; verify also after multiple edits, other app clipboard integration,
trackpad pan smoothness, D/C/S, Escape, dark theme and touchscreen gestures.
No permanent GitHub signing or publication; temporary test signing only.

## v0.14.1-android.9 — clipboard freshness + smooth trackpad pan (2026-11-02)

Owner tested Android.8 on HONOR MagicPad 4: Ctrl+A WORKS; Ctrl+C and Ctrl+X
appear to copy/cut but Ctrl+V inserts the WRONG or OLD text (laggy); Paste
Ctrl+V hint, Ctrl+W, D/C/S, Escape, pinch zoom, touch pan, and Dark Theme
WORK. Trackpad scrolling improved but less smooth than the touchscreen.

Root cause hypothesis supported by code: official app publish_clipboard(ctx)
calls egui ctx.copy_text(), which is committed asynchronously in frame output,
but DeckCraft's Android Activity hardware Ctrl+V path reads ClipboardManager
before the newer copied text is guaranteed present. Android.9 puts the
newly copied plain selection in a one-shot ctx slot, flushes it immediately
after app.logic via JNI into Android ClipboardManager setPrimaryClip(), and
makes the live Android clipboard authoritative over an older raw egui Paste
snapshot. Added source/regression assertions for copying FIRST then SECOND,
cutting SECOND, and pasting the most recent text (no previous clipboard leak).
The normal clipboard output remains for other app integration and fallback.

For trackpad point-wheel motion while an overflowing canvas is hovered,
Android.9 interpolates consecutive frame deltas (72% new, 28% previous),
retaining separate touchscreen touch-pan handling and original 10–400% zoom.
This is a test candidate only: do not merge, production-sign or publish.
Use local disposable-signature APK after successful ARM64 unsigned build,
then owner must test Copy/Cut/Paste repeated, cross-app clipboard, trackpad
pan, Ctrl+A/W, D/C/S, Esc, two-finger touchscreen pinch/pan, Dark Theme.

## v0.14.1-android.10 — clipboard redraw, trackpad spike limiting and centered modal title (2026-11-03)

Owner tested Android.9 on HONOR MagicPad 4: new clipboard content now correct, but
Copy and Cut occasionally require tapping elsewhere before changes appear; input
still feels slow. Trackpad two-finger pan improved but sometimes triggers the
MagicOS system right-edge panel (phone device overlay screenshot); D/C/S and Escape
continue working. Save-dialog DeckCraft heading appears slightly off-center.

Android.10 refreshes the app while a custom slide-text editor is active (24ms
scheduled repaint while editing) and requests immediate repaint when a raw
clipboard shortcut arrives, after the editor handles Copy/Cut/Paste and when
new clipboard data is queued, to avoid waiting for an unrelated touch.
Trackpad-only point-wheel smoothing retains existing gain but clamps extreme
per-frame deltas to ±80 px, making gestures less jumpy; native touchscreen
pan/pinch unchanged. This does not override Android/MagicOS system edge-swipe
recognizers; those remain OS-owned. D/C/S modal header uses symmetric slots
and a true centered egui label, preserving close X, buttons and modal safety.

No production signing, merge or release. Unsigned ARM64 CI and device testing are
mandatory. After CI success use local disposable test signing with no additional
GitHub signing job. Retest immediate Ctrl+A/C/X/V with focused text, no extra tap,
repeat D/C/S, centered title, trackpad pan away from screen edges and native
touchscreen gestures and themes.

## v0.14.1-android.11 — caret arrows + selection, touch-like trackpad settling, native APK strip (2026-11-03)

Owner tested v0.14.1-android.10 on HONOR MagicPad 4: ALL prior clipboard, Ctrl+W,
D/C/S, Escape, dialog centering, dark theme, touch pan/pinch and trackpad fixes WORK.
New requests: physical Left/Right/Up/Down arrow keys should move the live text
caret (currently inert); Shift+Arrow should extend text selection; trackpad
scrolling should feel as smooth as two-finger touchscreen pan; reduce APK size.

Official DeckCraft engine already supports session.key Left/Right/Up/Down,
where Mods.shift maps to text.move.extend. Android.11 captures only arrow
key-down during CUSTOM slide-text editing at both pre-egui RawInput and Java
Activity event dispatch, sends one-shot encoded direction + Shift through the
existing JNI bridge, then calls official engine session.key before the
focused-widget early return; does not interfere with ordinary UI widgets,
dialogs, slide selection or plain typing. Test text arrow/caret and Shift+Arrow
range, no accidental slide movement.

Trackpad-only scroll now interpolates uneven point-wheel bursts with a short
bounded 16ms momentum tail of <=220ms, using 64px per frame max, leaving
native direct touchscreen pan/pinch and Android system edge gestures alone.

Size audit of Android.10 signed APK: 125MiB total, 123,993,296 bytes in the
STORED arm64-v8a libdeckcraft_android.so, which is unstripped and includes
.symtab/.strtab. Android.11 removes nonessential ELF symbols using Android
NDK llvm-strip --strip-unneeded while converting the disposable-key APK to
unsigned, and then zipaligns preserving 16KiB native-page alignment. No change
to executable code/data, fonts/import, package, certificate policy, or DEX.
Measure reduced native size in GitHub build and verify SHA256/package/ABI.
Potential deeper LTO/code/data reductions require separate compatibility
review and are intentionally not attempted.

Use locally disposable-key v2-signing test APK, no additional GitHub signing
job, no permanent key, merge or public release before physical tablet test.

## v0.14.1-android.12 — remove duplicate trackpad smoothing after owner tablet test (2026-11-03)

HONOR MagicPad 4 owner tested Android.11: ordinary arrow caret motion, Shift+Arrow
text selection, all earlier Ctrl+A/C/X/V/W, D/C/S and Escape, dark theme,
touch pinch/pan, install and reduced APK size all WORK. Two-finger trackpad
scroll still has slight lag and can bring up MagicOS's separate connected-device
panel / global edge gesture (not controllable from DeckCraft after OS intercepts).

Pinned official egui InputState::smooth_scroll_delta already includes scroll
smoothing and has native trackpad pass-through. Android.11 additionally
low-passed deltas (36% old+64% new) and synthesized up to 220ms of momentum:
that unnecessary second filter may cause the reported latency. Android.12
removes redundant trackpad smoothing and synthetic scroll-after-lift; uses
native egui smooth_scroll_delta as the sole smoothing stage, trackpad pixel
scale 1.7 (previous 1.95), cap atypical trackpad bursts to ±72px/frame.
Direct two-finger touch scroll remains at 1.65 and pinch zoom untouched;
no slide switching from touch pan. No Android gesture interception, system
settings change, signing/release, toolbar/text, D/C/S or font modifications.

Build and device test remain required: verify trackpad feels more responsive,
with no unexpected extra momentum/slide changes, compare MagicOS overlay,
pinch/pan, keyboard shortcuts, theme, APK size. MagicOS can claim reserved
gestures; owners may optionally adjust HONOR Connect/MagicRing and Multi-Window
dock settings with awareness of cross-device side effects.

## v0.14.1-android.13 — GPU adapter diagnostics, preservation of existing GPU path (2026-11-03)

Owner confirmed Android.12 nearly perfect on HONOR MagicPad 4 and authorized
GPU acceleration integration. Current pinned builder ALREADY uses
`eframe::Renderer::Wgpu`, with `wgpu::Backends::VULKAN | GL` and device
adapter texture limits; DeckCraft UI uploads and caches rendered slide
textures in GPU memory. Official DeckCraft `deckcraft-render` still rasterizes
complex slides using `vello_cpu`. Forcing a different backend or silently
replacing the CPU rasterizer risks fidelity, rendering freezes and regression.

Phase 1 Android.13 adds non-invasive Help -> GPU Diagnostics UI and logs exact
selected runtime WGPU adapter (name, actual backend, device type and max
texture size) from `CreationContext.wgpu_render_state.adapter.get_info()`.
Dialog also displays current built-in frame_ms/render_ms/fps diagnostic values,
with explicit CPU rasterizer versus GPU compositor wording. Do NOT report
Adreno/Vulkan or actual GPU usage on a tablet solely from source flags;
the adapter must be checked on physical device. No new renderer, GPU compute,
texture format, asset removal, or power-management override. No changes to
existing input, D/C/S, font scan, recovery, APK size optimization and icons.

Follow-on gated engineering after owner validates diagnostics: measure
real render and frame timings with complex slides versus blank slides,
then evaluate GPU-native render passes only where fidelity can be matched.
Keep official CPU rasterizer as fallback; do not claim full GPU slide render.

Unsigned ARM64 CI only. Any test APK must be temporary-key signed locally
(no separate GitHub signing workflow) and verified before user install.
Keep PR #106 draft and do not merge, production-sign, tag or publish.

## v0.14.1-android.14 — measured GPU texture reuse without replacing the rasterizer (2026-11-03)

Owner physically tested Help > GPU Diagnostics on HONOR MagicPad 4 Android.13:
Adreno (TM) 829; Vulkan selected runtime backend; IntegratedGpu;
max texture side 16,384px; app UI pass 2.7ms, CPU slide raster last 3.7ms,
frame-pass frequency approximately 155.3 FPS (not screen refresh rate).
Confirmed existing WGPU/Vulkan acceleration; full GPU drawing of slide shapes is
not implemented because official renderer uses vello_cpu.

Android.14 is a conservative and reversible optimization of the GPU-resident
slide texture cache. If an unmodified slide, master, zoom, edit/text state,
GIF/grayscale/animation matches and its already-uploaded GPU texture contains
all requested pasteboard pixels after trackpad/touch panning, reuse it
instead of running CPU rasterization and uploading a new texture. Never reuse
on edit, different content or zoom; maintain original texture region and UVs.
Add a named Rust regression test for reused contained region and rejection
for out-of-region and changed slide/master/zoom/style/animation. Keep existing
canvas_renders and a new GPU texture reuse hit counter; show both in
Help > GPU Diagnostics, distinguish UI-pass rate from device refresh and
last raster cost from GPU compute timing. Remove redundant Cancel button
from diagnostics. Do NOT change Vulkan/GL device selection, CPU rasterizer,
font rendering, canvas coordinate mapping or the known working Android.12
keyboard, clipboard, DCS, dark theme, native touchscreen and trackpad behavior.

Save expensive full GPU slide rasterization until representative presentations
show CPU time as bottleneck and visual parity is tested. Keep existing draft
PR #106, unsigned ARM64 test CI, local disposable-key signing only for test,
no production keys, merge or publication without user approval.
