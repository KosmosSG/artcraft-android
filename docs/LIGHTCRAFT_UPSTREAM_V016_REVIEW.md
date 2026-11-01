# LightCraft official v0.16.0 — isolated source-lock review (1 November 2026)

**Review-only; no Android source port, APK, signing, merge or release is claimed.**

## Verified official source

- Official stable release: https://github.com/storytold/lightcraft/releases/tag/v0.16.0 (published 2026-10-31 03:53:25 UTC; not draft/prerelease).
- Direct Git tag `refs/tags/v0.16.0` resolves to commit `cdf00cc84bf87f544d6dbc40e3bc0456641661a9`.
- At that tag, root `Cargo.toml` reports workspace version `0.16.0`, Rust MSRV `1.95`, and upstream `storytold/lightcraft`.
- New stable changes include defensive RAW strip bounds, .cube LUT nonfinite rejection, ZIP/XML validation, monochrome JPEG XL LinearRaw DNG support, and updater UI refinements. These require app-specific regression review before Android porting.
- Read-only provenance helper: `python3 tools/lightcraft/verify_v016_source.py /path/to/official/v0.16.0/checkout`. Clone/tag checkout is an explicit local step; this branch does **not** fetch or alter sources automatically.

## Preserve Android-specific work

This review stacks on the existing approved LightCraft icon branch/PR #44, not main. Preserve `assets/lightcraft/lc-user-approved.png` and its recorded SHA-256 `8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4`, existing SAF import/export, session/sidecar data, UI, keyboard mappings, update channel, and RAW/ICC/export behavior. Do not substitute desktop update installation for the GitHub ARM64 APK update model. Do not assume the old v0.11 source-lock/API hashes apply to v0.16.

LightCraft is excluded from blanket 4 GiB shared-font scanning until its actual watermark/text-rendering paths are reviewed; see `docs/LIGHTCRAFT_ANDROID_REVIEW.md`.

## Blocked gates — no automatic production action

1. Compare v0.11 Android adapter API against v0.16 and port **without** discarding existing Android-only changes.
2. Run source provenance helper, host/RAW/colour/export regression tests and relevant public ARM64 compile. No build has been run by this PR.
3. Verify exact ARM64 APK ABI, package `com.artcraft.lightcraft`, versionCode continuity, launcher/adaptive icon, updater and SAF behavior.
4. Require original LightCraft permanent signing key **only on owner-operated HONOR Linux Lab**. Never invoke GitHub private signing, invent a replacement keystore, or claim a production upgrade without certificate comparison.
5. Require exact signed APK SHA256 and owner device acceptance, then separate explicit merge/release approval. Existing public APK stays untouched.

This branch adds only a locked upstream identity, a read-only verification helper and this review note. It is a safe staging point, **not** a synchronized or installable Android v0.16 build.
