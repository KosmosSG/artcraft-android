#!/usr/bin/env python3
"""EffectCraft-only temporary native MotionEvent app-local logging and SAF export.

Do not modify released apps, shared checkout, or production signing.
Call apply_native AFTER v020_winit_compat.py and Android lifecycle patch.
Call apply_java AFTER integrate_updater.py before invoking build.sh.
"""
from pathlib import Path

NATIVE = "src/platform_impl/android/mod.rs"
JAVA = "templates/android/SafActivity.java"
LOG_NAME = "effectcraft-motion-diag.txt"

NATIVE_ANCHOR = "                match motion_event.action() {\n                    // Hover:"
NATIVE_WRITER = r'''                // Android.11, diagnostic-only: do not rely on logcat on MagicOS.
                // Sample native MotionEvent axes directly to app-private file.
                // Never log pointer coordinates, device IDs, keystrokes or documents.
                let ec11_action = motion_event.action();
                static EC11_MOVE_SAMPLE: std::sync::atomic::AtomicUsize =
                    std::sync::atomic::AtomicUsize::new(0);
                static EC11_HOVER_SAMPLE: std::sync::atomic::AtomicUsize =
                    std::sync::atomic::AtomicUsize::new(0);
                let ec11_sample = match ec11_action {
                    MotionAction::Scroll
                    | MotionAction::Down | MotionAction::Up
                    | MotionAction::PointerDown | MotionAction::PointerUp
                    | MotionAction::Cancel => true,
                    MotionAction::Move =>
                        EC11_MOVE_SAMPLE.fetch_add(1, Ordering::Relaxed) % 8 == 0,
                    MotionAction::HoverMove =>
                        EC11_HOVER_SAMPLE.fetch_add(1, Ordering::Relaxed) % 32 == 0,
                    _ => false,
                };
                if ec11_sample {
                    use std::io::Write as _;
                    // ANativeActivity internalDataPath usually points to files/, but
                    // Java checks both files/ and its parent when exporting.
                    if let Some(dir) = android_app.internal_data_path() {
                        let target = dir.join("effectcraft-motion-diag.txt");
                        if std::fs::metadata(&target).map(|m| m.len()).unwrap_or(0) < 950_000 {
                            let (v, h, x48, y49, x50, y51, scale52) =
                                motion_event.pointers().next().map(|p| (
                                    p.axis_value(Axis::Vscroll),
                                    p.axis_value(Axis::Hscroll),
                                    p.axis_value(Axis::__Unknown(48)),
                                    p.axis_value(Axis::__Unknown(49)),
                                    p.axis_value(Axis::__Unknown(50)),
                                    p.axis_value(Axis::__Unknown(51)),
                                    p.axis_value(Axis::__Unknown(52))
                                )).unwrap_or((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0));
                            let millis = std::time::SystemTime::now()
                                .duration_since(std::time::UNIX_EPOCH)
                                .map(|x| x.as_millis()).unwrap_or(0);
                            let row = format!(
                                "EC11 time_ms={} action={:?} source={:?} tool={:?} \
                                 contacts={} mouseclass={} vscroll={:.3} hscroll={:.3} \
                                 gesture48={:.5} gesture49={:.5} scroll50={:.3} \
                                 scroll51={:.3} pinch52={:.4}\n",
                                millis, ec11_action, motion_event.source(),
                                tool_type, motion_event.pointer_count(), pointer_class,
                                v, h, x48, y49, x50, y51, scale52,
                            );
                            if let Ok(mut file) = std::fs::OpenOptions::new()
                                .create(true).append(true).open(&target) {
                                let _ = file.write_all(row.as_bytes());
                            }
                        }
                    }
                }
                match motion_event.action() {
                    // Hover:'''

JAVA_ON_CREATE = "        imeSetup();\n        handleIncomingFiles(getIntent());"
JAVA_ON_RESULT = "        super.onActivityResult(requestCode, resultCode, data);"
JAVA_CLASS = "public final class __CLASS__ extends NativeActivity {"

JAVA_METHODS = r'''
    // Android.11 temporary diagnostic-only export. The button does NOT change
    // input forwarding or the application's existing save/open/IME callbacks.
    private static final int EC11_EXPORT_REQ = 0xEC11;
    private static final String EC11_DIAG_NAME = "effectcraft-motion-diag.txt";

    private void ec11SetupExportButton() {
        final android.widget.Button button = new android.widget.Button(this);
        button.setText("Export gesture log");
        button.setAllCaps(false);
        button.setTextSize(11f);
        button.setAlpha(0.88f);
        button.setOnClickListener(view -> {
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("text/plain");
            intent.putExtra(Intent.EXTRA_TITLE, "EffectCraft-Android11-gestures.txt");
            try {
                startActivityForResult(intent, EC11_EXPORT_REQ);
            } catch (Exception error) {
                android.widget.Toast.makeText(
                    this, "Cannot open export picker: " + error, android.widget.Toast.LENGTH_LONG
                ).show();
            }
        });
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
            (int) (150f * getResources().getDisplayMetrics().density),
            (int) (40f * getResources().getDisplayMetrics().density),
            Gravity.BOTTOM | Gravity.RIGHT
        );
        params.bottomMargin = (int) (55f * getResources().getDisplayMetrics().density);
        params.rightMargin = (int) (9f * getResources().getDisplayMetrics().density);
        addContentView(button, params);
    }

    private void ec11ExportResult(int resultCode, Intent data) {
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        java.io.File local = new java.io.File(getFilesDir(), EC11_DIAG_NAME);
        if (!local.isFile()) {
            local = new java.io.File(getFilesDir().getParentFile(), EC11_DIAG_NAME);
        }
        try (java.io.OutputStream out = getContentResolver().openOutputStream(data.getData(), "w")) {
            if (out == null) throw new java.io.IOException("No output stream from SAF picker");
            if (local.isFile()) {
                try (java.io.InputStream input = new java.io.FileInputStream(local)) {
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        out.write(buffer, 0, count);
                    }
                }
                android.widget.Toast.makeText(
                    this, "Gesture log exported", android.widget.Toast.LENGTH_LONG
                ).show();
            } else {
                out.write(("EC11_DIAG_NO_NATIVE_FILE\n" +
                    "Native MotionEvent hook did not write a diagnostic file.\n" +
                    "Path checked: " + getFilesDir().getAbsolutePath() + "\n"
                ).getBytes(java.nio.charset.StandardCharsets.UTF_8));
                android.widget.Toast.makeText(
                    this, "No native gesture events found; export includes diagnosis",
                    android.widget.Toast.LENGTH_LONG
                ).show();
            }
        } catch (Exception error) {
            android.widget.Toast.makeText(
                this, "Gesture export failed: " + error, android.widget.Toast.LENGTH_LONG
            ).show();
        }
    }
'''

def once(s, anchor, what):
    if s.count(anchor) != 1:
        raise RuntimeError(f"STOP: EffectCraft Android.11 {what} drift: {s.count(anchor)} instances")
def apply_native(root: Path):
    path = root / NATIVE
    s = path.read_text(encoding="utf-8")
    if "EC11 time_ms=" in s:
        raise RuntimeError("STOP: EffectCraft Android.11 native diagnostic applied twice")
    once(s, NATIVE_ANCHOR, "native input callback")
    for required in ("MotionAction::Scroll => {", "MotionAction::Move if pointer_class",
                     "Axis::__Unknown(50)", "Axis::__Unknown(52)"):
        if required not in s:
            raise RuntimeError("STOP: missing existing gesture bridge " + required)
    path.write_text(s.replace(NATIVE_ANCHOR, NATIVE_WRITER, 1), encoding="utf-8")
    print("PASS: private app-local EffectCraft native gesture diagnostics installed")

def apply_java(root: Path):
    path = root / JAVA
    s = path.read_text(encoding="utf-8")
    if "EC11_EXPORT_REQ" in s:
        raise RuntimeError("STOP: EffectCraft Android.11 SAF export applied twice")
    once(s, JAVA_CLASS, "Java activity")
    once(s, JAVA_ON_CREATE, "activity init")
    once(s, JAVA_ON_RESULT, "SAF result dispatch")
    s = s.replace(JAVA_CLASS, JAVA_CLASS + "\n" + JAVA_METHODS, 1)
    s = s.replace(JAVA_ON_CREATE, JAVA_ON_CREATE + "\n        ec11SetupExportButton();", 1)
    s = s.replace(JAVA_ON_RESULT, JAVA_ON_RESULT + """
        if (requestCode == EC11_EXPORT_REQ) {
            ec11ExportResult(resultCode, data);
            return;
        }""", 1)
    path.write_text(s, encoding="utf-8")
    print("PASS: temporary EffectCraft Android.11 in-app SAF gesture export added")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3 or sys.argv[1] not in ("native", "java"):
        raise SystemExit("Usage: patch_android_local_diag.py native <winit root> | java <builder root>")
    (apply_native if sys.argv[1] == "native" else apply_java)(Path(sys.argv[2]))
