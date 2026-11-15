VectorCraft v0.24.1-android.9 native glass pan CURSOR ONLY ARM64 TEST.
Exact published base: vectorcraft-v0.24.1-android.9 tag 9beff78fd24b59e806f65424f9ee6443943d2901.
Working glass pan direction commit: 60fd9d797f9cf282db609fa5ddde8d73522cc319, run 43676135324 (confirmed by owner).
Fix unwanted painted/OS mouse arrow between touchscreen finger contacts by source-tagged suppression during native glass pan; retain wheel target, sign, pointer input and stylus hover.
Test-only separate candidate com.artcraft.vectorcraft.candidate_v0241a9cursor and launcher 'VectorCraft Pan Cursor Test', versionCode 16784915.
No typing/IME or .ai import changes, no Android.10 reset transport, no production signing, merge, publication, or release asset replacement.
Retest: corrected staged wheel-provenance regression assertion in commit 81d1ccda911757ea0a06efb8f3d11f40b4ffd992; exact native glass cursor change only. Disposable ARM64 test APK; no permanent signing/release.

Native pointer v2 test: Android TYPE_NULL arrow suppression, forced by source-tagged glass-pan flag; real pointer recovery preserved. Unique candidate_v0241a9cursor2 package, no changes to stable or typing/IME. GitHub Actions test only.
