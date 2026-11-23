# PDFCraft v0.22.0 Android candidate

**Status:** draft, test-only candidate. This is not a merge, permanent signing operation, or public release.

## Source and baseline

- Protected ArtCraft baseline: `pdfcraft-v0.21.1-android.10`
- Protected ArtCraft baseline commit: `6e58b1674633b4f5745c308b6c34c0f7ff42e02b`
- Candidate base branch: `pdfcraft-v0.21.1-android.10-baseline` (a reference-only branch created from that exact protected tag)
- Official upstream source: `storytold/pdfcraft` tag `v0.22.0`
- Official upstream commit: `ac140f809d554981a5276d748e6193fcf4d4bdfa`

The candidate retains the protected Android.10 tree, including the current PDFCraft stylus wheel, approved Pc branding assets, Android trackpad and stylus work, lifecycle handling, SAF/font integration, in-app updater, OCR bridge, and the full existing PDFCraft regression suite. Only the following files differ from the protected baseline:

1. `.github/workflows/pdfcraft-candidate.yml` — isolated ARM64 candidate workflow.
2. `docs/pdfcraft-v0.22.0-android-candidate.md` — this candidate record.
3. `lib/build-common.sh` — preserve the optional adaptive foreground behavior and invoke the audited Android winit overlay for the v0.22.0 candidate.
4. `tools/pdfcraft/winit_v015_compat.py` — restore the exact upstream winit 0.30.13 API required by egui-winit 0.37, while reapplying the reviewed Android mouse/scroll/hover and lifecycle patches for v0.22.0.
5. `tools/pdfcraft_stable_audit.py` — advance the official upstream comparison baseline from v0.10.1 to v0.21.1.
6. `tools/test_pdfcraft_adapter.py` — retain the complete Android.10 regression suite while testing the candidate package ID and approved Pc icon, including a guard against skipping the v0.22.0 winit overlay.

## Candidate identity and signing

- Android version name: `0.22.0-android.1`
- Expected version code: `16782848`
- Test-only package ID: `com.artcraft.pdfcraft.v0220test1`
- APK output path: `output/pdfcraft-0.22.0.apk` (the builder names the file from the upstream workspace version; the Android version name is stored separately in the manifest).
- ABI: ARM64 / `arm64-v8a` only.
- Icon: protected approved Pc artwork at `assets/pdfcraft/approved-icon.webp`.
- Signing: a new disposable keystore generated on the hosted runner for this run only.
- Image tooling: Pillow is installed in a temporary Python virtual environment for the approved WebP icon and stylus-wheel asset generation.

The test package is deliberately different from production `com.artcraft.pdfcraft`, so it can be installed side-by-side. Its signature is not compatible with the production app. Never use it as an update. The workflow has read-only repository permissions and does not create tags or releases.

## CI gates

1. Verify the candidate is a direct child of the protected Android.10 commit and that no other baseline files changed.
2. Verify the exact official upstream tag and commit.
3. Run the existing full PDFCraft Android adapter regression suite against upstream v0.22.0.
4. Compile the Android modifier tests against egui 0.37, matching upstream v0.22.0.
5. Run upstream PDF object/content unit tests.
6. Build the ARM64 APK with a fresh disposable signing key.
7. Verify package ID, version name/code, ABI, launcher icon resources, APK signature and SHA-256; upload the candidate artifact for inspection.

A green CI run does not establish device compatibility or PDF fidelity. Device acceptance remains required on the HONOR MagicPad 4: launch/relaunch, SAF open/save/export round trips, annotations, forms, embedded fonts, encrypted PDFs, signed PDFs, CJK/RTL text, keyboard/IME, trackpad, stylus/pressure/wheel, orientation changes, and updater/startup-check behavior. Do not clear production app data or install the disposable build over production.

## Known upstream issue to keep visible

Upstream issue [#8126](https://github.com/storytold/pdfcraft/issues/8126) reports that the Layers tab is empty for layered PDFs in v0.21.0 and v0.22.0. This is an upstream regression, not an Android integration fix in this candidate. Include a layered-PDF test and do not claim this candidate resolves the issue.

## Promotion gate

Keep the published Android.10 release and its signing identity untouched. Stop after the disposable candidate artifact and device test checklist. Do not merge, permanently sign, tag, publish, or replace a release unless separately approved.
