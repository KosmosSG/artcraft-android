VectorCraft v0.24.1-android.11 disposable ARM64 test trigger, based strictly on user-confirmed Android.10 AI typing success.

TEST ONLY: stylus wheel enabled by default on fresh candidate (explicit Off persists); Magic-Pencil 4s hovering side-button state and physical key fallback; physical keyboard Ctrl+Z Undo and Ctrl+Shift+Z Redo through document history.

Preserve Android.10 .ai typing IME reset transport, Ctrl+Q relaunch, Android.9 two-finger panning, approved Vc UI, fonts and in-app updater.

Separate package com.artcraft.vectorcraft.candidate_v0241a11wheelkeys, version 0.24.1-android.11 code 16784918. Disposable signing only, no merge, no production signing, no publishing or overwriting releases.

Need HONOR MagicPad 4 device testing after artifacts: hover button without contact, 8-slot wheel, Undo and Redo on document and imported .ai; Ctrl+Q 10x; typing in imported .ai, pan and pointer.

Android.11 isolated run #2: fix prior run 43775841967 Step 11 missing staged Rust keyboard fallback anchor. Keep direct Android.11 Java-to-Rust history queue (mode + poll) and native Ctrl+Z/Shift+Z handling, plus passive hover side-button; preserve working Android.10 .ai typing unchanged. Disposable ARM64 only, no publishing or permanent signing.

Android.11 isolated run #3: fix moved Ctrl+Q source-comment anchor by injecting Redo immediately before the unique existing Android Ctrl+Z handler. Confirm original Android.10 imported .ai typing and the existing Android.5 opt-in verified in-app update downloader/PackageInstaller are preserved. Disposable ARM64 test only; no merge, release or production signing.
