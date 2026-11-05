use egui::{Rect, Pos2, pos2, vec2};
/// The pad's width in points, and in the phone layout.
pub const WIDTH: f32 = 72.0;
pub const COMPACT_WIDTH: f32 = 56.0;
const MARGIN: f32 = 6.0;
/// A key's height when the pad has room; keys shrink evenly towards [`MIN_KEY_H`] to fit.
const KEY_H: f32 = 44.0;
/// The smallest key height, still a comfortable finger target.
pub const MIN_KEY_H: f32 = 26.0;
const GAP: f32 = 6.0;
const WHEEL_GAP: f32 = 12.0;
/// The on-screen keyboard key at the bottom of the pad.
const KEYBOARD_H: f32 = 36.0;

/// A part of the pad.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Control {
    Key(usize),
    Ring,
    Center,
    /// The always-present key at the bottom that opens the on-screen keyboard.
    Keyboard,
    /// The always-present key above it that enters and leaves full screen.
    ScreenMode,
    /// The pad's background: touches there do nothing (and don't reach the canvas).
    Panel,
}

/// Where the pad's parts are, for a pad of a given size.
#[derive(Clone, Debug, PartialEq)]
pub struct Layout {
    pub panel: Rect,
    /// Top to bottom: the first half (rounded up) above the wheel, the rest below.
    pub keys: Vec<Rect>,
    pub center: Pos2,
    pub ring_outer: f32,
    pub ring_inner: f32,
    /// The on-screen keyboard key, at the very bottom.
    pub keyboard: Rect,
    /// The full screen key, just above it.
    pub screen_mode: Rect,
}

impl Layout {
    /// `count` keys split around the wheel (the extra one of an odd count above it), centred
    /// vertically in `panel` above the keyboard key at its bottom. Keys are [`KEY_H`] tall where
    /// they fit and shrink evenly, down to [`MIN_KEY_H`], on a shorter panel.
    pub fn new(full: Rect, count: usize) -> Self {
        let w = (full.width() - 2.0 * MARGIN).max(1.0);
        let keyboard = Rect::from_min_size(pos2(full.left() + MARGIN, full.bottom() - MARGIN - KEYBOARD_H), vec2(w, KEYBOARD_H));
        let screen_mode = Rect::from_min_size(pos2(full.left() + MARGIN, keyboard.top() - GAP - KEYBOARD_H), vec2(w, KEYBOARD_H));
        // The keys and wheel share what is left above them.
        let panel = Rect::from_min_max(full.min, pos2(full.right(), (screen_mode.top() - GAP).max(full.top())));
        let wheel = w;
        let above = count.div_ceil(2);
        let below = count / 2;
        let gaps = (above.saturating_sub(1) + below.saturating_sub(1)) as f32 * GAP;
        let fixed = wheel + 2.0 * WHEEL_GAP + gaps;
        let key_h = if count == 0 { KEY_H } else { ((panel.height() - 2.0 * MARGIN - fixed) / count as f32).clamp(MIN_KEY_H, KEY_H) };
        let total = count as f32 * key_h + fixed;
        // Centred; on a panel too short even for the smallest keys, from the top.
        let mut y = (panel.center().y - total / 2.0).max(panel.top() + MARGIN);
        let x = panel.left() + MARGIN;
        let mut keys = Vec::with_capacity(count);
        for i in 0..above {
            keys.push(Rect::from_min_size(pos2(x, y), vec2(w, key_h)));
            y += key_h + if i + 1 < above { GAP } else { 0.0 };
        }
        y += WHEEL_GAP;
        let center = pos2(x + w / 2.0, y + wheel / 2.0);
        y += wheel + WHEEL_GAP;
        for _ in 0..below {
            keys.push(Rect::from_min_size(pos2(x, y), vec2(w, key_h)));
            y += key_h + GAP;
        }
        Self { panel: full, keys, center, ring_outer: wheel / 2.0, ring_inner: wheel * 0.3, keyboard, screen_mode }
    }

    /// The keys' height (the same for all).
    pub fn key_height(&self) -> f32 {
        self.keys.first().map_or(KEY_H, |k| k.height())
    }

    /// What a touch at `p` (inside the pad) lands on. The wheel takes a little slop around its
    /// edge; keys take half the gap around them.
    pub fn hit(&self, p: Pos2) -> Control {
        if self.keyboard.expand(GAP / 2.0).contains(p) {
            return Control::Keyboard;
        }
        if self.screen_mode.expand(GAP / 2.0).contains(p) {
            return Control::ScreenMode;
        }
        let d = p.distance(self.center);
        if d <= self.ring_inner {
            return Control::Center;
        }
        // The whole width of the pad beside the wheel is the ring: easy to hit with a finger.
        if d <= self.ring_outer + WHEEL_GAP / 2.0 || (p.y - self.center.y).abs() <= self.ring_outer + WHEEL_GAP / 2.0 {
            return Control::Ring;
        }
        self.keys.iter().position(|k| k.expand(GAP / 2.0).contains(p)).map_or(Control::Panel, Control::Key)
    }
}

/// A pad touch, for the pad to act on.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum PadTouch {
    Down(Control, Pos2),
    Move(Control, Pos2),
    Up(Control),
}
