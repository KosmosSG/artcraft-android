// WC_ANDROID_PRESSURE_STROKES_V1
// Standalone, safe pressure mapping with bounded geometry. Saved as ordinary
// WordCraft draw.stroke shapes (each with a standard fixed width) to retain
// document compatibility across DOCX/export/replay. No custom format needed.

fn wc_pressure_width(base: f32, pressure: f32) -> f32 {
    let base = if base.is_finite() { base.clamp(0.25, 72.0) } else { 1.5 };
    if !pressure.is_finite() || pressure <= 0.0 { return base; }
    let factor = (0.32 + 2.35 * pressure.clamp(0.0, 1.0)).clamp(0.32, 2.67);
    (base * factor).clamp(0.25, 72.0)
}

// Pressure values undergo the exact same endpoint-preserving Chaikin pass
// as the corresponding XY points. The lengths are always synchronized.
fn wc_smooth_pressures(pressures: &[f32], max: usize) -> Vec<f32> {
    if pressures.len() < 3 || pressures.len().saturating_mul(2) > max {
        return pressures.to_vec();
    }
    let mut out = Vec::with_capacity(pressures.len() * 2);
    out.push(pressures[0]);
    for pair in pressures.windows(2) {
        let a = pair[0];
        let b = pair[1];
        out.push(a * 0.75 + b * 0.25);
        out.push(a * 0.25 + b * 0.75);
    }
    out.push(*pressures.last().unwrap_or(&1.0));
    out
}

// Split into a low, bounded number of contiguous segments. Adjacent pieces
// share endpoints, keeping strokes continuous. Segment widths follow mean
// pressure, remain in WordCraft's normal 0.25..72.0 point range and survive
// save/reopen as ordinary ink freeforms with no format change.
fn wc_pressure_segments(
    points: &[[f32; 2]], pressures: &[f32], base: f32, max_segments: usize,
) -> Vec<(Vec<[f32; 2]>, f32)> {
    if points.len() < 2 || points.len() != pressures.len()
        || points.iter().any(|p| !p[0].is_finite() || !p[1].is_finite())
        || pressures.iter().any(|p| !p.is_finite())
    { return Vec::new(); }
    let intervals = points.len() - 1;
    let count = ((intervals as f32).sqrt().ceil() as usize)
        .clamp(1, max_segments.max(1).min(16));
    let mut result = Vec::with_capacity(count);
    let mut start = 0usize;
    for part in 0..count {
        let end = ((part + 1) * intervals / count).max(start + 1).min(intervals);
        let slice = &pressures[start..=end];
        let avg = slice.iter().sum::<f32>() / slice.len() as f32;
        result.push((points[start..=end].to_vec(), wc_pressure_width(base, avg)));
        start = end;
    }
    result
}

#[cfg(test)]
mod wc_pressure_tests {
    use super::{wc_pressure_width,wc_pressure_segments,wc_smooth_pressures};

    #[test]
    fn changing_pressure_changes_width() {
        assert!(wc_pressure_width(3., 0.8) > wc_pressure_width(3., 0.15));
        assert_eq!(wc_pressure_width(2., f32::NAN), 2.);
        assert_eq!(wc_pressure_width(2., 0.), 2.);
        assert!(wc_pressure_width(72., 1.) <= 72.);
    }
    #[test]
    fn pressure_smoothing_matches_point_count() {
        let a = wc_smooth_pressures(&[0.1,0.4,0.8], 100);
        assert_eq!(a.len(), 6);
        assert_eq!(a[0], 0.1);
        assert_eq!(*a.last().unwrap(), 0.8);
    }
    #[test]
    fn segments_join_and_bound_document_shape_count() {
        let pts: Vec<[f32; 2]> = (0..200).map(|i| [i as f32, 4.]).collect();
        let ps: Vec<f32> = (0..200).map(|i| i as f32 / 200.).collect();
        let seg = wc_pressure_segments(&pts,&ps,3.0,16);
        assert!(!seg.is_empty() && seg.len() <= 16);
        assert_eq!(seg.first().unwrap().0.first(),pts.first());
        assert_eq!(seg.last().unwrap().0.last(),pts.last());
        for w in seg.windows(2) { assert_eq!(w[0].0.last(),w[1].0.first()); }
        assert!(seg.first().unwrap().1 < seg.last().unwrap().1);
    }
    #[test]
    fn malformed_pressure_falls_back_safely() {
        assert!(wc_pressure_segments(&[[1.,2.],[3.,4.]], &[0.4],2.,16).is_empty());
        assert!(wc_pressure_segments(&[[1.,2.],[3.,4.]], &[f32::NAN,0.2],2.,16).is_empty());
    }
}
