VectorCraft v0.21.0-android.12 guarded TEMP-SIGNED ARM64 TEST ONLY.
Device report: native 64 vs egui 36 keyboard receipts, hidden IME active after editing, V/T and S/C/D fail, transient black startup, menus not as smooth as PhotoCraft.
Candidate source: d51be7ada0be8a84c4a44e85e39d64b9806ec3aa.
Fix only: per-mode Android physical-key fallback, branded non-black startup cover, popup-only frame-paced menu scroll. All upstream and Android stable features preserved.
Cheap full overlay + behavioral test gates before ARM64 build. Package com.artcraft.vectorcraft.test, disposable key; NEVER sign with original keys or publish.
