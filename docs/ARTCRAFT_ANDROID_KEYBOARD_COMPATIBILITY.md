# ArtCraft Android — physical keyboard compatibility standard

Recorded from an owner-tested HONOR MagicPad 4 Android keyboard fix on 25 October 2026.
Apply to other ArtCraft Android apps **only when their own editor/shortcut model is compatible**.

## User-validated interaction
- Physical **Esc** exits active text editing; preserve the upstream tool switch
  (VectorCraft returns to Selection when its Type tool has no prior tool).
- A subsequent unmodified **Esc**, when a visible contextual bar has focus and a
  selection tool is idle, may dismiss that bar using its supported existing action.
  Avoid globally disabling contextual toolbars or intercepting Escape during a modal,
  brush action, timeline, or an active IME composition.
- **V, T, P** select their respective tools after leaving Type mode in VectorCraft;
  other apps use their own approved shortcut registries, not VectorCraft's key map.
- Return physical-keyboard focus from Android's hidden EditText to the visible
  native canvas after editing ends. Do not lose the corresponding KeyUp event.
- Keep genuine egui text fields, standard typing, Chinese IME composition, Enter,
  Ctrl/Cmd, Shift, Alt, repeat, Back, clipboard, and editing tools fully operational.

## Implementation and release policy
- Refer to VectorCraft draft PR #51 (device-tested isolated build) and production
  upgrade draft based on `release/vectorcraft-v0.14.0-android.8`.
- PhotoCraft PR #59, DesignCraft PR #60, FilmCraft PR #61, EffectCraft PR #62
  contain guarded adaptations but require full app-specific device validation.
- Preserve existing features, package identity, user-approved launcher **and in-app**
  icons, app-specific permanent signing certificates, versionCode monotonicity,
  existing GitHub Releases, and in-app update URLs.
- Do not copy disposable test APK signing identity or overwrite a production
  release with a separately installable candidate.
- Do not enable upstream sync or unattended publishing. Use reviewed source pins,
  repeatable CI, verification of the exact signed artifact, and explicit owner
  authorization for publication.
- On Android, validate: enter text, Escape, Escape again where appropriate,
  return to tool shortcuts, re-enter text, restart, Chinese IME, clipboard,
  font import, Check for Updates, save/open, launcher and graphics rendering.

This is a project acceptance policy, not a claim that every application already
implements or has passed these tests.
