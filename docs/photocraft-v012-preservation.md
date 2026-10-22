# PhotoCraft v0.12 preservation follow-up

Stacked on public PR14 head90d57fe2e1142039dad7dafa76789cf320fe2196 (successful Rust ARM64 + Java API35 compatibility run39706882021). No APK/signing/publishing is enabled.

The v0.12 draft adapter inherited older renderer setup and single modifier-state transport. Restore the GPU diagnostics/compositor integration and independent left/right Ctrl/Shift/Alt state from the previously validated private enhancement candidates. Upstream v0.12 exact commit6a2d027ee2e7ca12afd248544ed2262b0fa078dd still provides set_wgpu with caught initialization panics/CPU fallback and use_adapter_limits. Preserve software adapter/explicit CPU-mode safeguards and existing fonts/shared SAF/file/update/IME code. Retain the GPU reference MIT notice.

Local integration anchors passed; Android Rust compilation pending on this branch-specific no-signing workflow. Tablet behavior remains untested. Current exact approved Pc artwork, newer native font/update controls and touch Shortcut Pad still require reconciliation with the private passed enhancement baseline; do not claim full feature parity or release readiness. Existing android.2 remains unchanged. No versionCode allocated and no production signer allowlist changed.
