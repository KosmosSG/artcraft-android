//! VectorCraft-only two-pointer touchpad fallback. No Android dependencies.
//! Platform-classified API 34 scroll/pinch axes take priority over this detector.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum Mode { #[default] Undecided, Pan, Pinch }
#[derive(Clone, Copy, Debug)]
pub struct Sample { pub x: f64, pub y: f64, pub spread: f64 }
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Step { None, Pan(f64, f64), Pinch(f64) }
// Android API 34 gesture axes are RELATIVE to the immediately preceding
// native sample. A single MotionEvent can carry several historical samples.
// Accumulate all historical values then the current sample exactly once.
// This is pure Rust so batching logic can be unit-tested without Android.
#[derive(Debug, Default, Clone, Copy)]
pub struct AxisTotals {
    pub pan_x: f64,
    pub pan_y: f64,
    pub zoom_log: f64,
    pub zoom_count: u32,
}
impl AxisTotals {
    pub fn add(&mut self, x: f64, y: f64, scale: f64) {
        if x.is_finite() { self.pan_x += x; }
        if y.is_finite() { self.pan_y += y; }
        if scale.is_finite() && (0.4..=2.5).contains(&scale)
            && (scale - 1.0).abs() >= 0.0001 {
            self.zoom_log += scale.ln();
            self.zoom_count = self.zoom_count.saturating_add(1);
        }
    }
    pub fn scale(&self) -> f64 {
        if self.zoom_count == 0 { 0.0 } else { self.zoom_log.exp() }
    }
    pub fn has_data(&self) -> bool {
        self.pan_x != 0.0 || self.pan_y != 0.0 || self.zoom_count > 0
    }
}
#[derive(Default, Debug)]
pub struct Detector {
    first: Option<Sample>,
    previous: Option<Sample>,
    mode: Mode,
    // Consecutive, same-direction spread-dominant samples allow a deliberate
    // pinch to take over an early pan without relying on total drag distance.
    pinch_streak: u8,
    last_spread_direction: i8,
}
impl Detector {
    pub fn reset(&mut self) { *self = Self::default(); }
    pub fn mode(&self) -> Mode { self.mode }
    pub fn step(&mut self, current: Sample) -> Step {
        if !current.x.is_finite() || !current.y.is_finite() ||
            !current.spread.is_finite() || current.spread <= 0.0 {
            self.reset();
            return Step::None;
        }
        let Some(previous) = self.previous.replace(current) else {
            self.first = Some(current);
            return Step::None;
        };
        let origin = self.first.unwrap_or(previous);
        if self.mode == Mode::Undecided {
            let travelled = (current.x - origin.x).hypot(current.y - origin.y);
            let stretched = (current.spread - origin.spread).abs();
            // Small, decisive deadzones: don't turn a two-finger glide into a pinch.
            if stretched >= 3.5 && stretched > 1.05 * travelled {
                self.mode = Mode::Pinch;
            } else if travelled >= 7.0 && travelled > 1.15 * stretched {
                self.mode = Mode::Pan;
            } else {
                return Step::None;
            }
            // Discard the recognition packet to avoid a first-frame jump.
            return Step::None;
        }
        // A MagicOS pinch may start as a TwoFingerSwipe. The previous
        // algorithm compared spread against all midpoint travel since gesture
        // start: after scrolling, that growing travel made a fresh pinch
        // nearly impossible. Instead detect TWO consistent local pinch steps.
        // This also keeps ordinary pan drift from becoming a pinch.
        if self.mode == Mode::Pan {
            let ds = current.spread - previous.spread;
            let dp = (current.x - previous.x).hypot(current.y - previous.y);
            let direction: i8 = if ds > 0.0 { 1 } else { -1 };
            if ds.abs() >= 2.0 && ds.abs() > 1.3 * dp {
                self.pinch_streak = if self.last_spread_direction == direction {
                    self.pinch_streak.saturating_add(1)
                } else { 1 };
                self.last_spread_direction = direction;
            } else {
                self.pinch_streak = 0;
                self.last_spread_direction = 0;
            }
            let travelled = (current.x - origin.x).hypot(current.y - origin.y);
            let stretched = (current.spread - origin.spread).abs();
            let clear_start_pinch = stretched >= 9.0 && stretched > 1.5 * travelled;
            if self.pinch_streak >= 2 || clear_start_pinch {
                self.mode = Mode::Pinch;
                return Step::None; // Drop transition packet; avoid zoom jump.
            }
        }
        match self.mode {
            Mode::Pan => {
                let dx = current.x - previous.x;
                let dy = current.y - previous.y;
                if dx.abs() > 256.0 || dy.abs() > 256.0 {
                    Step::None // Still resynced previous; discard obviously stale jump.
                } else if dx != 0.0 || dy != 0.0 {
                    Step::Pan(dx, dy)
                } else { Step::None }
            }
            Mode::Pinch => {
                if previous.spread <= 0.0 { return Step::None; }
                let factor = current.spread / previous.spread;
                if factor.is_finite() && (0.4..=2.5).contains(&factor) &&
                    (factor - 1.0).abs() > 0.0001 { Step::Pinch(factor) }
                else { Step::None }
            }
            Mode::Undecided => Step::None,
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn s(x:f64,y:f64,spread:f64)->Sample { Sample{x,y,spread} }
    #[test] fn batched_native_pinch_applies_all_historical_samples() {
        let mut totals=AxisTotals::default();
        totals.add(0.0,0.0,1.005);
        totals.add(0.0,0.0,1.007);
        totals.add(0.0,0.0,1.0);
        assert_eq!(totals.zoom_count, 2);
        assert!((totals.scale()-1.005*1.007).abs()<1.0e-12);
        assert!(totals.has_data());
    }
    #[test] fn batched_native_scroll_applies_all_history_in_order() {
        let mut totals=AxisTotals::default();
        totals.add(3.0,-4.0,0.0);
        totals.add(2.0,-1.0,0.0);
        assert_eq!(totals.pan_x,5.0);
        assert_eq!(totals.pan_y,-5.0);
        assert_eq!(totals.scale(),0.0);
    }
    #[test] fn reject_invalid_native_axis_values() {
        let mut totals=AxisTotals::default();
        totals.add(f64::INFINITY,f64::NAN,-1.0);
        totals.add(0.0,0.0,1.0);
        assert_eq!(totals.zoom_count,0);
        assert!(!totals.has_data());
    }
    #[test] fn two_finger_pan_stays_pan_even_if_fingers_drift() {
        let mut d=Detector::default();
        assert_eq!(d.step(s(10.,10.,80.)), Step::None);
        assert_eq!(d.step(s(17.,11.,80.)), Step::None);
        assert_eq!(d.step(s(21.,13.,81.)), Step::Pan(4.,2.));
        assert_eq!(d.step(s(25.,14.,92.)), Step::Pan(4.,1.));
    }
    #[test] fn pinch_uses_incremental_scale_not_total_spread() {
        let mut d=Detector::default();
        assert_eq!(d.step(s(100.,100.,100.)),Step::None);
        assert_eq!(d.step(s(100.,100.,110.)),Step::None);
        assert_eq!(d.step(s(100.,100.,121.)),Step::Pinch(1.1));
        assert_eq!(d.step(s(100.,100.,110.)),Step::Pinch(110./121.));
    }
    #[test] fn never_acts_on_single_baseline_or_outlier() {
        let mut d=Detector::default();
        d.step(s(0.,0.,100.)); d.step(s(6.,0.,100.));
        assert_eq!(d.step(s(500.,0.,100.)),Step::None);
        assert_eq!(d.step(s(501.,0.,100.)),Step::Pan(1.,0.));
        d.reset();
        assert_eq!(d.step(s(100.,0.,100.)),Step::None);
    }
    #[test] fn clear_pinch_can_take_over_an_early_swipe_classification() {
        let mut d=Detector::default();
        assert_eq!(d.step(s(0.,0.,100.)),Step::None);
        assert_eq!(d.step(s(10.,0.,100.)),Step::None);
        assert_eq!(d.step(s(12.,0.,101.)),Step::Pan(2.,0.));
        assert_eq!(d.step(s(13.,0.,135.)),Step::None);
        assert_eq!(d.mode(),Mode::Pinch);
        assert_eq!(d.step(s(13.,0.,150.)),Step::Pinch(150./135.));
    }
    #[test] fn scrolling_with_small_spread_drift_does_not_zoom() {
        let mut d=Detector::default();
        d.step(s(0.,0.,100.)); d.step(s(9.,0.,102.));
        assert_eq!(d.step(s(20.,0.,110.)),Step::Pan(11.,0.));
        assert_eq!(d.step(s(25.,0.,112.)),Step::Pan(5.,0.));
        assert_eq!(d.mode(),Mode::Pan);
    }
    #[test] fn direct_small_pinch_does_not_require_preceding_scroll() {
        let mut d=Detector::default();
        assert_eq!(d.step(s(100.,100.,100.)),Step::None);
        assert_eq!(d.step(s(101.,100.,104.)),Step::None);
        assert_eq!(d.mode(),Mode::Pinch);
        assert_eq!(d.step(s(102.,100.,108.)),Step::Pinch(108./104.));
    }
    #[test] fn slow_pinch_after_long_scroll_uses_local_movement() {
        let mut d=Detector::default();
        d.step(s(0.,0.,100.)); d.step(s(12.,0.,100.));
        assert_eq!(d.mode(),Mode::Pan);
        assert_eq!(d.step(s(120.,0.,100.)),Step::Pan(108.,0.));
        assert_eq!(d.step(s(121.,0.,103.)),Step::Pan(1.,0.));
        assert_eq!(d.step(s(122.,0.,106.)),Step::None);
        assert_eq!(d.mode(),Mode::Pinch);
        assert_eq!(d.step(s(122.,0.,109.)),Step::Pinch(109./106.));
    }
    #[test] fn scroll_drift_in_one_direction_is_not_a_pinch() {
        let mut d=Detector::default();
        d.step(s(0.,0.,100.)); d.step(s(10.,0.,101.));
        assert_eq!(d.step(s(20.,0.,104.)),Step::Pan(10.,0.));
        assert_eq!(d.step(s(30.,0.,107.)),Step::Pan(10.,0.));
        assert_eq!(d.mode(),Mode::Pan);
    }
    #[test] fn thresholds_do_not_confuse_slight_uneven_pan_and_zoom() {
        let mut pan=Detector::default(); pan.step(s(0.,0.,80.));
        pan.step(s(9.,0.,82.));
        assert_eq!(pan.step(s(13.,0.,83.)),Step::Pan(4.,0.));
        let mut pinch=Detector::default(); pinch.step(s(0.,0.,80.));
        pinch.step(s(1.,0.,90.));
        assert_eq!(pinch.step(s(1.,0.,99.)),Step::Pinch(1.1));
    }
}