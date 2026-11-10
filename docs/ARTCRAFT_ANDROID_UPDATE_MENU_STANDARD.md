# ArtCraft Android: Update Menu Interaction Standard

Status: preferred behavior for **future Android development** across PhotoCraft, DeckCraft, VectorCraft, GridCraft, WordCraft, DesignCraft, EffectCraft, LightCraft, PDFCraft, FilmCraft and other ArtCraft applications. This document is **not** an instruction to change or publish other apps immediately.

## User-approved reference

Reference: PhotoCraft compact launcher menu, and DeckCraft v0.17.0-android.3's `Dk > App Updates` submenu.

- Use an app-icon launcher menu, with compact left-aligned labels and a **nested App Updates submenu**.
- Offer **Check for Updates…**, **Toggle Update Check at Startup**, and **Toggle Preview Releases** if preview support exists.
- **No floating settings dialog** for these toggles. Tap once to change a saved preference.
- While the toggle is **ON**, prefix the corresponding menu item with a visible **✓**. While **OFF**, show an unmarked item. Check marks must reflect the saved value when the menu reopens, including after a full app restart; never derive them solely from a temporary UI switch.
- Confirm changes with a brief **bottom toast/pill** using the current app's name or icon: e.g. `Dk Update checks at startup: ON` or `OFF`. Do not open a dialog just to report success.
- Save state in durable app-private settings. If the UI and Android bridge are separate, keep them synchronized before showing the checkmark.
- Default update channel to **stable**; let preview releases be a separate explicit opt-in. Retain existing app-specific startup check intervals (e.g. 24-hour throttling) and the **manual check** action.

## Security and preservation

- Always use the **latest verified published working Android release** as the protected baseline; do not remove or regress approved Android-specific features, menus, fonts, file associations, keyboard shortcuts, stylus support, gestures, or recovery.
- Keep the original production signing key and published releases untouched during development.
- Use isolated integration/test branches, compile ARM64 test APKs with **temporary/disposable keys** and a separately installable package, and obtain device validation before permanent signing or publishing.
- Maintain authenticated/verified HTTPS downloads, package/architecture/version checks, original signing certificate continuity and standard Android installation consent. Never silently install.
- Prefer minimal patches and limit GitHub Actions minutes. Reduce APK size only by safe stripping/compression without removing required code or ABI support.

## Recommended regression checks

1. Turn startup checks ON → visible ✓, bottom ON feedback, and no modal.
2. Reopen menu → ✓ remains. Fully relaunch app → ✓ remains.
3. Turn startup checks OFF → ✓ disappears and bottom OFF feedback.
4. Repeat both actions for preview channel, with stable-only default.
5. Check for updates still works, and startup checks respect the user's preference and throttle.
6. Test all approved features from the protected release before signing or publishing.

Adopt this UI standard opportunistically during each app's **next approved development/integration**, not by bulk-changing existing stable releases.
