# DeckCraft Android integration candidate

Continues suite PR #84 from the latest DeckCraft D/C/S development source in PR #91
(`42310d8c1699f9f6384ec4be6091664af6dd2781`), preserving that branch rather than
replacing it. Existing releases and permanently signed APKs are unchanged.

Pinned official source: Storytold DeckCraft v0.13.1,
`4ce2944630b04188dee8504c14151994d06c416a` (checked 2026-10-31).
Pinned Android builder: MostafaXS1/artcraft-android
`fbb4f66fcc868afdd8303d5227aa81db6a21d7fa`.
Candidate: `DeckCraft v0.13.1-android.1`, package `com.artcraft.deckcraft`,
versionCode `100000005`. The workflow retains only an **unsigned** ARM64 APK.

Changes staged:
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
