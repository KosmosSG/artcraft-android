# VectorCraft Android 3 device fixes

The user installed android.2 and reported a black launcher border, missing Help update controls, and missing Custom Font Import. This revision retains official VectorCraft v0.14.0 at `ad0566943ab9741e6356bbc9b53c3cc09895068d` and the existing Android adapter, package, and permanent signing identity.

## Changes

- Generate launcher resources from the approved glossy Vc source, removing only the near-black canvas connected to its exterior. Transparent legacy corners and a copper adaptive background replace the black surround. Padding preserves the lettering under circular and rounded-square masks; the approved input PNG is unchanged.
- Add **Help > Check for Updates** and a checked **Check for Updates at Startup** command. A missing startup setting defaults to enabled; explicitly saved settings survive upgrades. Startup checks remain asynchronous and only open a dialog for an available update. Manual checks show results, including no published release and network errors.
- Add **Type > Custom Fonts > Import Font (.ttf / .otf)**, **Select Shared Font Folder**, and **Refresh Shared Fonts**. They call the existing SAF/font-validation bridge and rescan the existing application font catalog. Completion or failure is visible in the status bar.
- Expose Android Settings under Help and keep the existing Android Tools fallback, keyboard controls, GPU details, file operations, and persistence.

The Android menu overlay verifies the exact upstream file hashes before applying. The builder uses an immutable source commit; the overlay only changes the disposable build checkout.

## Validation and release gate

Local Python regression tests pass (18), including source-artwork identity, both launcher masks, circular lettering bounds, and existing Android bridge guards. The overlay applies successfully to the pinned official UI source. Java bridge, Rust command-dispatch, and ARM64 compilation run in CI. The signed APK must retain the recorded permanent certificate, package `com.artcraft.vectorcraft`, and monotonic versionCode `16780803`.

The previous android.2 APK remains the installed-device baseline. Tablet verification is still required for the three reported fixes and an update-install preserving settings before a production release. No main merge, schedule, or public publication is enabled by this change.
