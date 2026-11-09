"""VectorCraft Android.22: adaptive high-refresh hints, guarded menu pacing and ANR metrics.

Protect Android.20 PASS physical keyboard/IME and Android.21 native menu path.
Do not force a display mode or Vulkan unsynchronized present mode.
Request the highest supported same-resolution refresh up to 165Hz; power saver
and thermal policy can lower the request; the OS makes the final choice.

Measure UI-loop frame spacing and slow UI logic (a proxy, NOT actual GPU
presentation timings); log without text, document content, files or PII.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    s=once(s,'''    private int splashDp(int dp) {''',
    '''    // Android 11+ frame-rate preference. This is NOT a forced display
    // mode, refresh-rate lock or a promise of 165 presented FPS.
    private void vcRefreshRateHint() {
        try {
            Window window = getWindow();
            android.view.Display display = getDisplay();
            if (window == null || display == null) return;
            android.view.Display.Mode active = display.getMode();
            float maximum = 60f;
            for (android.view.Display.Mode mode : display.getSupportedModes()) {
                if (mode.getPhysicalWidth() == active.getPhysicalWidth()
                        && mode.getPhysicalHeight() == active.getPhysicalHeight()
                        && mode.getRefreshRate() <= 165.5f
                        && mode.getRefreshRate() > maximum) {
                    maximum = mode.getRefreshRate();
                }
            }
            float limit = maximum;
            android.os.PowerManager power = (android.os.PowerManager)
                getSystemService(POWER_SERVICE);
            if (power != null) {
                if (power.isPowerSaveMode()) {
                    limit = Math.min(limit, 60f);
                } else if (android.os.Build.VERSION.SDK_INT >= 29) {
                    int thermal = power.getCurrentThermalStatus();
                    if (thermal >= android.os.PowerManager.THERMAL_STATUS_SEVERE)
                        limit = Math.min(limit, 60f);
                    else if (thermal >= android.os.PowerManager.THERMAL_STATUS_MODERATE)
                        limit = Math.min(limit, 90f);
                    else if (thermal >= android.os.PowerManager.THERMAL_STATUS_LIGHT)
                        limit = Math.min(limit, 120f);
                }
            }
            float chosen = active.getRefreshRate() > 0f ?
                Math.min(active.getRefreshRate(), limit) : 60f;
            // Choose only an actual supported display mode at this resolution.
            // 60/90/120/144/165 are possible, never assumed to exist.
            float best = 0f;
            for (android.view.Display.Mode mode : display.getSupportedModes()) {
                float rate=mode.getRefreshRate();
                if (mode.getPhysicalWidth() == active.getPhysicalWidth()
                        && mode.getPhysicalHeight() == active.getPhysicalHeight()
                        && rate <= limit + 0.5f && rate > best) best=rate;
            }
            if (best > 0) chosen=best;
            WindowManager.LayoutParams attrs=window.getAttributes();
            if (Math.abs(attrs.preferredRefreshRate-chosen) > 0.1f) {
                attrs.preferredRefreshRate=chosen;
                window.setAttributes(attrs);
            }
            Log.i(TAG, "VC_DISPLAY_HINT cap=" + maximum
                + " requested=" + chosen + " actual=" + display.getRefreshRate()
                + " thermal/power managed by Android");
        } catch (Throwable error) {
            Log.w(TAG, "Optional refresh-rate hint unavailable", error);
        }
    }

    private int splashDp(int dp) {''')
    s=once(s,'''        startupStage("photocraft_direct_native_launch");
        applyImmersiveFullscreen();''',
    '''        startupStage("photocraft_direct_native_launch");
        applyImmersiveFullscreen();
        // Surface/Display may attach after onCreate; prefer its actual modes.
        getWindow().getDecorView().post(this::vcRefreshRateHint);''')
    s=once(s,'''            nativePointerIconType = -1;
            applyImmersiveFullscreen();''',
    '''            nativePointerIconType = -1;
            applyImmersiveFullscreen();
            vcRefreshRateHint();''')
    java.write_text(s)

    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    s=once(s,'''    first_painted_frame_probe_sent: bool,''',
    '''    first_painted_frame_probe_sent: bool,
    // Low-overhead ON-DEVICE performance statistics, never content/logged keys.
    vc_perf_last_ui: Option<std::time::Instant>,
    vc_perf_active_until: Option<std::time::Instant>,
    vc_perf_last_report: std::time::Instant,
    vc_perf_intervals_ms: Vec<f32>,
    vc_prune_last: Option<std::time::Instant>,''')
    s=once(s,'''                first_painted_frame_probe_sent: false,''',
    '''                first_painted_frame_probe_sent: false,
                vc_perf_last_ui: None,
                vc_perf_active_until: None,
                vc_perf_last_report: std::time::Instant::now(),
                vc_perf_intervals_ms: Vec::with_capacity(192),
                vc_prune_last: None,''')
    s=once(s,'''    fn staged_prune_tick(&mut self) {
        let current: Vec<String> = self.inner.ui.recent_files.clone();''',
    '''    fn staged_prune_tick(&mut self) {
        // Avoid filesystem metadata scans / recent-doc allocations at 165Hz.
        // Keep the exact existing safe cleanup and orphan-grace rules.
        let now=std::time::Instant::now();
        if self.vc_prune_last.is_some_and(|last|
            now.duration_since(last) < std::time::Duration::from_millis(1000)) {
            return;
        }
        self.vc_prune_last=Some(now);
        let current: Vec<String> = self.inner.ui.recent_files.clone();''')
    s=once(s,'''        self.inner.logic(ctx);
        self.persist_tick();''',
    '''        let vc_logic_started=std::time::Instant::now();
        self.inner.logic(ctx);
        let vc_logic_ms=vc_logic_started.elapsed().as_millis();
        if vc_logic_ms > 120 {
            log::warn!("VC_UI_STALL logic_ms={vc_logic_ms} (no document data recorded)");
        }
        self.persist_tick();''')
    s=once(s,'''        classify_android_precision_scroll(raw);
        // The long Window/Effect popup lists''',
    '''        classify_android_precision_scroll(raw);
        // Trigger high-refresh redraws only during actual gestures, not idle.
        // Vulkan vsync/swapchain and Android compositor decide actual pacing.
        if raw.events.iter().any(|event| matches!(event,
                egui::Event::MouseWheel { .. } | egui::Event::Touch { .. }
            )) {
            self.vc_perf_active_until =
                Some(std::time::Instant::now() + std::time::Duration::from_millis(850));
            ctx.request_repaint_after(std::time::Duration::from_micros(6060));
        }
        // The long Window/Effect popup lists''')
    s=once(s,'''    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        if !self.first_ui_logged {''',
    '''    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        // UI-loop interval proxy. Actual onscreen GPU FPS must be captured
        // separately on the tablet via Android SurfaceFlinger/Perfetto.
        let vc_now=std::time::Instant::now();
        if let Some(last)=self.vc_perf_last_ui.replace(vc_now) {
            if self.vc_perf_active_until.is_some_and(|until|vc_now <= until) {
                let dt=vc_now.duration_since(last).as_secs_f32()*1000.0;
                if dt > 0.01 && self.vc_perf_intervals_ms.len() < 240 {
                    self.vc_perf_intervals_ms.push(dt);
                }
            }
        }
        if vc_now.duration_since(self.vc_perf_last_report)
            >= std::time::Duration::from_secs(5) {
            self.vc_perf_last_report=vc_now;
            if self.vc_perf_intervals_ms.len() >= 8 {
                self.vc_perf_intervals_ms.sort_by(|a,b|a.total_cmp(b));
                let n=self.vc_perf_intervals_ms.len();
                let median=self.vc_perf_intervals_ms[n/2];
                let p95=self.vc_perf_intervals_ms[(n*95/100).min(n-1)];
                let mean=self.vc_perf_intervals_ms.iter().copied()
                    .sum::<f32>()/n as f32;
                log::info!("VC_PERF_UI_PROXY samples={n} fps={:.1} p50_ms={median:.2} p95_ms={p95:.2} target_165_frame_ms=6.06 (not Vulkan present FPS)",
                    1000.0/mean.max(0.1));
            }
            self.vc_perf_intervals_ms.clear();
        }
        if !self.first_ui_logged {''')
    rust.write_text(s)
    popup=root/"source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
    s=popup.read_text()
    s=once(s,'''ui.ctx().request_repaint_after(std::time::Duration::from_millis(16));''',
    '''ui.ctx().request_repaint_after(std::time::Duration::from_micros(6060));''')
    popup.write_text(s)
    print("PASS: Android supported-mode adaptive refresh hints; UI-loop FPS proxy; guarded 165Hz active gestures; idle unchanged")

if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
