"""VectorCraft Android.13: preserve ordered IME reset fences across document switches.

Android.9 introduced vcDocumentChanged() and a native reset-key deletion,
even though upstream egui still owns an outstanding ImeResetId. When SAF
import or tab closure crosses this boundary, discarding BOTH the Java
completion and the opaque Rust matcher can strand the editor in Stale/blocked.

Fix only the handoff: discard old content events on document change while
retaining reset-completion controls; retain the exact editor-owned reset ID
until a matching completion, replacement, or retirement by the upstream
reset state machine. Do not manufacture completions, lift stale-input guards,
disable recovery, clear preferences, or touch document payloads.
"""
from pathlib import Path
import sys


def replace_exact(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Android.13 {label}: expected one reviewed anchor, found {count}")
    return source.replace(old, new, 1)


def replace_in_method(source: str, begin: str, end: str,
                      old: str, new: str, label: str) -> str:
    a = source.index(begin)
    b = source.index(end, a + len(begin))
    return source[:a] + replace_exact(source[a:b], old, new, label) + source[b:]


def patch(root: Path) -> None:
    adapter = root / "adapters/vectorcraft"
    java_path = adapter / "java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    rust_path = adapter / "src/lib.rs"
    java = java_path.read_text()
    rust = rust_path.read_text()

    # The per-Activity rebind flag added in Android.12 must be safe when a
    # native renderer initiates an SAF/document transition off the UI thread.
    java = replace_exact(java,
        "    private boolean vcImeNeedsRebind = true;",
        "    private volatile boolean vcImeNeedsRebind = true;",
        "activity-local rebind visibility")

    java = replace_in_method(java,
        "    public void vcDocumentChanged() {",
        "    public boolean vcStylusHoverActive() {",
        "        imeWanted = false;\n        imeEvents.clear();",
        """        imeWanted = false;
        vcImeNeedsRebind = true;
        // Old text/preedit belongs to the closed or imported document.
        // Reset-completion controls are not text and MUST reach the
        // opaque request-id matcher; upstream rejects superseded IDs.
        imeEvents.removeIf(event -> !event.startsWith("r"));
        Log.i(TAG, "VC_IME13 document_switch preserved_reset_controls");""",
        "document-change acknowledgement retention")

    rust = replace_exact(rust,
        '''            let reset_key = egui::Id::unique(("vc-android-ime-reset", ctx.viewport_id()));
            ctx.data_mut(|data| data.remove_temp::<Option<egui::ImeResetId>>(reset_key));''',
        '''            // Do not erase the editor's outstanding opaque IME reset ID.
            // The Java queue keeps its completed reset controls; the bridge
            // compares the exact serial/viewport and upstream complete()
            // additionally verifies live context, target and destination.
            // A newer request replaces this slot through request_guard().''',
        "native document-change fence preservation")

    # Existing bridge and upstream guards remain the authority: this fix
    # only prevents their ordered acknowledgements from being orphaned.
    assert 'event -> !event.startsWith("r")' in java
    assert 'vcImeNeedsRebind = true;' in java
    assert 'ctx.data_mut(|data| data.remove_temp::<Option<egui::ImeResetId>>(reset_key));' not in rust
    assert 'self.ime.poll(ctx, raw);' in rust
    java_path.write_text(java)
    rust_path.write_text(rust)
    print("PASS: Android.13 document-switch IME control retention, activity-local rebind, exact-match fences preserved")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
