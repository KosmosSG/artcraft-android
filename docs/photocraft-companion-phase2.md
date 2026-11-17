# PhotoCraft Companion — Android Phase 2 (test-only)

This is an **isolated, unsigned-for-production ARM64 candidate** built from
\`photocraft-v0.23.1-android.5\`. The original \`com.artcraft.photocraft\` APK,
published tag, production signing identity, OpenFill branch and owner-tested
features must not change.

## What Phase 2 adds

1. A user-enabled, **127.0.0.1:18492-only**, per-session-token control endpoint
   that accepts the companion JSON-lines RPC handshake.
2. \`companion.ping\` for authenticated connection/version/permissions checks.
3. Read-only \`ui.inspect\`, \`engine.commands\`, \`document.inspect\`, and
   \`session.inspect\` (latter two via \`engine.execute\`, with empty params).
4. An explicit **Allow approved undoable edits** checkbox, off by default.
   Only the empty-parameter commands \`layer.duplicate\`,
   \`image.adjustments.desaturate\`,
   \`layer.newAdjustmentLayer.blackWhite\`, \`edit.undo\`, and \`edit.redo\`
   are permitted while enabled.
5. A tablet-native B&W Film Pop button, requiring separate on-device confirmation:
   duplicate the active layer and desaturate the copy. These create two separate
   normal Undo steps; the second step can fail after the first succeeds.
6. A stdlib-only Linux Lab client and **restricted no-code JSON** macro runner.
   Native plugins, \`.pcpl\` packages, scripts, plugin marketplace, GPU inference
   and AI image generation are **not** installed or implemented.

The session token is hidden in the Android UI; tap **Copy pairing token privately**.
If a past screenshot exposed a token, disable and re-enable the bridge to rotate it.

## Tablet and Linux Lab smoke test

1. Install the **new isolated candidate** on the tablet and open PhotoCraft.
2. Open **Pc → AI Tools → PhotoCraft Companion** and enable the local bridge.
3. Copy the **new** one-session token. Do not paste it into a GitHub issue, screenshot
   or command-line argument.
4. In Linux Lab on the *same tablet*, obtain
   \`tools/photocraft_companion_linuxlab.py\` (Python 3, standard library only).
5. Run \`python3 photocraft_companion_linuxlab.py --ping\`. The script prompts for
   the hidden token; optionally use the local \`PHOTOCRAFT_COMPANION_TOKEN\`
   environment variable, but do not save it in shell history or scripts.
6. Open a PhotoCraft document, then run
   \`python3 photocraft_companion_linuxlab.py --inspect\` to inspect
   session/document state. This must not edit pixels.
7. To test the supported plugin, use
   \`python3 photocraft_companion_linuxlab.py --dry-run black_white.json\`.
   Review the two steps before allowing any edits.
8. **Optional edit test, on a throwaway document:** enable *Allow approved
   undoable edits* on the tablet, then run
   \`python3 photocraft_companion_linuxlab.py --run black_white.json --confirm-edits\`.
   Use \`--undo --confirm-edits\` twice to revert both steps. Alternatively run
   the B&W Film Pop macro through the Android dialog with its separate checkbox.
9. Disable the Companion bridge after testing.

If \`127.0.0.1:18492\` is not reachable from Linux Lab, the environment may
have an isolated network namespace. **Do not** switch PhotoCraft to public
listening or expose its token. Report the exact error so the integration can be
adapted safely.

## Security/integration constraints

- All requests are authenticated before dispatch. The server binds only to
  tablet loopback and rejects unapproved RPC methods/commands/params.
- No \`app.save\`, \`app.open\`, synthetic keyboard/pointer, shell/plugin
  execution, screenshots, arbitrary commands, remote AI, or file upload.
- The read-only probe never generates output images and is **not** proof
  that OpenFill's Fill, Remove Object, Generative Expand or Create work.
- A valid network handshake or mocked desktop contract test is **not**
  a device integration test. Report pass/fail from the physical tablet.
- The desktop [PhotoCraft Companion](https://github.com/kobaltgit/photocraft-companion)
  uses a compatible RPC format but its native desktop program is not bundled.
  The example no-code B&W macro follows the upstream plugin's commands;
  upstream Companion is MIT licensed. Credits stay with its author.

## Build acceptance

Use the GitHub Actions workflow
\`.github/workflows/photocraft-companion-android-arm64-test.yml\` only on the
\`feature/photocraft-v0231-companion-android-20261117\` development branch.
Require completed Python offline tests, ABI=arm64-v8a, a **separate candidate
package**, \`apksigner verify\`, and a non-production certificate hash.
Never merge, sign with production keys, or publish a release.
