# ArtCraft Android Suite — approved launcher icon standard

Updated 2026-10-22. This is the shared icon handoff and review record, not a
permission to publish apps, replace signing certificates or change production builds.

## Visual requirements

- Reuse the exact user-approved per-app glossy letter artwork. Never redraw it
  with a system font, flatten the glass effects, recolour it as a different app,
  or substitute a similar design.
- Respect the Android API 26+ **108dp adaptive icon canvas** and central **72dp
  safe area**. Do not scale the whole original tile edge-to-edge into the
  foreground: on HONOR MagicPad 4 that clipped the DesignCraft D and c.
- For approved artwork already committed, keep its bytes, recorded SHA-256
  validation, and legacy mipmap icon resources unchanged. The adaptive
  foreground can be **derived** with artwork scaled to a maximum ~61% of its
  canvas, feathered tile edges and an opaque matching brand background.
- Avoid transparent black-looking corners, embedded hard frames, white wedges
  or additional square masks. Let Android apply the launcher shape.
- Check the compiled APK resources, especially mipmap-anydpi-v26/ic_launcher.xml
  and drawable-xxxhdpi/ic_launcher_foreground.png. A source PNG preview alone
  does not confirm what the launcher displays.
- Test real icons on the HONOR MagicPad 4 before declaring a production icon
  accepted. Preserve the upstream source pins, versions, feature patches,
  keystores, signing identities, and existing released APKs.

## Current branch handoffs

| App | Icon integration | Scope / branch |
| --- | --- | --- |
| DesignCraft (Dc) | Glossy approved source and Android-safe composite committed; candidate passed 2026-10-22, tablet re-test still required | `designcraft-android-candidate` |
| VectorCraft (Vc) | Exact uploaded `assets/branding/vectorcraft/vc-glass-approved.png` preserved; adaptive-only safe-area patch staged, candidate CI re-check required | `vectorcraft-photocraft-parity-20261021` |
| FilmCraft (Fc) | Existing uploaded approved icon preserved; adaptive-only safe-area patch staged in both candidate branches; enhanced FilmCraft SAF/IME launcher overlay has an independent build failure | `filmcraft-v0.10.0-android1-candidate`, `filmcraft-android-candidate` |
| PDFCraft (PdfC) | Approved red image present; custom workflow already centres 278px foreground in 432px adaptive canvas; do not overwrite this distinct packaging without testing | `pdfcraft-v0.10.1-android1-candidate` |
| WordCraft (Wc) | Approved Wc source retained with checksum guard; adaptive-only safe-area patch staged, CI re-check required | `review/wordcraft-v0.9.0-android1-20261022` |
| DeckCraft (Dk) | Approved red PowerPoint-inspired Dk source retained with checksum guard; adaptive-only safe-area patch staged, CI re-check required | `review/deckcraft-v0.9.0-android1-20261022` |
| LightCraft (Lc) | Exact uploaded glossy cyan/blue icon is staged and checksum-pinned, but Android candidate/icon resource verification has not been implemented | `review/lightcraft-approved-icon-20261022` |
| PhotoCraft (Pc) | Existing production signing/release source unchanged; previous review explicitly requires the *exact* uploaded cyan Pc source to be committed before enabling `-appicon` | `review/photocraft-icon-upstream-safety-20261021` |
| EffectCraft (Ec) | Source audit only; no checked-in approved icon/build integration verified yet | `review/effectcraft-v0.13.0-android1-20261022` |
| GridCraft / ExcelCraft (Xc) | Source audit only. Confirm app name and approved Xc asset mapping before applying branding | `review/gridcraft-v0.9.0-android1-20261022` |
| SoundCraft / CADCraft / other suite apps | Await per-app approved source, Android integration and safe candidate checks | Not yet verified |

## CI safety gates

The VectorCraft, FilmCraft, WordCraft and DeckCraft candidate branches carry
scoped `adaptive_safe.py` helpers for the reviewed external builder at
`MostafaXS1/artcraft-android@ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.
They edit the *temporary builder* `lib/app_icons.py` only for the targeted
application and only when an explicit approved `-appicon` is supplied. Each
helper fails closed if the builder's adaptive-icon code changes. No new signing
keys or release workflows are introduced.

Do not promote these candidate changes until their GitHub Actions jobs pass,
the icon is visually confirmed on an installed candidate, and each app's
existing signing/version/feature-preservation checks pass. A green candidate
build does **not** authorize production publication or a key change.
