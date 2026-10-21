# DesignCraft Android candidate

Reviewed 21 October 2026. Integration branch targets the existing main branch and adds only DesignCraft files. PhotoCraft and VectorCraft refs, workflows, releases and private signing repositories are untouched.

## Provenance

- Official: storytold/designcraft v0.10.0, commit 15a2f3c8c88ae2e011e5912149ac67460ea6d949.
- Android reference: MostafaXS1/artcraft-android ac54d62d9d2d6f663295a4afd8972a7a3e79f9af.
- Existing connected repos: artcraft-android (public), photocraft-signing-private, vectorcraft-signing-private. No DesignCraft signing repo or release was found. Actions secrets are not readable through the connector; absence of a key is not proven.
- Existing main workflows are manual PhotoCraft build/verification/release workflows. None trigger on this branch push. They are preserved byte for byte.

## Implemented candidate integration (device validation pending)

- Isolated package com.artcraft.designcraft.candidate, disposable CI key, versionName 0.10.0-android.1, candidate versionCode 16800001.
- Reviewed Services.read/write/open_async/download/inbox APIs; retain the reference's asynchronous SAF bridge and error return for failed export startup.
- Native Android multi-file picker for TTF/OTF import, bounded import validation and private font catalog reload through the actual font.reload command. Existing filenames are preserved. Android system fonts remain available through child symlinks; custom fonts no longer target a read-only system-font symlink.
- Retain DesignCraft's keyboard customization and settings persistence, with the reference's Android modifier/clipboard/IME/mouse fixes.
- Optional session-only docked Undo/Redo/Save buttons invoking actual app commands.
- GPU adapter/driver diagnostics. DesignCraft v0.10.0 renders documents on CPU; Vulkan/GLES composites the interface. No claim of a fully CPU-rendered Android window or recovery from every driver fault.
- Original glass-style Dc icon, magenta-violet accent.
- Read-only CI verifies official tag resolution, APK signature, package, version and ARM64 launcher/library; no public release or production key access.

## Gates still open

- Run candidate build; inspect compile/package verification results. No tablet behavior has been tested by the assistant.
- Shared font folder selection/refresh and optional manual/startup update checks require further DesignCraft integration and tests. Importing selected files is not cross-app font sharing.
- Permanent signing: confirm whether any prior DesignCraft APK exists and verify its signing certificate before establishing a key. If none exists, create a dedicated persistent DesignCraft identity in a dedicated private signing repository, store an encrypted backup with a separately held recovery secret, record the certificate fingerprint and verify restore before publishing. Never reuse PhotoCraft's or VectorCraft's keys. No permanent key has been created yet.
- Production package com.artcraft.designcraft must use a ledger exceeding every previous released/installed versionCode; 16800001 is reserved for the separate candidate package only. Later enhancements increment android.N; upstream upgrades preserve monotonic codes independently of semver.
- Private installation testing requires a private artifact channel; this public repo's candidate artifacts are authenticated downloads, not confidential artifacts. Do not describe them as private. A dedicated private DesignCraft repository is not currently connected.
- Public publishing stays blocked until permanent certificate continuity, backup recovery, feature checks, and user tablet tests pass. No updater metadata or upstream synchronization workflow is enabled yet. Tracking must select official non-draft, non-prerelease tags, open a reviewed candidate change, preserve enhancements, and never publish without these gates.

## Tablet test checklist

Back up any test projects. Install DesignCraft Test beside other suite apps; this disposable-key package cannot serve as the production update chain. Check cold start, rotation, keyboard shortcuts/customization persistence, font import and rendering after restart, open/cancel/save/export/reopen, touch dock, GPU diagnostics, clipboard and background/resume. Report exact failures before promotion.
