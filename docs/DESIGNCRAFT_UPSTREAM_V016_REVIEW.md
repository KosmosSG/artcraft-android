# DesignCraft official v0.16.0 — source-lock and Android 4 GiB preservation review (2026-11-02)

**Scope:** Review-only, stacked on DesignCraft 4 GiB font-scanner draft PR #98. No source port, new APK, signing, merge or release is claimed.

## Verified official source
- Official stable tag: https://github.com/storytold/designcraft/releases/tag/v0.16.0 (2026-11-01 19:32:27 UTC; not draft or prerelease).
- Direct tag commit: `1fe8885bda7451263879cfbb256b9a3d46c411bf`. Root Cargo workspace version `0.16.0`, Rust MSRV `1.95`, repository `storytold/designcraft`.
- Read-only provenance helper: `python3 tools/designcraft/verify_v016_source.py /path/to/clean/tagged/designcraft`; no checkout, build, signing or publishing is performed by this helper.
- Review upstream Type menu and CJK command structure, File/Quit handling and shared craft-update check-result UI against Android native menus and updater.

## Preserve tested Android behavior
- Preserve the publicly listed DesignCraft v0.12.0-android.9 APK and its stated 4 GiB recursive shared-font scanner, 5,000-file/folder refresh bounds, 64 MiB/font cap, TTF/OTF/TTC support, import success/error feedback and font catalog refresh. Public android.9 release asset SHA-256 is `bf74cf217c989a951303d7d5131b980871699335d429e523e50c10f310929162`; this is asset metadata, **not independent proof of internal scanner behavior**.
- Preserve Android-only SAF permissions, menus, Esc and D/C/S shortcuts, approved Dc launcher/adaptive artwork, updater GitHub APK channel and `com.artcraft.designcraft` package identity.
- Existing v0.14 host compatibility PR #89 does not prove v0.16 source/API compatibility. Avoid overwriting Android-only changes.

## Blocked gates
1. Port upstream v0.16 source and review dependency/API changes on an isolated integration branch without changing existing published APKs.
2. Pass host/type/menu/font tests and Android integration checks; build a public unsigned ARM64 candidate only after compatibility is established. No private/quota-failing build retries.
3. Verify exact APK SHA-256, ABI, package, monotonic versionCode, fonts, updater and approved assets.
4. Owner alone signs using original DesignCraft permanent keystore on HONOR Linux Lab; independently verify certificate matches installed production.
5. Require exact signed APK HONOR MagicPad 4 acceptance and separate explicit owner merge/publication approval. No private GitHub Actions signing, auto-merge, release/tag or Latest change.

This is a source provenance staging PR, **not** a v0.16 Android integration or new installable APK.
