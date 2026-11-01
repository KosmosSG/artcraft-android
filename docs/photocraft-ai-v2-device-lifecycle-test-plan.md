# PhotoCraft AI V2 — device lifecycle acceptance protocol

**Target:** HONOR MagicPad 4 ARM64; PhotoCraft AI `0.14.0-android.2` signed with permanent V2 certificate.  
**Purpose:** extend the owner's already-passed seven feature checks. This is a **manual, non-destructive acceptance plan**, not evidence that tests have been run.

## Before testing

- Save and make a separate backup of an expendable test project and any app-private data. Test with a non-sensitive image only; do not share private photos, API bearer tokens, or project files in CI logs.
- Work with the **already installed AI V2 preview** and existing Linux Lab U2NetP environment. Do not uninstall PhotoCraft, clear app data, rotate signing keys, reinstall model weights, or downgrade the application merely for these tests.
- Start the U2NetP sidecar manually from the installed Linux Lab desktop shortcut. The token changes each time the server restarts; keep it private. No ComfyUI/GPU/root changes.

## Safe lifecycle checks

| Scenario | Procedure | Expected result |
| --- | --- | --- |
| Restart service | Complete one background-removal operation, close the Linux Lab sidecar, then reopen it and reconnect with its **new** token. | A new request succeeds; an old token is not silently accepted. No unexpected edits to the original document. |
| Cancel midway | On a duplicated image, begin one removal and cancel/close the AI dialog during processing. | No result layer is inserted after cancellation. The sidecar may continue the already started CPU operation (known limitation); the application must not apply a stale result. |
| Android focus change | Keep Linux Lab available and switch between PhotoCraft, Android home and back during a test request. | UI remains responsive; a resumed or cancelled job never inserts into a different/closed document. |
| Suspend and resume | With the test project saved, lock/unlock screen or suspend/resume Linux Lab once, then retry with a new authenticated request if necessary. | Failure or timeout is surfaced clearly without document corruption; a later valid request can succeed. Actual Linux Lab behavior depends on the OS lifecycle. |
| Repeated usage | Perform several consented test requests sequentially, with Undo/Redo and Save/Open between them. | Each accepted result is one editable new layer; no stale insertion, lockout or persistent temporary images. |
| Service unavailable | Stop the sidecar, then try the feature using a disposable test image. | Bounded, actionable connection error; no change to the document; app and shortcuts remain usable. |

Record pass/fail with the tested app version, Android version, whether Linux Lab was visible/floating, and any safe reproducible error text. Do **not** include session bearer tokens or screenshots of private project content.

## Signing migration versus V2 upgrade

- An APK signed with the old PhotoCraft production certificate **cannot** be updated in place to V2. Keep that warning in the download page and release notes.
- GitHub CI verified the **same V2 certificate** and higher versionCode for an update from regular V2 `0.14.1` (code `16780801`) to AI V2 `0.14.0-android.2` (code `16790005`). **This is not proof of a data-preserving device update.**
- Do NOT downgrade your current AI V2 installation simply to test regular-V2-to-AI-V2 migration; this could require destructive uninstallation. The preferred upgrade acceptance test is on a secondary test device/emulator with expendable data, or in a separately planned, fully backed-up migration.

## Release decision

Completed test records can support the `real_device_sidecar_lifecycle_stress` checklist entry in `docs/photocraft-ai-v2-stable-checklist.json`. Only update its status after the real-device acceptance evidence is documented and reviewed. Model/dataset rights and explicit stable-release approval remain separate gates; one pass cannot substitute for the other.
