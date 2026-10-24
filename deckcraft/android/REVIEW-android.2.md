# DeckCraft 0.9.0-android.2 review

Scope: existing PR #12 only; pinned upstream v0.9.0 and reference builder unchanged.
Package com.artcraft.deckcraft; versionCode 100000002; original independent permanent certificate required by CI.

- Android File → Import Font, Help → Check for Updates, View → Tablet Tools.
- Docked panel reserves space and remembers visibility through existing UI preferences.
- Font imports restore from private app storage. Import invalidates slide/thumbnail textures.
- Imported legacy family aliases (for example Montserrat SemiBold) appear in the font dropdown and resolve through the existing renderer.
- Panel lists detected families/styles; import notifications distinguish registration and persistence errors.
- Manual updater filters stable deckcraft-v* tags, ARM64 APKs, newer semantic revisions; requires GitHub SHA256 asset digest, package identity, higher versionCode, matching original certificate and Android compatibility before offering APK save. Android performs its installation checks when the saved APK is opened. No automatic download or installation.
- Approved October 24 red Dk artwork source SHA256: ad317bea26246ba72079701d695c402cb3e11ee91413eff09d48c6d6669aa75e. Derivative SHA256: c34ca250698ab31399ab8697119b27fdbd22761bc2a1ef957a250a1eb82b9d85. Edge extension replaces feathered inset; only the launcher supplies a rounded mask. Artwork used under the owner's explicit instruction for this app.

Validation: Python patch anchors/syntax and local Java version comparisons checked. CI includes ARM64 compilation, certificate/package/ABI/version/archive/resource verification and a font import → selection → render → native .deckcraft save/reopen regression using upstream-owned Regular/Semibold fixtures. These checks do not substitute for device testing.

Required HONOR tests before production publication:
1. Update in place; confirm icon size, no clipped lettering or extra frame.
2. Import Montserrat Regular and SemiBold TTF, then a supported OTF; confirm notifications and detected families/styles.
3. Select slide text and change family, including the SemiBold family alias. Save, close and reopen the .deckcraft presentation; restart app and repeat.
4. Hide/show Tablet Tools, restart, and confirm setting and usable slide area.
5. Check updates online and offline. When a newer signed release exists, download, save and verify in-place Android update behavior.
6. Check slide editing, slideshow and normal export workflows.

No production release, automatic upstream synchronization, other-app changes or new signing key.
