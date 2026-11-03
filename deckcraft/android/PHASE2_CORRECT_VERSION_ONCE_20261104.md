OWNER_APPROVES_V0150_ANDROID1_ONE_TEST_20261104

Owner requested fully unattended progress until a disposable-key signed ARM64 DeckCraft test APK exists.
Requested exact versionName: 0.15.0-android.1, versionCode 100000022, package com.artcraft.deckcraft.
Official upstream: storytold/deckcraft v0.15.0 pinned 3e178d8f5a59c787a6a53a7ed0f052b3e4a1489f.
Protected baseline: deckcraft-v0.14.1-android.17, commit 54fbdd4088d0e835c7642fafe039a72c3993be72.

This is a single-use Actions build approval for source regression testing and ARM64
APK packaging with newly generated DISPOSABLE test signing key only. It intentionally
supersedes already running 0.15.0-android.18-test build #41682410373 with GitHub's
cancel-in-progress concurrency setting to conserve Actions quota.

No permanent signing certificate access, no GitHub releases or tags, no merges
or modification of published Android.17, and no other app modifications.
After this run queues, remove the one-shot push workflow trigger, leaving manual
approval for any later GitHub test runs.
