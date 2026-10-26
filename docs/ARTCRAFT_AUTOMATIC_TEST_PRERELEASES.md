# ArtCraft Android — automatic testing Pre-releases

Status: enabled for existing owner-controlled candidate workflows via
[`.github/workflows/auto-publish-test-prereleases.yml`](../.github/workflows/auto-publish-test-prereleases.yml).

## What happens

When a **new** successful ArtCraft candidate workflow completes, the central
publisher on `main` downloads the retained GitHub Actions APK artifact. It
checks the originating workflow, repository, actor, source commit, APK package,
versionName/versionCode, ARM64 native libraries, APK signature, SHA-256 and
any supplied verification metadata. The candidate bytes are copied unchanged:
the publisher does **not** rebuild or re-sign the APK.

For an APK with the standard `com.artcraft.<app>` package, the signer must
match the latest published Stable APK and the versionCode must be higher. A
first production-signed release still needs independent owner approval.
Temporary test-only APKs are eligible only if their package is explicitly
separated from the Stable app (for example, `.fonttest`), preventing an
incompatible signing key from replacing the installed version.

Eligible candidates get a **GitHub Pre-release** with a unique per-run
`<app>-v<version>-preview.<run-id>` tag, an APK, SHA256SUMS and
`test-verification.json`. Stable releases and signing credentials are not
modified. The new test release does not become GitHub's latest Stable release.

Failed, cancelled, skipped, unsigned, incompatible, missing or ambiguous
candidates do **not** become Pre-releases. An artifact with the same
versionCode as the existing Stable APK is not an installable update and is
skipped. These are intentional safety gates.

## Scope

The workflow listens to the existing eligible candidate builders for
PhotoCraft, VectorCraft, DesignCraft, EffectCraft, FilmCraft, GridCraft,
DeckCraft, LightCraft, WordCraft and PDFCraft. SoundCraft, CADCraft and
FigCraft currently need compatible candidate-producing workflows and explicit
review before their workflow names can be added. Other newly introduced
candidate workflow names must likewise be added to the central allow-list.

The automatic publisher is prospective: it starts when a candidate workflow
*next completes successfully*. Older Actions artifacts are not retroactively
released. A manual `workflow_dispatch` with `candidate_run_id` is also
available for an authorized one-off retry.

## Owner acceptance and Stable channel

Pre-release means **ready for owner device testing**, not approved Stable.
After testing on the HONOR MagicPad 4, the owner must separately approve a
specific production-signed APK before it can be promoted to Stable. That
promotion requires the existing per-app release workflow and its signing,
version, test and provenance checks.

For a test-only package, keep the installed Stable app and its data.
Test-only preview APKs are not guaranteed to upgrade the Stable app.

## Validation

The guarded publisher runs a GitHub push-time self-test that compiles its
embedded verification scripts and confirms `--prerelease` and
`--latest=false` are present. Passing this test checks the workflow's
configuration but does not substitute for observing the first end-to-end
candidate-triggered Pre-release.
