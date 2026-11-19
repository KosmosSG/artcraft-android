# LightCraft approved Android icon

The user explicitly selected the uploaded Glossy Glass Lc App Icon(1).png on 22 October 2026.

Use the exact original at assets/lightcraft/lc-user-approved.png.
SHA256: 8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4
Library source: libfile_f480a7545b60819198e00f08ecce5fcc

Preserve the blue/cyan liquid-glass Lc lettering, background and transparency. Do not redraw, recolour, replace or use another app icon. Only derive required Android launcher densities/adaptive resources from this original after inspecting the actual builder output.

## Integration into the future isolated candidate
Before building:
```bash
echo '8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4  assets/lightcraft/lc-user-approved.png' | sha256sum --check
```
Pass the absolute path of this checked asset as the pinned reference builder's -appicon= argument for LightCraft. Verify the actual packaged legacy/adaptive launcher resources; do not treat this source asset or preview as evidence that an APK includes it.

No existing LightCraft branch/PR was found during this transfer review. This branch stages approved artwork only. Official source/version/API/license, candidate workflow, package/signing history, monotonic versionCode and build verification still require review. No APK, permanent signing or publication is performed by this change.
