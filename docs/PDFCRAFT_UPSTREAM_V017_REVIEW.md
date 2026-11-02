# PDFCraft official v0.17.0 — isolated source provenance and Android integration review (2026-11-02)

**Scope:** Review-only staging stacked on draft PR #108 (which itself stacks on the failing v0.15 candidate PR #87). This change does not port upstream source, trigger builds, sign APKs, merge, tag or publish.

## Verified upstream identity
- Official stable release: https://github.com/storytold/pdfcraft/releases/tag/v0.17.0 (published 2026-11-01 19:33:10 UTC; neither draft nor prerelease).
- Direct Git tag `refs/tags/v0.17.0` resolves to commit `7d78f3e14474b978be014715e0cc64895d77025a`; `Cargo.toml` workspace version is `0.17.0`, Rust MSRV `1.95`, repository `storytold/pdfcraft`.
- Provenance check: `python3 tools/pdfcraft/verify_v017_source.py /path/to/clean/tagged/pdfcraft`. This helper is read-only and must be run against a separately acquired checkout; it is not a substitute for a source diff or build.
- Notable upstream changes: shared craft-update result dialog; rewrite unsigned documents fully after page deletion; image/text editing UI changes; XFA placement rotation; mismatched-mask resilience; JBIG2 arithmetic overflow fix; licensing validation for bundled assets. Review these against PDF editing, render/export, security, and updater behavior.

## Android integration blockers and release gates
1. Resolve PR #87's pinned winit / egui-winit ARM64 build failure first; do not repeat known quota-failing jobs. Re-evaluate Android APIs and dependencies for v0.17.0 on an isolated integration branch.
2. Preserve current PDFCraft Android-only SAF open/save, imported fonts, physical keyboard/IME, menus, approved red PdfC launcher/adaptive assets, updater's GitHub APK channel, and PDF annotation/form/export behavior. Do not import desktop self-update installation.
3. Run dependency, PDF engine, form/redaction/annotation/render, Android adapter and integration regressions; compile a **public unsigned ARM64** candidate only when compatible. Verify APK SHA-256, `com.artcraft.pdfcraft`, ABI, monotonic versionCode, updater/assets and exact build provenance.
4. Owner alone signs with the **original permanent PDFCraft keystore on HONOR Linux Lab**; verify certificate continuity against installed production. No private GitHub Actions signing, new signing key, release tag, auto-merge, or Latest flag changes.
5. Exact signed APK physical-device acceptance and separate explicit owner approval are mandatory before any merge or publication. Existing PDFCraft v0.12.1-android.3 public APK stays untouched.

This PR is **not** an upstream-synchronized Android source tree or an installable APK. No production gate is claimed passed by this provenance lock.
