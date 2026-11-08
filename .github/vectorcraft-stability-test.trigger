VectorCraft v0.21.0-android.13 — ONE guarded ARM64 disposable-test APK, HONOR MagicPad 4.
Source 3dc0db8c908f0062e4a2bdc4cd8ee591d2ec1a23.
Device failures in android.12: transient black startup; ANR on Ctrl+Q quick relaunch; physical V/T stops working after typing despite ESC; Save Changes S/C/D not working; menu wheel stutters vs PhotoCraft.
Fixes: native modal owner D/S/C, no Java stale imeWanted canvas guard, restore direct V/T/P dispatch, normal Activity finish(), no 16-second black fail-open, menu scrolling without double damping.
Required: complete cheap generated-source preflight and Rust behaviour gates, ARM64 binary/package/signature checks. Package com.artcraft.vectorcraft.test and disposable key only. NEVER permanently sign, merge, or publish.
