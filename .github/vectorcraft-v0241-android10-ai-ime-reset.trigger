VectorCraft 0.24.1-android.10 TEST ONLY — fix imported Illustrator .ai typing and Ctrl+Q/relaunch IME lifecycle.
User device diagnostics from Android.9: reset_requested=42, java ime_resets=0, reset_matched=0, stale_ime_rejected=235; tool_text_calls=182 and edit_accepted=182.
New fix: restore Storytold editor-owned IMEOutput.reset_request forwarding through MostafaXS1 v0.5.0 builder's egui-winit override; patch vendored Android winit/native-activity forwarding so Java vcResetIme actually restarts connection and queues matching 'r' ID.
DO NOT bypass stale guards, synthesize acknowledgements, clear data or change .ai data. Preserve working two-finger pan direction and current cursor implementation unchanged (the synthetic arrow remains a known unresolved issue).
Build separate com.artcraft.vectorcraft.candidate_v0241a10typing ARM64 APK, launcher VectorCraft AI Typing Test, versionCode 16784917, disposable signing only.
Test on HONOR MagicPad 4: fresh document typing; imported .ai Type tool; .ai->new document; close/reopen; Ctrl+Q/relaunch 10x; real reset_requested/java ime_resets/reset_matched and stale input counters. Device PASS not yet claimed.
No merge, release, published APK overwrite or permanent production signing.
