# PhotoCraft V2: consolidate the two previews into one future stable release

**Prepared:** 1 November 2026. **Decision status:** proposed plan only; NOT a merged PR, signed APK or stable publication.

## Why two PhotoCraft APKs are public

| Existing public **prerelease** | Android identity | AI enabled | Purpose |
| --- | --- | --- | --- |
| [Regular PhotoCraft V2 0.14.1](https://github.com/KosmosSG/artcraft-android/releases/tag/photocraft-v0.14.1-v2-preview) | `com.artcraft.photocraft`, `versionCode 16780801`; new V2 permanent certificate | No | Historical regular editing V2 proof based on an earlier pinned upstream baseline. |
| [PhotoCraft AI V2 0.14.0-android.2](https://github.com/KosmosSG/artcraft-android/releases/tag/photocraft-v0.14.0-android.2-ai-v2-preview) | `com.artcraft.photocraft`, `versionCode 16790005`; **same** V2 permanent certificate | Yes: locally hosted, opt-in U2NetP background removal | Owner-tested AI feature-preview baseline. |

Despite its lower *display versionName*, **AI V2 is the higher Android versionCode**. Both share the same package name and cannot install side-by-side. Do not tell AI V2 users to install regular V2 0.14.1 as an upgrade: it would be an Android downgrade. Do not rename/re-sign/overwrite either historical preview release to hide this distinction.

## Single stable release recommendation

1. Use the **PR #93 AI source** and preserve all owner-tested photo editing, file Open/Save, custom/system fonts, keyboard/ESC, Undo/Redo and in-app update behavior. Keep unimplemented generative tools disabled. Preserve the model-free APK and opt-in tablet-local CPU sidecar architecture.
2. Review the exact upstream PhotoCraft version actually compiled. Apply the suite's official `MAJOR.MINOR.PATCH-android.N` naming standard; for unchanged reviewed upstream `v0.14.0`, a **candidate** name could be `PhotoCraft v0.14.0-android.3`. This is a **proposal, not an assigned version or approved tag**. If upstream source advances, reconsider the series and revision. Never infer source version from the previous regular V2 preview title.
3. The final Android `versionCode` must be **greater than 16790005**, the installed AI V2 preview, and greater than any other published production/V2 code. Validate this from the **actual signed APK**, not GitHub tag ordering or versionName. Do not assign a code without checking the actual build config first.
4. Sign only with the **same permanent PhotoCraft V2 key** (certificate SHA-256 `EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936`) stored encrypted in `KosmosSG/photocraft-signing-private`. Never rotate or expose it.
5. Before shipping: run the fail-closed V2 signed-APK comparison against the immutable public **AI V2 0.14.0-android.2** baseline with `tools/photocraft_ai_v2_upgrade_gate.py`, check the actual candidate archive for ARM64/no model weights, and verify old-to-new bytes and updater behavior. Existing `tools/photocraft_ai_candidate_compatibility.py` is intentionally scoped to the **original-key production** path; it must **not** be silently repurposed for the V2 key.
6. On a spare or expendable **V2-signed** app installation, verify a real **V2 AI preview → candidate** in-place Android upgrade retains project, fonts, preferences and local content. Avoid downgrading or uninstalling the owner's working AI app simply to prove upgrade acceptance.
7. Explain **original-key-to-V2 migration** separately: an original-signed PhotoCraft installation **cannot** update in place to this V2 series and needs a data backup before uninstall/reinstall. The exact original signer differs.
8. Gate stable/Latest release on U2NetP model/dataset rights review, actual tablet lifecycle/stress tests, device upgrade and data retention acceptance, verified update channel semantics, and explicit owner stable-publication approval. **Do not merge draft PR #93 or mark anything Latest based only on an offline CI green run.**

## Compatibility ordering for support

- **Original-key PhotoCraft 0.14.0-android.1 → V2 AI preview:** signing identity mismatch. Back up and migrate; Android in-place update cannot work.
- **Regular V2 0.14.1 → AI V2 0.14.0-android.2:** same signer/package, increasing Android versionCode; identity gate passed. Physical data retention test was **not** independently documented.
- **AI V2 0.14.0-android.2 → Regular V2 0.14.1:** versionCode decreases, **not an upgrade**.
- **AI V2 0.14.0-android.2 → future single stable V2:** must retain V2 signer, increase code and pass actual device acceptance before publication.

**Current action:** leave both existing previews public for transparency and historical download compatibility; publish only a new, separately verified, owner-approved unified PhotoCraft stable candidate when all gates are satisfied.
