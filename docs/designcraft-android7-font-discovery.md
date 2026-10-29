# DesignCraft Android.7 — font discovery, starting from tested Android.6

Baseline: `feature/designcraft-unsaved-dcs-20261029` (PR #92; versionName 0.12.0-android.6, versionCode 16800007). This branch must not alter or publish that working APK.

## Source audit findings
- `tools/designcraft/prepare_builder.py` patches Android HOME/XDG paths, migrating read-only system-font symlinks into writable directories while leaving imported fonts intact.
- `tools/designcraft/support/font_methods.java` scans persisted SAF folders for TTF/OTF (bounded at 200 files, 32 MiB/file, 128 MiB total), caching under `home/.local/share/fonts/shared`.
- `templates/android/system_fonts.rs` supplies script-based UI fallback fonts and a desktop-style fontconfig environment. Fallback glyph coverage does **not** imply that every Android system font family appears in DesignCraft's typeface picker.
- The actual DesignCraft font catalog is in the pinned upstream source and must be inspected/tested against the generated Android build before modifying selection behavior.

## Implementation acceptance criteria
1. Preserve working Android.6 import, shared SAF folder, ESC, D/C/S and signed update path.
2. Enumerate readable system font files and all supported TTC faces (where supported by the actual font engine), derive real family/style names from internal font tables, deduplicate, and merge with imported and SAF fonts.
3. Never list fonts that the document text engine cannot select or render; avoid promising inaccessible OEM fonts.
4. Add diagnostics displaying scanned, accepted, duplicated and rejected families and scan errors; make manual refresh update the actual document font picker.
5. Test restart, selected typeface rendering, imported Montserrat/Inter, CJK fallback, unsupported/corrupt files and SAF access revocation.
6. Reserve next versionCode > 16800007, use original DesignCraft signing identity only in private signing workflow, and keep this PR draft until the exact signed Android.7 APK is device-tested.

## Safety
No changes to the Android.6 branch, any published release, icons, keyboard shortcuts, updater, package identity or production keys. Do not claim feature completion from this plan alone.
