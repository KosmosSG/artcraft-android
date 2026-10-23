# PDFCraft Android v0.13.0-android.1 — isolated update-checker fix

Status: **candidate only; not a signed upgrade and not a public release**. This branch starts from the previously published red-icon fix (`fix/pdfcraft-icon-android2`) and keeps the existing PDFCraft-only Android adapter and icon. The upstream input is **storytold/pdfcraft v0.13.0**, pinned to commit `53199fb4fa36f3c95b539add6218c57aeb2f823c`. The upstream v0.13.0 change is primarily macOS PDF association recovery; Android compatibility must still be established by the candidate build.

## Fix and rationale

The GitHub release feed serves **all** ArtCraft app releases. Previous PDFCraft update checking read only 50 entries, which can eventually hide published PDFCraft APKs. The Android checker now reads up to three 100-entry pages with per-page 2 MiB size caps, 8-second connect/read timeouts, HTTP response validation, and a disconnect on each page. It continues to reject draft, prerelease, non-PDFCraft, malformed-version, wrong-URL or missing-APK releases, and never provides downgrade links. When the 300-release limit is reached, it does not claim full release-history coverage. The updater **never downloads or installs** an APK automatically.

## Version and safety guards

- Candidate Android versionName: `0.13.0-android.1`; build metadata must show versionCode `16780544` (higher than v0.12.1 `16780289`).
- Package: `com.artcraft.pdfcraft`; ARM64 `arm64-v8a` only; owner-approved red PdfC launcher retained.
- The push-triggered workflow uses a **disposable build keystore** solely to compile and check an artifact. It is not an update to the permanently signed public APK and **must not be installed over the existing app**.
- The PDFCraft permanent key and encrypted offline backup are not touched. Do not borrow another app's key or rotate PDFCraft's identity.
- No automatic upstream synchronization, signing, tagging, or GitHub Release publishing.

## Validation requirements before a signed release

1. GitHub Actions candidate workflow succeeds on the exact pinned commit: tests, Android adapter generation, version, ABI, launcher assets, package ID and ephemeral certificate. Check the build job logs and retained artifact.
2. Manually review any API changes and perform PDF open/edit/save/save-as/export round-trip tests. Include annotated, embedded-font, CJK/RTL, encrypted, form-filled and digitally signed documents. A modified signed PDF may invalidate an existing signature; do not imply otherwise.
3. On the HONOR MagicPad 4, test document picker, cancel, duplicate names, persistent shared font folder, font picker feedback, keyboard/IME, touch, resizing and startup/manual update checks. Do not try to update an installed production build with the disposable-key candidate.
4. Prepare a **separate manual** v0.13.0 signing workflow after the candidate has passed. Check the exact candidate SHA and run, input release fingerprint against existing production cert, old/new versionCode ordering, signed/unsigned payload equivalence, signing output and signed APK retention before creating any public tag. Do not overwrite old releases.
5. Preserve attribution and review upstream branding licence for any public modified build.

Production source remains the already released `pdfcraft-v0.12.1-android.1` until a newer version is verified, signed with the same identity, and deliberately published.
