# DesignCraft v0.17 upstream integration — published Android.9 baseline lock

Status: BASELINE VERIFIED; INTEGRATION AND TEST APK NOT VERIFIED.
Scope: DesignCraft ONLY. This branch is not a published release and is not production-approved.

## Published stable baseline (immutable)
- Repository: KosmosSG/artcraft-android
- Owner-tested, published release: designcraft-v0.12.0-android.9
- Published release tag HEAD: e8d7c43a4c1a628433bf92975ea616ad47682440
- IMPORTANT: the published tag refers to an unrelated GridCraft commit on main. Do not use its commit as DesignCraft source.
- Provenance from successful permanent signer run 41363008462, signing stage:
  - verified DesignCraft build source commit: 652f1475ff02fc7c7dc6b1652f2d36404d931838
  - original public compile run 41013650823
  - APK SHA-256: bf74cf217c989a951303d7d5131b980871699335d429e523e50c10f310929162
- Compare: source commit 652f147... descends from designcraft-v0.12.0-android.8 with two additional DesignCraft commits for the 4 GiB font scanner. The public build workflow commit descends one more step.
- Original public stable APK: 88,370,167 bytes.
- Stable application ID: com.artcraft.designcraft. Keep the existing production signer and installed app/data unchanged.
- Verified source branch starting point: exact commit 652f1475ff02fc7c7dc6b1652f2d36404d931838.

## Proposed upstream (immutable)
- Official repository: storytold/designcraft
- Latest published stable as checked 2026-11-04: v0.17.0
- Upstream tag commit: e79d682e02dc66f14370958b193bfa46072b2f41
- Proposed test version: 0.17.0-android.1
- Candidate application ID: com.artcraft.designcraft.test
- Architecture: arm64-v8a
- Temporary/disposable signing ONLY.

## Required feature-preservation checks
- Preserve the published Android.9 recursive 5,000-file/folder scan, up-to-4-GiB font scan budget, 64 MiB per font and TTF/OTF/TTC handling.
- Shared SAF library, system font discovery, font import + feedback, font reload, and stable storage.
- Esc exits text editing; D/C/S repeated close-dialog interactions; keyboard shortcuts, focus, T/V tools and selection.
- Approved glossy Dc launcher/adaptive icon and in-app branding, menus, touchscreen / touchpad navigation and GPU compatibility.
- Preserve file opening/saving, session state and updates. Do not silently change offline requirements.

## Integration constraints
- Work from the protected release *source* at 652f147..., not the unrelated published release-tag pointer.
- Review upstream improvements selectively; do not reset the Android baseline or accept loss of Android functionality.
- A successful build from a newly cloned upstream v0.17.0 source with a partial Android overlay is NOT sufficient to prove approved published features were preserved.
- Existing branch feature/designcraft-v017-android-test-20261104 and run 41761357020 are experimental reference material ONLY; source-contract/build checks passed, but no published-parity or device test was established. Do not use this artifact as the approved test candidate.
- Keep integration changes DesignCraft-scoped. Avoid edits to other suite applications and unnecessary GitHub Actions consumption.
- Optimized release-style ARM64 temporary-signed APK preferred over unoptimized debug APK, only after source and feature preservation checks.
- Compare equivalent stable and candidate APK variants, report size and performance honestly.

## Gates (fail closed)
1. Verify this branch's ancestry from 652f147... and the upstream 0.17 tag commit.
2. Port individual compatible changes into the verified Android baseline; review every Android-impacting source diff and resolve conflicts without sacrificing approved functionality.
3. Run static, compatibility, and regression checks for fonts, controls, files, branding, GPU, updater, and data.
4. Generate ONE necessary ARM64 optimized temporary-signed APK, ideally a separately installable test package. Verify version, ABI, signer, checksum and installability.
5. Report package size, regression results, known limitations and download link for HONOR MagicPad 4 device testing.
6. STOP. Require separate explicit device approval, permanent-signing approval and publication authorization.

No production signing, publishing or release/tag changes are authorized by this document.
