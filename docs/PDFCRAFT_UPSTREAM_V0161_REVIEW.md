# PDFCraft v0.16.1 — isolated upstream provenance review (1 November 2026)

**No Android source migration or APK build is claimed.** This branch stacks on draft PR #87 (v0.15 candidate) so existing SAF/fonts/updater/keyboard and approved red PdfC artwork remain intact. The earlier v0.15 ARM64 candidate failed and must not be silently promoted.

## Stable upstream identity

- Official [v0.16.1](https://github.com/storytold/pdfcraft/releases/tag/v0.16.1), published 2026-10-31 03:59:54 UTC; Git tag directly resolves to `24bb85308e4b65404fc908506ade6341a29999d7`.
- Root `Cargo.toml` at this tag declares workspace version `0.16.1`, Rust MSRV `1.95`, `storytold/pdfcraft`.
- Provenance helper `python3 tools/pdfcraft/verify_v0161_source.py /path/to/tagged/pdfcraft` validates commit, local tag, clean tracked tree, workspace identity. It does not fetch sources or run automatically.
- New upstream changes include rotated-page widget flattening, forms/radio-button selection and field fixes, PDF redaction/rendering fixes, text CropBox clipping, PDF optimizer monochrome encoding and update prompt changes. Review regression fixtures before adapting Android.

## Android integration blockers

1. Fix the existing v0.15 Android build failure in PR #87 (including pinned winit / egui-winit compatibility); then separately evaluate v0.16.1 APIs. This review does **not** edit the existing ephemeral workflow or cause another failed build.
2. Port v0.16.1 on an isolated app branch without deleting existing SAF, native menus, shared-font handling, keyboard/IME, updater, red PdfC launcher/adaptive icon, PDF editing and export.
3. Public Rust/engine tests and unsigned ARM64 compile, verify package `com.artcraft.pdfcraft`, ABI, versionCode increase over installed release, updater and APK SHA256. Test PDF round-trip, signed/encrypted/annotated/XFA/form documents and graphics fidelity.
4. Owner-operated original PDFCraft permanent-key signing only in HONOR Linux Lab. Compare certificate to existing installed/public production APK. No private GitHub Actions signing, automatic release, tag or Latest change.
5. Owner exact signed APK tablet acceptance and separate explicit merge/publication approval are mandatory. Existing public PDFCraft v0.12.1-android.3 remains untouched.

This review creates only source provenance, a read-only helper and a compatibility checklist. It is not a completed upstream sync.
