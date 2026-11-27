# Upstream integration review — 2026-11-27

This branch is a guarded upstream-integration review for the four ArtCraft Android apps
that are behind the latest stable Storytold release.

## Rules

- Protected published Android releases remain untouched.
- Upstream source is integrated only from the exact stable release commit listed below.
- Existing Android customizations must be preserved; no launcher/icon/menu replacement from upstream is permitted.
- No production signing, release creation, or permanent publication is performed by this review branch.
- Each app requires an ARM64 candidate build and owner device validation before promotion.

| App | Current protected Android baseline | Stable upstream | Upstream commit |
|---|---|---|---|
| WordCraft | v0.18.1-android.1 | v0.19.1 | 5d658dc033f3139926839bffd6ae0eef558c210c |
| EffectCraft | v0.24.1-android.6 | v0.25.1 | f5ce0dc56803a47ea9e483f400ab1c24426caa50 |
| DesignCraft | v0.20.1-android.10 | v0.21.1 | 7470feae15b824534c842b7888952e63f6493003 |
| DeckCraft | v0.18.1-android.8 | v0.19.1 | 4a980c33ddf37eb64157777fcaeab6d19baa5878 |

## Required Android preservation gates

### WordCraft
Preserve the Wc compact menu, stylus wheel, 5,000-font / 4 GiB SAF font workflow,
keyboard/IME shortcuts, Ctrl+W D/C/S, Ctrl+Q, pressure/hover/palm rejection,
two-finger and trackpad safeguards, document recovery, and in-app updater.

### EffectCraft
Preserve the Ec compact menu and branding, PhotoCraft-style 8-slot stylus wheel,
hover pointer and hover isolation, Ctrl+W D/C/S, Ctrl+Q, Undo/Redo, fonts,
touch/trackpad navigation and selection suppression, and in-app updater.

### DesignCraft
Preserve the Dc launcher/menu branding, native pre-touch Magic-Pencil hover pointer,
stylus wheel and button behavior, hover isolation, Ctrl+Z, Z zoom, fonts, file handling,
and verified in-app updater.

### DeckCraft
Preserve the Dk launcher/menu branding, PhotoCraft-style stylus wheel, pen-hover pointer,
hover isolation, fonts import/shared/refresh, D/C/S shortcuts, Ctrl+W, PPTX open/save,
touch/trackpad safeguards, and in-app updater. Legacy .ppt support must not be claimed
unless independently verified.

## Promotion rule

This file is a review record only. Do not merge or publish an Android release until the
four candidate builds compile for arm64-v8a, pass package/version/icon/signing checks,
and are separately device-tested on the target Android tablet.
