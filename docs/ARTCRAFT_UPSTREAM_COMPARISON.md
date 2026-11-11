# ArtCraft Suite upstream comparison (read-only)

Workflow: `.github/workflows/artcraft-upstream-comparison.yml`.
Script: `tools/artcraft_upstream_compare.py`.

- Weekly schedule: Mondays at 09:19 Malaysia time (01:19 UTC); also supports manual Run workflow.
- Reads the latest *official stable* Storytold release, current upstream `main`, and the suite's published Android releases for ten apps.
- Separately identifies the latest published Android version (including previews) from the protected stable Android release with an APK asset.
- Reports missing Android stable releases, renamed prereleases, official release gaps, commit ancestry, recent upstream main commits, and missing APK assets.
- Publishes detailed Markdown/JSON as GitHub Actions artifacts (30-day retention) and a run summary.
- Does not use signing keys, write GitHub content, create releases, trigger other workflows, checkout upstream code, build APKs, or run Android SDK/Rust.
- Treats API errors as incomplete reports; never reports a failed lookup as 'no update'.
- The report only inspects release asset metadata, not certificate continuity or on-device Android behavior.

To run: GitHub > Actions > ArtCraft Suite upstream vs published Android (READ ONLY) > Run workflow.
Do not use this report as authorization to merge, build, permanently sign, or publish an Android APK.
