//! VectorCraft-only two-pointer touchpad fallback. No Android dependencies.
//! Platform-classified API 34 scroll/pinch axes take priority over this detector.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum Mode { #[default] Undecided, Pan, Pinch }
#[derive(Clone, Copy, Debug)]
pub struct Sample { pub x: f64, pub y: f64, pub spread: f64 }
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Step { None, Pan(f64, f64), Pinch(f64) }
#[derive(Default, Debug)]
pub struct Detector {
    first: Option<Sample>,
    previous: Option<Sample>,
    mode: Mode,
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
            if stretched >= 4.5 && stretched > 1.15 * travelled {
                self.mode = Mode::Pinch;
            } else if travelled >= 5.0 && travelled > 0.8 * stretched {
                self.mode = Mode::Pan;
            } else {
                return Step::None;
            }
            // Discard the recognition packet to avoid a first-frame jump.
            return Step::None;
        }
        // A MagicOS touchpad may label an entire pinch as Swipe. Permit a
        // deliberate spread-dominant handoff from Pan to Pinch, but NEVER
        // switch for an ordinary two-finger scroll with slight finger drift.
        if self.mode == Mode::Pan {
            let travelled=(current.x-origin.x).hypot(current.y-origin.y);
            let stretched=(current.spread-origin.spread).abs();
            if stretched >= 14.0 && stretched > 1.8 * travelled {
                self.mode=Mode::Pinch;
                return Step::None; // Reset origin on handoff; no giant zoom.
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
    #[test] fn thresholds_do_not_confuse_slight_uneven_pan_and_zoom() {
        let mut pan=Detector::default(); pan.step(s(0.,0.,80.));
        pan.step(s(9.,0.,82.));
        assert_eq!(pan.step(s(13.,0.,83.)),Step::Pan(4.,0.));
        let mut pinch=Detector::default(); pinch.step(s(0.,0.,80.));
        pinch.step(s(1.,0.,90.));
        assert_eq!(pinch.step(s(1.,0.,99.)),Step::Pinch(1.1));
    }
}