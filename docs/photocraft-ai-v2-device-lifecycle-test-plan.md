# PhotoCraft AI PR #93 — non-destructive V2 device lifecycle acceptance plan

**Current accepted production baseline (1 November 2026):** PhotoCraft `0.14.0-android.4`, package `com.artcraft.photocraft`, versionCode `16790007`, V2 signer SHA-256 `EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936`. The existing public release is **stable and must remain unchanged**.

**Rejected test candidate:** `0.14.0-android.5` (code `16790008`) failed the owner's Ctrl+W test on HONOR MagicPad 4. **Do not reinstall, rebuild, re-sign, promote, or distribute android.5** to repeat this test. Its runtime root cause is unproven; passing source parity and CI checks are not device acceptance.

**Scope:** Manual, non-destructive acceptance for a *future separately authorized* candidate. This document records **procedures only**, not tests performed or release readiness. PR #93 remains DRAFT. The owner must separately approve any new APK/device installation and any eventual publication.

## Safe preparation

- Back up the current PhotoCraft documents and app-private data using the application's supported export/backup flow. Keep at least one separate copy of a disposable test project and a non-sensitive PNG.
- For baseline keyboard observations, use the **already installed, working android.4**; do not uninstall, clear data, downgrade, or replace it. Do not install an experimental APK just to follow this plan.
- Start the local U2NetP CPU sidecar manually from the Linux Lab desktop shortcut when needed. Keep its session token private; do not put it in logs, screenshots, GitHub comments, or test records. No root, ComfyUI/GPU changes, model redistribution, or public network binding.
- If an owner-approved future update is tested, first independently verify the package `com.artcraft.photocraft`, a versionCode **greater than 16790007**, and the **same V2 signing certificate**. These checks establish install compatibility, **not** data preservation.

## Accepted android.4 Ctrl+W reference (no new APK)

| Observation | Safe procedure on current android.4 | Expected outcome |
| --- | --- | --- |
| Ordinary document | Open a saved disposable document, ensure no text cell or dialog is editing, press Ctrl+W once | Existing close/save decision flow appears and remains keyboard-responsive |
| Unsaved document | Change the disposable document, press Ctrl+W, then exercise D / C / S on separate repetitions | Discard, Cancel and Save follow the accepted android.4 behavior; no input leaks to the canvas while the dialog is open |
| Text editing focus | Enter text on a disposable layer, exit typing with Esc, then press Ctrl+W | Text focus exits before document-close handling; no silent loss of unrelated document edits |
| Dialog repetition | Cancel the first close dialog, press Ctrl+W again, and test the dialog shortcuts | Repeated invocations remain responsive; no stale modal state |

Record the exact input device (hardware keyboard or external keyboard), keyboard layout, focus state, app version, and result. Do **not** claim android.5's regression is fixed from these android.4 reference observations. For a future explicitly approved candidate, compare the same four cases on the same device, using only expendable data.

## Local U2NetP lifecycle scenarios (future owner acceptance)

| Scenario | Safe procedure | Expected result |
| --- | --- | --- |
| Restart sidecar | Complete one consented request, stop Linux Lab sidecar, restart manually, then enter the new token | Old token is rejected; new per-image consent works; original image remains unchanged |
| Cancel/close | On a duplicated image, start removal and cancel/close its dialog before completion | No late layer is inserted; the CPU subprocess may finish independently |
| App focus change | Switch PhotoCraft to Android home and back during a test request | No stale result is inserted into a different or closed document |
| Linux Lab suspend/resume | Save the disposable project, lock/unlock or suspend/resume once, then retry with fresh consent | Failure is bounded and recoverable; no project corruption |
| Repeated requests | Perform several sequential consented operations, Undo/Redo and Save/Open | Each accepted result is one editable layer, with no stale insertion or persistent image files |
| Sidecar unavailable | Stop the service, attempt a request on disposable content | Clear connection failure and no document change |

Capture pass/fail and a short reproduction with Android/MagicOS version, app versionCode, keyboard/focus context and whether Linux Lab was foregrounded. Never include tokens or private images.

## Signing and data-preservation gates

- **Old signer versus V2:** The historical `45933A88…` certificate cannot update an installed V2 `EDDA8AB3…` app in place. Migration between those signing lines requires separately planned backup/restore and may lose app data. Never describe it as a seamless upgrade.
- **V2-to-V2:** Matching package, matching V2 signer and increasing versionCode are necessary but insufficient. A future owner-approved candidate must also pass an **in-place install over current V2** with document, custom-font/SAF access, preferences, AI opt-in state, shortcuts and Undo/Redo preserved. No such new candidate is approved now.
- **Rights:** The local model weights are not bundled. The current personal/noncommercial assessment does not establish commercial clearance; consult `docs/photocraft-ai-model-rights-review.md` and retain accurate notices.
- **Publication:** Only update `docs/photocraft-ai-v2-stable-checklist.json` after genuine recorded acceptance. Green CI, historical preview tests and this written plan cannot substitute for hardware verification or explicit final publication approval.
