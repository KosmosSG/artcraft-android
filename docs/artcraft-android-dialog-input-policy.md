# ArtCraft Android Suite — Unsaved-changes keyboard compatibility policy

**Approved 2026-11-04 from WordCraft device feedback.** Apply to other apps only where they have a compatible unsaved-changes confirmation; preserve each working release baseline and test before promotion.

- While the Save / Don't Save / Cancel (D/S/C) dialog is open, **Esc means Cancel**: close the dialog and keep the document and unsaved edits intact.
- Physical **D** = Don't Save, **S** = Save, **C** = Cancel. Handle keys only while the dialog is active; no shortcut should type into the underlying document. Touch buttons must keep working.
- **Ctrl+Q** requests normal exit, asking D/S/C first for unsaved work; never force-quit or silently discard edits.
- Preserve typing, Esc outside dialogs, Ctrl+S, clipboard, IME/Gboard focus and app-specific shortcuts. Intercept alternate Android InputConnection routes only where necessary.
- Use disposable signing for testing; leave permanent keys, released APKs and stable data untouched until owner approval. Do not copy WordCraft code mechanically into incompatible applications.
