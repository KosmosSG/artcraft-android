# DesignCraft 0.12.0-android.1

This release preparation combines the existing PhotoCraft-parity branch with a launcher packaging fix. Official source is v0.12.0 at `5e8ef678321cfdd2d18927e2af94d58e5f9d8836`; builder remains `ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.

- The approved glossy Dc PNG is preserved. Build-time launcher layers remove its black exterior canvas and pad the whole artwork for circular and rounded-square masks.
- Type exposes Custom Font Import (TTF/OTF), Select Shared Font Folder, and Refresh Shared Fonts at the top of the menu. Existing persisted SAF permissions, local font cache and font.reload behavior are retained.
- Help exposes Check for Updates and Startup Update Settings. Startup checks remain optional and saved, following PhotoCraft. Manual checks show native Android feedback; automatic checks only alert when a newer compatible release exists.
- Update discovery checks app-specific published metadata, production package, permanent certificate, matching APK asset and increasing Android versionCode. Installation remains a user action handled by Android.
- Existing document SAF, IME, keyboard customization, optional touch pad and GPU diagnostics remain.

Production package is `com.artcraft.designcraft`. The existing permanent certificate is `c45236b436cbfbfbeade716b11cb24a50a795a6af3f147132ce6f19753fea394`; the private signing repository records a restored encrypted backup. Never replace it. The earlier disposable candidate used a separate package and cannot update over this production app.

Python tests cover menu patch drift, retained font-cache protections, icon source identity/masks and clipping. CI checks the generated Java Activity and metadata policy. The private pipeline builds ARM64, signs on an isolated runner using the existing backup, and verifies source provenance, signature, package, version and unchanged payload. Tablet behavior must be recorded separately; CI is not a device test.

Prior signing-pending statements in REVIEW.md, APPROVED_ICON_STATUS.md and PRODUCTION_GATES.md are historical. This release record and the private signing identity supersede them. No scheduled builds or main merge are enabled here.

## Android revision 2 — owner menu and icon improvements

The owner's new 1254px glossy magenta Dc upload (SHA-256 `f6dbdba9ea8e510414934c0aea697457a922dfada96feecc0baf0809d8e391ae`) replaces the icon source used by the v0.12.0-android.1 build; its pinned 192px packaging derivative preserves the appearance at Android launcher sizes. Font import/shared-folder/refresh actions now appear at the bottom of the Type menu. Update checking and startup setting appear immediately below About DesignCraft at the bottom of Help, because About is a dialog action rather than a submenu. The production upgrade must be v0.12.0-android.2 with Android versionCode strictly above 16800002 and the original certificate unchanged. Do not overwrite the first release.