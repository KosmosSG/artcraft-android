# PDFCraft 0.18.0 Android integration — published stable first

Protected user-approved baseline: `pdfcraft-v0.12.1-android.3` / `ba604057f77eb0ae45dac85914280121d0e9eb12`.
Official upstream stable: `storytold/pdfcraft` `v0.18.0` / `3936f93a1479366a951206fc6d3094680fe2d3dc`.
New branch `integration/pdfcraft-v018-stablebase-20261104` was created *directly* from that approved published stable baseline (not from experimental v0.17/v0.18 source).

Selective overlay: bounded 4 GiB / 5,000 recursive shared-font scan, guarded input and keyboard handling, GPU diagnostics, pinned native clipboard and winit compatibility, and upstream 0.18 bug/security fixes.

PROTECTED: exact published approved red PDFCraft branding assets, Android Help menu (Import Fonts / Shared fonts folder / Refresh shared fonts / Android tools dialog), no always-on Android bottom toolbar, SAF import/export, updater, keyboard controls and production signing/data. An *optional* View > Android tools panel is retained as additional access but disabled by default.

DO NOT sign with production key, publish, merge into main, change any other app or discard the published release. Build for ARM64 with disposable key only. Any compiled APK needs device tests on HONOR MagicPad 4 for full PDF edit/save, fonts, gestures, shortcuts, update checker and icon before further approval.
