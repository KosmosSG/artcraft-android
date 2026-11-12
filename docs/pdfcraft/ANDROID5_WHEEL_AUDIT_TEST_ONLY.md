# PDFCraft Android.5 test candidate

Separate com.artcraft.pdfcraft.v020test5 package, disposable signing. No production signing, merge, release or Google appeal.

Opt-in Pc > Stylus Wheel follows VectorCraft's Magic-Pencil 4s button integration. Hover then single press opens; hover highlights; tip selects; double press selects Eraser. Passive stylus-only hover cursor never consumes Android input. Hardware must supply hover events. Eight customizable slots, persisted size 75–150%, opacity 40–100%, live preview and reset. Exact launcher Pc art, #FB0E00 round centre, mark 36 x 22.5 points (10% below PhotoCraft's 40 x 25).

Reported production APK SHA-256: fa65eb8d63cf106d048da402a7966e93814122cea59da9f66e6153e9d4128bda. Archive/metadata inspection found normal ZIP structure, ARM64, one Activity, no services/receivers/providers. Existing storage permissions serve current file workflows and are retained. This does not establish Google's warning cause or certify malware absence.

Updater fixes: mandatory checksum; hash while copying external download into private snapshot; check exact version, newer version code, package and signer; stream the same verified private bytes into a sealed PackageInstaller session requiring system confirmation. Nonce/session-scoped callback. Existing pinned dependencies preserved; comprehensive dependency vulnerability scanning is not claimed.

CI covers adapter generation/idempotence, keyboard/input/OCR regressions, wheel logic, snapshot tamper/mutation checks, ARM64 build, branding and metadata. Owner hardware checks remain necessary for hover/contact/exit, all size settings, persistence, ordinary drawing/navigation, and installer confirmation/cancellation on MagicOS 10. No Play Protect clearance claimed.
