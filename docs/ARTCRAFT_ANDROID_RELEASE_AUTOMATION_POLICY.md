# ArtCraft Android Suite — guarded automatic public release policy
Updated 22 October 2026. Public distribution is through this repository's
GitHub Releases, not Google Play.

## Policy

1. Follow official stable storyteller upstream source only via pinned, reviewed
   tags or exact commits. New upstream code first undergoes compatibility
   review; never auto-overwrite Android app enhancements.
2. Preserve approved icon assets and Android adaptive icon safe areas, font
   import/shared folders, SAF storage, GPU diagnostics, keyboard shortcuts,
   touch improvements and in-app update checking.
3. Each app gets its own permanently backed-up signing identity and fixed
   Android package ID. Verify certificate fingerprint across every update.
   Every new production versionCode must exceed **all** prior installed and
   published codes. Do not publish ephemeral-signed candidate APKs.
4. CI build, tests, ABI, resources, signer, package/version and APK checksum
   must pass. A tablet device-test record is required for **the exact APK
   SHA256**, not merely a similar candidate from the same source.
5. Only a verified production baseline plus complete device attestation
   permits automatic release of that exact previously tested APK. A failure,
   missing secret, changed source/certificate or unverified code halts
   publication. Never replace existing public releases.
6. Use per-app GitHub release tags and package metadata; never assume that the
   latest repository release belongs to every app. In-app updater logic must
   filter by the app and understand the published version format.

## Implementation progress

- **PhotoCraft:** guarded automatic promotion workflow installed in the
  private KosmosSG/photocraft-signing-private repository, with its original
  signer and existing build workflows intact. Promotion is fail-closed:
  production-baseline.enabled is false until the owner verifies historical
  versions and original signed tablet baseline. The private repo also
  requires an owner-provided public-repository scoped release token and an
  exact tested APK approval. Until then **no public release occurs**.
- **DesignCraft:** candidate builds pass; the private dedicated signing
  bootstrap is prepared, but no permanent DesignCraft identity has been
  confirmed. No public auto-publishing enabled.
- **VectorCraft:** candidate/icon checks available; verify permanent signing
  continuity, device baseline and full feature tests before enabling release.
- **FilmCraft:** separate Java SAF/IME integration failure in an enhanced
  candidate; public release prohibited until that build and device tests pass.
- **PDFCraft, WordCraft, DeckCraft, LightCraft, EffectCraft, GridCraft and the
  other suite apps:** individual workflows, permanent keys, source/feature
  checks, verified icons and exact tablet device attestations are required.
  No app is assumed production-ready from its existence in a branch.
- **PhotoCraft updater constraint:** currently filters only numeric
  photocraft-vMAJOR.MINOR.PATCH tags, ignoring -android.N tags. The guarded
  PhotoCraft release gate therefore accepts numeric versions only until the
  app's updater is enhanced and device-tested.

## Automatic vs manual

The installed PhotoCraft workflow **automatically publishes after the
device-tested signed APK's evidence is committed and all hard checks pass**.
Current upstream review/build workflows are still manual or review-only,
so upstream releases do not yet trigger unattended new production builds.
Do not enable completely unattended upstream merging or publication without
a trustworthy method to test real device behavior and preserve app features.

For each next app, clone the policy, never a secret or keystore: choose the
actual installed package/certificate and version ledger, establish its
private signing/backup, verify its exact built APK and tablet test report,
and only then enable that app's individually scoped public release job.

Existing releases, signing certificates and APK update chains take priority
over build speed. An invalid or absent gate must always fail closed.
