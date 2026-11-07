// WC_STYLUS_CURVE_SMOOTHING_V1
// One bounded Chaikin pass: a low-cost, endpoint-preserving rounded ink curve.
// Used for both live previews and saved draw.stroke path; document data remains
// ordinary points, so undo/replay/export paths are unchanged.
fn wc_smooth_stroke(points: &[[f32; 2]], limit: usize) -> Vec<[f32; 2]> {
    if points.len() < 3 || points.len().saturating_mul(2) > limit {
        return points.to_vec();
    }
    let mut out = Vec::with_capacity(points.len() * 2);
    out.push(points[0]);
    for pair in points.windows(2) {
        let (a, b) = (pair[0], pair[1]);
        // Don't propagate a broken coordinate into the drawing.
        if !a.iter().chain(b.iter()).all(|v| v.is_finite()) {
            return points.to_vec();
        }
        out.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25]);
        out.push([a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
    }
    out.push(*points.last().expect("stroke is non-empty"));
    out
}

#[cfg(test)]
mod wc_stylus_smoothing_tests {
    use super::wc_smooth_stroke;
    #[test]
    fn endpoints_are_preserved() {
        let pts = [[0., 0.], [4., 7.], [10., 0.], [11., 3.]];
        let result = wc_smooth_stroke(&pts, 100);
        assert_eq!(result.first(), pts.first());
        assert_eq!(result.last(), pts.last());
        assert_eq!(result.len(), pts.len() * 2);
    }
    #[test]
    fn short_and_full_strokes_remain_unchanged() {
        assert_eq!(wc_smooth_stroke(&[[0.,0.], [1., 1.]], 20).len(), 2);
        assert_eq!(wc_smooth_stroke(&[[0.,0.], [1., 1.], [2., 2.]], 4).len(), 3);
    }
    #[test]
    fn right_angle_is_rounded_without_spiking() {
        let result = wc_smooth_stroke(&[[0.,0.], [10.,0.], [10.,10.]], 100);
        assert!(result.iter().all(|p| p[0] >= 0. && p[0] <= 10. && p[1] >= 0. && p[1] <= 10.));
        assert_eq!(result[2], [7.5, 0.]);
        assert_eq!(result[3], [10., 2.5]);
    }
}
