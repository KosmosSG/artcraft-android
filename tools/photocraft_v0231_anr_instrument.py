#!/usr/bin/env python3
"""PhotoCraft v0.23.1 test-only ANR instrumentation.

Applied to the disposable runner's Android Java activity AFTER existing input,
font, wheel, updater and canvas overlays. Emits bounded main / native thread
stacks in logcat (PcANRTest) while isolating a create/open document ANR.
Does not disable GPU canvas or the tested wheel and shortcut pad.
"""
import argparse
from pathlib import Path

CLASS = "public final class PhotoCraftActivity extends NativeActivity {"
CREATE = "        super.onCreate(savedInstanceState);"
END = "    public String pcFilesDir() {"

WATCH = r'''
    // v0.23.1 ANR isolation. Test build ONLY; no changes to user documents.
    private static final String PC_ANR_TAG = "PcANRTest";
    private volatile long pcLastUiTickMs = android.os.SystemClock.uptimeMillis();
    private volatile boolean pcAnrWatchStop = false;
    private int pcAnrStackReports = 0;

    private void pcStartAnrWatch() {
        final android.os.Handler ui = new android.os.Handler(android.os.Looper.getMainLooper());
        ui.post(new Runnable() {
            @Override public void run() {
                if (pcAnrWatchStop) return;
                pcLastUiTickMs = android.os.SystemClock.uptimeMillis();
                ui.postDelayed(this, 500L);
            }
        });
        Thread watcher = new Thread(() -> {
            long lastDumpMs = 0L;
            while (!pcAnrWatchStop) {
                try { Thread.sleep(3000L); }
                catch (InterruptedException interrupted) { return; }
                if (pcAnrWatchStop) return;
                long now = android.os.SystemClock.uptimeMillis();
                long lag = now - pcLastUiTickMs;
                // Also take periodic snapshots of the native editor thread: ANR
                // can occur inside NativeActivity while the Java looper survives.
                if (pcAnrStackReports >= 20) continue;
                if (lag < 4500L && now - lastDumpMs < 12000L) continue;
                lastDumpMs = now;
                pcAnrStackReports++;
                android.util.Log.w(PC_ANR_TAG,
                    "v0.23.1-android.1 new-document diagnostic snapshot "
                    + pcAnrStackReports + " main_heartbeat_lag_ms=" + lag);
                try {
                    java.util.Map<Thread, StackTraceElement[]> threads =
                        Thread.getAllStackTraces();
                    int printed = 0;
                    for (java.util.Map.Entry<Thread, StackTraceElement[]> entry : threads.entrySet()) {
                        Thread thread = entry.getKey();
                        String name = thread.getName();
                        String lower = name.toLowerCase(java.util.Locale.ROOT);
                        if (!(name.equals("main")
                              || lower.contains("android_main")
                              || lower.contains("renderthread")
                              || lower.contains("photocraft")
                              || lower.contains("gpu")
                              || lower.contains("wgpu")
                              || lower.contains("egui")
                              || lower.contains("compositor"))) continue;
                        StringBuilder stack = new StringBuilder();
                        StackTraceElement[] frames = entry.getValue();
                        for (int i = 0; i < Math.min(32, frames.length); i++)
                            stack.append("\n  at ").append(frames[i]);
                        android.util.Log.w(PC_ANR_TAG,
                            "THREAD " + name + " state=" + thread.getState() + stack);
                        if (++printed >= 14) break;
                    }
                } catch (Throwable error) {
                    android.util.Log.e(PC_ANR_TAG, "watchdog stack capture failed", error);
                }
            }
        }, "photocraft-anr-diagnostic");
        watcher.setDaemon(true);
        watcher.start();
        android.util.Log.i(PC_ANR_TAG,
            "ANR diagnostic watchdog enabled; no GPU / UI behavior changes");
    }

'''

def change_once(s, old, new, meaning):
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"REJECT: {meaning} anchor changed; matches={count}")
    return s.replace(old, new, 1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, required=True)
    args = parser.parse_args()
    activity = args.adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"
    source = activity.read_text(encoding="utf-8")
    if "v0.23.1 ANR isolation" in source:
        raise SystemExit("REJECT: repeated ANR instrumentation")
    source = change_once(source, END, WATCH + END, "Activity field")
    source = change_once(source, CREATE, CREATE + "\n        pcStartAnrWatch();",
                         "NativeActivity onCreate")
    source = change_once(source, CLASS, CLASS,
                         "NativeActivity package identity")
    activity.write_text(source, encoding="utf-8")
    text = activity.read_text(encoding="utf-8")
    assert text.count("pcStartAnrWatch();") == 1
    assert text.count("private void pcStartAnrWatch()") == 1
    assert "pcStylusIntercept" in text  # native stylus wheel not disabled
    assert "pcCheckUpdates" in text
    print("PASS: isolated 0.23.1 Android Java ANR native + UI thread diagnostics")
    print("PASS: stylus wheel native Java route and in-app updater preserved")
    print("NOTE: A passing CI build does not confirm that the device ANR is fixed")

if __name__ == "__main__":
    main()
