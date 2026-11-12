"""Android.12 guarded IME host rebind across Activity lifetimes.

A fresh Activity must not treat a focused hidden EditText as proof that its
InputConnection is bound to the current native editor. Rebind once on its
first Type entry even when focus was restored by Android before imeShow.
Old input generations remain rejected; document and preference stores untouched.
"""
from pathlib import Path
import sys

def once(src, old, new):
    n=src.count(old)
    if n != 1:
        raise ValueError(f"Android.12 expected one anchor, got {n}: {old[:90]}")
    return src.replace(old,new,1)

def patch(root):
    p=Path(root)/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=p.read_text()
    s=once(s, "    private long vcImeGeneration = 0L;",
        """    // This belongs to each Activity, never to process-wide settings.
    // A SurfaceView/IME focus restoration does not establish a valid
    // InputConnection for this Activity's native event-loop generation.
    private boolean vcImeNeedsRebind = true;
    private long vcImeGeneration = 0L;""")
    s=once(s, "                if (imm != null && !alreadyFocused) {\n                    vcImeGeneration++;\n                    imm.restartInput(view);\n                }",
        """                if (imm != null && (!alreadyFocused || vcImeNeedsRebind)) {
                    // Invalidate callbacks from the previous connection before
                    // asking Android to bind the new editor. No stale-input
                    // filter is removed or bypassed.
                    vcImeGeneration++;
                    imm.restartInput(view);
                    vcImeNeedsRebind = false;
                    Log.i(TAG, "VC_IME12 first_edit_rebind completed");
                }""")
    # End the old Activity's input host before NativeActivity completes its
    # teardown. Queues are Activity scoped; never clear persisted recovery data.
    s=once(s, '        vcMarkNativeQuitStage("on_destroy_enter");',
        '''        vcMarkNativeQuitStage("on_destroy_enter");
        // Invalidate every pending InputConnection before native teardown.
        vcImeFocusEpoch.incrementAndGet();
        vcImeGeneration++;
        vcImeNeedsRebind = true;
        imeWanted = false;
        imeEvents.clear();
        if (imeView != null) {
            try {
                InputMethodManager imm =
                    (InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
                if (imm != null) imm.hideSoftInputFromWindow(imeView.getWindowToken(), 0);
                imeView.clearFocus();
            } catch (RuntimeException error) {
                Log.w(TAG, "VC_IME12 teardown IME host", error);
            }
        }
        Log.i(TAG, "VC_IME12 old_activity_connection_invalidated");''')
    p.write_text(s)
    print("PASS: Android.12 one-time new-Activity IME rebind and old-Activity input invalidation")
if __name__ == "__main__":
    patch(Path(sys.argv[1]))
