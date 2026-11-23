# ArtCraft Android suite — upstream audit (2026-11-23)

## Scope and safety

This is an inventory and review plan only. It does not change application source, protected release branches, signing identities, tags, APK assets, or production workflows. Do not merge this audit or promote any candidate merely because an upstream release exists.

Repository: `KosmosSG/artcraft-android`
Builder-supported app flags (from `README.md`): PhotoCraft, VectorCraft, FilmCraft, LightCraft, PdfCraft, EffectCraft, DesignCraft, FigCraft, WordCraft, SoundCraft, DeckCraft, CADCraft, GridCraft.
The ArtCraft core upstream repository and the separate ArtCraft Launcher are tracked as adjacent projects, not assumed to be Android app targets of the same build flag.

## Official upstream release inventory

Latest GitHub `releases/latest` tags queried on 2026-11-23:

| App | Official upstream tag | Published | Android-side inventory |
|---|---|---:|---|
| PhotoCraft | v0.23.1 | 2026-11-12 | Protected Android.5 branch; OpenFill draft PR #168; Companion work remains separate/deferred |
| VectorCraft | v0.24.1 | 2026-11-12 | Protected Android.16 stable branch; retain tested keyboard/IME, trackpad/touch, stylus wheel and next hover-pointer requirement |
| FilmCraft | v0.20.1 | 2026-11-12 | Android.8 production branch; preserve approved signed production identity |
| LightCraft | v0.21.1 | 2026-11-12 | Android.4 owner-approved branch |
| PdfCraft | v0.22.0 | 2026-11-23 | Android.10 protected release; separate v0.22.0 candidate branch and draft PR #170 |
| EffectCraft | v0.24.1 | 2026-11-12 | Android.6 optimized/original-certificate branch |
| DesignCraft | v0.20.1 | 2026-11-12 | Android.10 production-payload branch |
| FigCraft | v0.18.1 | 2026-11-12 | No dedicated Android release branch found in current branch inventory |
| WordCraft | v0.18.1 | 2026-11-12 | Android.1 original-sign release branch |
| SoundCraft | v0.20.1 | 2026-11-12 | No dedicated Android release branch found in current branch inventory |
| DeckCraft | v0.18.1 | 2026-11-12 | Android.8 optimized release branch |
| CADCraft | v0.20.1 | 2026-11-12 | Android.15 production branch; Android.20.1 stable branch |
| GridCraft | v0.19.1 | 2026-11-12 | Android.8 release branch |
| ArtCraft core | artcraft-v0.41.1 | 2026-11-07 | No matching app-specific Android release branch found; audit separately from Craft app APKs |

The suite builder README currently lists 13 app flags. FigCraft and SoundCraft are therefore included in this audit even though no dedicated Android release branch was found. Their Android port feasibility must be assessed before creating release candidates.

## Protected Android baselines found

- PhotoCraft: `release/photocraft-v0231-android5-optimized-20261113`
- VectorCraft: `release/vectorcraft-v0241-android16-stable-20261117`
- FilmCraft: `release/filmcraft-v0201-android8-production-20261114`
- LightCraft: `release/lightcraft-v0211-android4-owner-approved-20261114`
- PdfCraft: `release/pdfcraft-v0211-android10-exact-publish-20261114`
- EffectCraft: `release/effectcraft-v0241-android6-optimized-original-cert-20261114`
- DesignCraft: `release/designcraft-v0201-android10-production-payload-20261114`
- WordCraft: `release/wordcraft-v0181-android1-original-sign-20261116`
- GridCraft: `release/gridcraft-v0191-android8-size75-20261114`
- CADCraft: `release/cadcraft-v0201-android1-stable-20261117`
- DeckCraft: `release/deckcraft-v0181-android8-optimized-20261114`

These branch names are inventory references, not permission to rewrite or move them. No production branch, tag, release asset, keystore or signing secret may be altered during the audit.

## Existing integration work and blockers

1. PdfCraft v0.22.0 candidate is tracked by draft PR #170. Its head branch is `pdfcraft-v0.22.0-android-integration`; the PR targets `main`, not the protected PdfCraft release branch. Before considering it a candidate derived from the protected baseline, verify the full merge-base and source/adapter diff against the protected Android.10 branch. Its disposable signing workflow explicitly leaves device/PDF-fidelity/SAF tests outstanding. Do not merge or publish.
2. PhotoCraft OpenFill is draft PR #168. The PR conversation records a successful small-image U2NetP Remove Background → new layer → Undo test, but the full four OpenFill operations, high-resolution alpha-proxy quality, cancellation/relaunch, and companion integration are not all accepted. Keep Companion separate and do not claim those features are production-ready.
3. Existing suite-wide older integration branches and draft PRs are historical work, not proof that each app is current with today's upstream tag. Rebase/recreate only after per-app diffs and acceptance gates are reviewed.
4. ArtCraft Launcher has separate Android.12 / Play Protect work. Keep launcher versioning and signing separate from individual app APKs.

## Integration order

### Wave 1 — lowest-risk source/API review first
WordCraft, GridCraft, CADCraft, DeckCraft, LightCraft.

For each: pin exact upstream tag+commit; inspect manifest/dependency/toolchain changes; compare Android adapter and generated launcher boundaries; preserve SAF/font import, updater, keyboard/IME, trackpad/touch and stylus-wheel behaviors; run host tests and an isolated ARM64 disposable-signed candidate only if the source diff is compatible.

### Wave 2 — feature-heavy apps
EffectCraft, DesignCraft, FilmCraft, then PhotoCraft.

In addition to Wave 1 checks, preserve app-specific input routing, file round-trips, export, undo/redo, original app icons and production signing identity. PhotoCraft OpenFill remains an independent workstream; do not combine it with Companion.

### Wave 3 — high-risk integrations
VectorCraft and PdfCraft.

- VectorCraft: preserve Android.16 as the rollback point; verify physical keyboard/IME after relaunch and opening/importing AI files, touch/trackpad pan and pinch, no accidental object selection, hover pointer visible before pen contact, stylus wheel isolation, and heavy-document rendering performance.
- PdfCraft: v0.22.0 includes a major engine/shared-library migration. Audit API changes and security fixes, test PDF open/edit/save/export, forms, annotations, embedded fonts, OCR, signatures, encrypted files, SAF, lifecycle/Ctrl+Q, touch/trackpad and stylus. A changed signed PDF can invalidate an existing signature; do not claim universal signature preservation.

### Wave 4 — missing Android targets
FigCraft and SoundCraft: perform a source/toolchain/Android API feasibility review first. No APK build, production release or signing key should be created until an explicit Android baseline and acceptance criteria exist.

## Required promotion gates

- Exact upstream tag and commit are verified and pinned.
- Protected release branch remains unchanged and a tested rollback reference exists.
- Android-specific adapter changes are allowlisted and reviewed; no silent source resets or blanket upstream merges.
- Host tests and ARM64 candidate workflow pass.
- Candidate is disposable-signed and isolated from installed production packages where signature identity differs.
- On HONOR MagicPad 4, validate launch, file open/save/export, SAF, fonts, keyboard/IME, shortcuts, touch, trackpad, stylus hover/button/wheel, updater, undo/redo and representative app-specific workflows.
- APK ABI/package/version/versionCode/icon/manifest/hash/signature and size are checked.
- User explicitly approves permanent signing and publication separately. Until then: no production signing, tagging, merging or publishing.

## Current result

Upstream release inventory is complete for the 13 builder-supported app repositories plus ArtCraft core. This document does not certify source compatibility or APK readiness. The next implementation action is a per-app source diff and candidate build, beginning with Wave 1, while preserving every protected release branch.
