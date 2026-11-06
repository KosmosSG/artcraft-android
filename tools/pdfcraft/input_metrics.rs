//! PDFCraft-only native input telemetry. No JNI, logging or allocation per event.
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering::Relaxed};
use std::sync::OnceLock;
use std::time::Instant;
pub static ENABLED: AtomicBool = AtomicBool::new(false);
static START: OnceLock<Instant> = OnceLock::new();
static EVENTS: AtomicU64 = AtomicU64::new(0);
static SCROLLS: AtomicU64 = AtomicU64::new(0);
static SOURCE: AtomicU64 = AtomicU64::new(0);
static ACTION: AtomicU64 = AtomicU64::new(0);
static EVENT_NS: AtomicU64 = AtomicU64::new(0);
static FIRST_NS: AtomicU64 = AtomicU64::new(0);
static PENDING: AtomicU64 = AtomicU64::new(0);
static LATENCY: AtomicU64 = AtomicU64::new(0);
pub fn enabled(value: bool) { ENABLED.store(value, Relaxed); if !value { PENDING.store(0, Relaxed); } }
fn micros() -> u64 { START.get_or_init(Instant::now).elapsed().as_micros() as u64 + 1 }
pub fn record(source: u32, action: u32, time: i64, scrolling: bool) {
    if !ENABLED.load(Relaxed) { return; }
    EVENTS.fetch_add(1, Relaxed);
    SOURCE.store(source as u64, Relaxed);
    ACTION.store(action as u64, Relaxed);
    EVENT_NS.store(time.max(0) as u64, Relaxed);
    if scrolling {
        SCROLLS.fetch_add(1, Relaxed);
        let current = time.max(0) as u64;
        let previous = SCROLL_LAST.swap(current, Relaxed);
        // Only gaps within an active burst; idle time is not input frequency.
        if previous > 0 && current > previous && current - previous <= 250_000_000 {
            let gap = current - previous;
            GAP_COUNT.fetch_add(1, Relaxed);
            GAP_NS.fetch_add(gap, Relaxed);
            GAP_MAX.fetch_max(gap, Relaxed);
        }
        let _ = FIRST_NS.compare_exchange(0, time.max(0) as u64, Relaxed, Relaxed);
        let _ = PENDING.compare_exchange(0, micros(), Relaxed, Relaxed);
    }
}
/// Dispatch-to-UI-completion, NOT input-to-photon or GPU present latency.
pub fn ui_complete() {
    if !ENABLED.load(Relaxed) { return; }
    let start = PENDING.swap(0, Relaxed);
    if start != 0 {
        let elapsed = micros().saturating_sub(start);
        LATENCY.store(elapsed, Relaxed);
        LATENCY_MAX.fetch_max(elapsed, Relaxed);
    }
}
pub fn snapshot() -> (u64, u64, u64, u64, u64, f64, f64) {
    let last = EVENT_NS.load(Relaxed);
    let first = FIRST_NS.load(Relaxed);
    let scrolls = SCROLLS.load(Relaxed);
    let hz = if last > first && first > 0 { scrolls.saturating_sub(1) as f64 * 1e9 / (last-first) as f64 } else { 0.0 };
    (EVENTS.load(Relaxed), scrolls, SOURCE.load(Relaxed), ACTION.load(Relaxed), last, hz, LATENCY.load(Relaxed) as f64 / 1000.0)
}

/// Sum relative samples once per native batch; absolute touch coordinates are NOT summed.
#[derive(Default)]
pub struct ScrollBatch {
    sum: [f64; 4],
    pub historical_nonzero: u64,
    pub fractional: bool,
}
impl ScrollBatch {
    pub fn push(&mut self, axes: [f32; 4], historical: bool) {
        if !axes.iter().all(|v| v.is_finite()) { return; }
        if historical && axes.iter().any(|v| *v != 0.0) { self.historical_nonzero += 1; }
        self.fractional |= axes[0].fract() != 0.0 || axes[1].fract() != 0.0;
        for (sum, value) in self.sum.iter_mut().zip(axes) { *sum += value as f64; }
    }
    pub fn axes(&self) -> [f32; 4] {
        self.sum.map(|v| { let v = v as f32; if v.is_finite() { v } else { 0.0 } })
    }
}
static HISTORY: AtomicU64 = AtomicU64::new(0);
static HISTORY_SCROLL: AtomicU64 = AtomicU64::new(0);
static SCROLL_LAST: AtomicU64 = AtomicU64::new(0);
static GAP_COUNT: AtomicU64 = AtomicU64::new(0);
static GAP_NS: AtomicU64 = AtomicU64::new(0);
static GAP_MAX: AtomicU64 = AtomicU64::new(0);
static LATENCY_MAX: AtomicU64 = AtomicU64::new(0);
pub fn history(total: u64, scrolling: u64) {
    if !ENABLED.load(Relaxed) { return; }
    HISTORY.fetch_add(total, Relaxed);
    HISTORY_SCROLL.fetch_add(scrolling, Relaxed);
}
pub fn timing_snapshot() -> (u64, u64, f64, f64, f64) {
    let n = GAP_COUNT.load(Relaxed);
    (HISTORY.load(Relaxed), HISTORY_SCROLL.load(Relaxed),
        if n > 0 { GAP_NS.load(Relaxed) as f64 / n as f64 / 1e6 } else { 0.0 },
        GAP_MAX.load(Relaxed) as f64 / 1e6, LATENCY_MAX.load(Relaxed) as f64 / 1000.0)
}

/// Sticky precision classification within a native timestamped event stream.
/// No guessed velocity or generated momentum. Zero deltas do not end a gesture.
#[derive(Default)]
pub struct PrecisionStream { device: Option<i32>, last_ns: i64, precise: bool }
impl PrecisionStream {
    pub fn classify(&mut self, device: i32, ns: i64, evidence: bool) -> bool {
        if self.device != Some(device) || ns < self.last_ns || ns - self.last_ns > 250_000_000 {
            self.precise = false;
        }
        self.device = Some(device);
        self.last_ns = ns;
        self.precise |= evidence;
        self.precise
    }
    pub fn reset(&mut self) { *self = Self::default(); }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn fractional_integer_zero_replay() {
        let mut s = PrecisionStream::default();
        for (i, d) in [0.25_f32, 1.0, 0.0, -1.0, -0.5].into_iter().enumerate() {
            assert!(s.classify(1, i as i64 * 8_000_000, d.fract() != 0.0));
        }
    }
    #[test] fn mouse_and_device_isolation() {
        let mut s = PrecisionStream::default();
        assert!(!s.classify(1, 1, false));
        assert!(s.classify(1, 2, true));
        assert!(!s.classify(2, 3, false));
        assert!(s.classify(2, 4, true));
        assert!(!s.classify(2, 300_000_000, false));
        assert!(s.classify(2, 300_000_001, true));
        s.reset(); assert!(!s.classify(2, 300_000_002, false));
    }
    #[test] fn timestamp_reversal_resets() {
        let mut s = PrecisionStream::default();
        assert!(s.classify(1, 100, true)); assert!(!s.classify(1, 90, false));
    }
}

#[cfg(test)]
mod batch_tests {
    use super::*;
    #[test] fn keeps_history_when_latest_is_zero() {
        let mut b = ScrollBatch::default();
        b.push([0.0, 0.0, 3.0, -8.0], true);
        b.push([0.0, 0.0, 4.0, -12.0], true);
        b.push([0.0; 4], false);
        assert_eq!(b.axes(), [0.0, 0.0, 7.0, -20.0]);
        assert_eq!(b.historical_nonzero, 2);
    }
    #[test] fn partition_invariant_and_reversal() {
        let samples = [[0.25, 0.0, 5.0, -20.0], [0.75, 0.0, -5.0, 10.0], [0.0, 0.0, 2.0, -5.0]];
        let mut batch = ScrollBatch::default();
        let mut separate = [0.0; 4];
        for sample in samples {
            batch.push(sample, true);
            let mut one = ScrollBatch::default(); one.push(sample, false);
            for (total, value) in separate.iter_mut().zip(one.axes()) { *total += value; }
        }
        assert_eq!(batch.axes(), separate);
        assert!(batch.fractional); // Integral sum must not erase precision evidence.
    }
    #[test] fn rejects_nonfinite_without_losing_other_samples() {
        let mut b = ScrollBatch::default();
        b.push([0.0, 0.0, 0.0, f32::NAN], true);
        b.push([0.0, 0.0, 0.0, 700.0], false);
        assert_eq!(b.axes()[3], 700.0);
    }
}
