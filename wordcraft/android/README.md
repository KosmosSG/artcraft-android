# WordCraft Android candidate — isolated review

Status: **candidate / NOT released**. No permanent signing key created, no APK distributed, and no tablet tests claimed.

## Source of truth
- Official upstream release: [storytold/wordcraft v0.9.0](https://github.com/storytold/wordcraft/releases/tag/v0.9.0), published 2026-10-21, stable (not prerelease).
- Resolved lightweight tag `refs/tags/v0.9.0` -> commit `2e6db0bd88795e80375176c01665cff7dbe2b057`. Never build unpinned `main`.
- Reviewed Android implementation baseline: [MostafaXS1/artcraft-android](https://github.com/MostafaXS1/artcraft-android/tree/ac54d62d9d2d6f663295a4afd8972a7a3e79f9af) at `ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`. It has WordCraft-specific SAF/print hooks, Android IME and icon generation, and a shared file association registry. **This is a reference, not evidence of Android compatibility with 0.9.0.**
- Current suite main remains unchanged. It lacks the pinned reference's `lib/app_icons.py` and `lib/android_project.py`; candidate CI therefore checks out the reference into a separate directory instead of modifying the suite's shared builder or other apps.

## Approved icon
- Original upload: `Glossy Glass Wc App Icon(1).png`, 1254 x 1254 RGBA, SHA-256 `429f49edd6b206566d65b428fe576d4e5e084a2b5285fffeeebdba0b5dd538bb`.
- GitHub source derivative: `icon/wordcraft-approved-192.webp`, resized from that exact upload, 192 x 192, SHA-256 `71bf833ddbc94b2edbf6ff2cf944bce9696f1e73f851f0f9a176a9fb7fdf7766`. This is an optimized **derivative**, not byte-for-byte original artwork.
- Candidate workflow renders this into a PNG and passes `-appicon=...` to the **pinned reference** builder. It must verify packaged adaptive and legacy icon resources; a preview by itself is not APK integration.
- Prefer the original full-resolution upload for production-quality density and adaptive assets when it can be transferred safely; verify that Android masks do not leave black corner wedges.

## Candidate target
- ARM64 (`arm64-v8a`), minimum SDK 28 per reference builder; device HONOR MagicPad 4, MagicOS 10.
- Planned Android package: `com.artcraft.wordcraft` (reference default; **no signed identity verified yet**).
- Candidate versionName: `0.9.0-android.1`; candidate versionCode: `100000001` (provisional; **not reserved for permanent signing**).
- Final APK filename convention: `wordcraft-0.9.0-android.1.apk`. Candidate output remains private to an ephemeral CI runner and **must not** become a public APK, artifact, release or installer.
- Each official release resets Android revision to `android.1`; Android-only revisions increase sequentially. The release versionCode must exceed all previously installed, signed, and published **WordCraft** builds. We cannot inspect the owner's tablet from GitHub, so final reservation is blocked pending identity/history reconciliation.

## Current capability review (not implementation claims)
| Area | Evidence and open check |
|---|---|
| Text and formatting | Upstream 0.9.0 supports Word editing, selections, clipboard, undo/redo, tables, images and pagination; real Android behavior unverified |
| Formats | Upstream reads/writes DOCX, imports legacy DOC, supports ODT/RTF/HTML/Markdown/TXT/LaTeX and PDF export. Fidelity, tables, pictures and unsupported Word features require round-trip samples |
| File bridge | Reference builder has SAF open/save/save-as, open-with/share handling; WordCraft mappings for DOCX/DOCM/DOTX/DOTM/DOC/DOT/RTF/ODT/TXT/MD/Markdown. Verify URI write-back, cancellation, autosave and restart |
| Printing | Reference wires WordCraft's PDF bytes to Android PrintManager / native dialog. Verify actual print preview, pagination, paper settings and PDF output on tablet |
| Fonts | Android system fonts are referenced; native TTF/OTF import, Montserrat and shared SAF font folders require WordCraft-specific integration review and testing |
| Input | Reference has soft IME / physical keyboard bridges; verify composition, shortcuts, selection, undo, stylus, mouse and trackpad. Customizable shortcut pad is **not implemented** |
| Updates | No WordCraft native updater or upstream watcher has been implemented here. Future checks must compare **official stable tags resolved to commits**, not arbitrary pushes |
| GPU | Do not claim Vulkan/Adreno acceleration: test actual graphics backend, report renderer and fallback accurately, no fabricated GPU diagnostics |

## PhotoCraft parity: WordCraft-native font import (candidate patch)

The upstream **v0.9.0** engine already implements `font.add` and validates TTF/OTF, plus TTC/OTC/WOFF/WOFF2. Its UI sends Android-picked font bytes from `open_async` / Inbox to `font.add` and updates font lists without a floating Custom Fonts window. The reference Android launcher did **not** initialize WordCraft's persistent `FontDb` directory; fonts could disappear on restart.

The isolated `patch_builder.py` integrates WordCraft's own `wordcraft-fonts::FontDb::load_user_fonts` before app creation and stores newly imported fonts in the WordCraft-only app-private `files/fonts` folder. It removes the Android **All files access** permission/prompt for this WordCraft candidate, relying on user-selected documents through SAF. These code paths need compilation plus tablet tests for import, restart, Montserrat and PDF embedding.

**Not implemented yet:** PhotoCraft-style SAF shared `ArtCraft-Fonts` document-tree selection/refresh (must use persisted URI grants and scoped reads without assuming primary storage); a WordCraft-specific manual/startup update-check UI and saved preference; configurable Android Shortcut Pad; stylus refinements and verified GPU diagnostics. Those features require additional WordCraft-only code and testing before any release.

## Release blockers
1. Candidate must compile; verify tag/commit, source patch scope, package, ABI, versionName/versionCode, certificate fingerprint, SHA-256 and actual packaged Wc icon.
2. Existing WordCraft signing identity must be reconciled with any external/local keys or installed APKs. No dedicated key or encrypted recovery backup has been established. **Never** borrow another ArtCraft application's certificate.
3. Separate compilation from permanent-key signing. Release verifier must compare the pre-sign and post-sign payloads with only expected signature entries differing and log reproducible hashes.
4. Permission audit: reference SAF Activity also prompts for broad **All files access**. Prefer document-scoped SAF and ensure WordCraft does not require unnecessary storage permissions in a distributed build.
5. Test Montserrat TTF/OTF import and shared font folders without floating dialog; keyboard/IME, save/backups, print/PDF, large DOCX, tracked changes, multilingual fonts, tables, embedded pictures and document round trips.
6. Manual GitHub updater metadata/public release logic requires explicit WordCraft-specific verification and permanently signed APK. **No schedules on main, no auto-merge, no release publishing**.

CI runs with a fresh temporary signing key **only on the isolated candidate runner**, retains no APK artifacts, and does not use other apps' signing secrets. Green CI establishes compilation and static APK checks, **not tablet readiness or Word file fidelity**.
