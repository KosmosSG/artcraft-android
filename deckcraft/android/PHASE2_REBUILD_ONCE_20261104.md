AUTHORIZED_PHASE2_PACKAGING_REPAIR_REBUILD_ONCE

Owner authorization: 2026-11-04 (Malaysia time).
Purpose: rerun DeckCraft upstream v0.15.0 testing after verified
Android packaging metadata regression in run 41675943962.

Allowed actions: rerun patch checks, Rust tests, and compile **one**
ARM64 APK with fresh disposable test-signing key; upload test APKs.
Blocked: original certificate access, production signing, publishing,
altering Android.17 release, modifying other ArtCraft applications.

Root cause: builder-side approved branding hook overrode Android
Gradle versionName/versionCode (0.14.1-android.17, 100000021).
Fix: override metadata only in ephemeral builder manifest and
android_project.py to test version 0.15.0-android.18-test, 100000022.
Original Dk icon asset checksums and released branding manifest protected.

This file is a one-time workflow trigger. The trigger must be removed
immediately after the run is queued. Keep the file as audit evidence.
