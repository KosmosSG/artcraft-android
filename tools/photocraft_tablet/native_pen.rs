//! NativeActivity pen sampling. Android tool type distinguishes a pen from a finger even
//! on touchscreens reporting pressure for every contact.
use std::collections::{HashSet, VecDeque};
use std::sync::{LazyLock, Mutex};
use std::time::{Duration, Instant};

#[derive(Clone, Copy, PartialEq)]
pub enum Phase { Down, Move, Up, Hover, Leave, Cancel }
pub struct Sample {
    pub phase: Phase, pub x: f32, pub y: f32, pub pressure: f32,
    pub tilt_x: f32, pub tilt_y: f32, pub eraser: bool,
}
#[derive(Default)]
struct State {
    samples: VecDeque<Sample>,
    down: bool,
    palm_off: bool,
    near: Option<Instant>,
    pad: Option<[f32; 4]>,
    accepted: HashSet<(i32, i32)>,
    blocked: HashSet<(i32, i32)>,
    allow_pad: HashSet<(i32, i32)>,
}
static STATE: LazyLock<Mutex<State>> = LazyLock::new(|| Mutex::new(State::default()));
pub fn reset() { *STATE.lock().unwrap() = State::default(); }
pub fn reject_palms(enabled:bool) {STATE.lock().unwrap().palm_off = !enabled;}
pub fn pad(rect: Option<[f32;4]>) { STATE.lock().unwrap().pad = rect; }
pub fn drain() -> Vec<Sample> { STATE.lock().unwrap().samples.drain(..).collect() }

/// 0 passes the touch, 1 suppresses it, 2 cancels a previously accepted contact once.
pub fn finger(device: i32, id: i32, x: f32, y: f32, start: bool, end: bool) -> u8 {
    let mut s = STATE.lock().unwrap();
    let key = (device,id);
    if start {
        s.blocked.remove(&key);
        s.accepted.remove(&key);
        s.allow_pad.remove(&key);
        if s.pad.is_some_and(|[l,t,r,b]| x>=l && x<=r && y>=t && y<=b) { s.allow_pad.insert(key); }
    }
    let mut result=0;
    if !s.palm_off && !s.allow_pad.contains(&key) && (s.down || s.near.is_some_and(|t| t.elapsed()<Duration::from_millis(500))) {
        s.blocked.insert(key);
    }
    if s.blocked.contains(&key) { result=if s.accepted.remove(&key) {2} else {1}; }
    else if start { s.accepted.insert(key); }
    if end { s.accepted.remove(&key); s.blocked.remove(&key); s.allow_pad.remove(&key); }
    result
}

/// The event is borrowed from the NDK queue and all samples are copied before finishing it.
pub(crate) unsafe fn observe(p: *const ndk_sys::AInputEvent) {
    use ndk_sys::*;
    unsafe {
        let action=AMotionEvent_getAction(p);
        let kind=action & 255;
        let which=((action>>8)&255) as usize;
        for i in 0..AMotionEvent_getPointerCount(p) {
            let tool=AMotionEvent_getToolType(p,i);
            if tool!=2 && tool!=4 { continue; }
            if matches!(kind,5|6) && i!=which { continue; }
            let phase=match kind {0|5=>Phase::Down,1|6=>Phase::Up,2=>Phase::Move,3=>Phase::Cancel,
                7|9=>Phase::Hover,10=>Phase::Leave,_=>continue};
            let mut s=STATE.lock().unwrap();
            s.near=Some(Instant::now());
            if phase==Phase::Down {s.down=true;}
            if matches!(phase,Phase::Up|Phase::Leave|Phase::Cancel) {s.down=false;}
            let history=if phase==Phase::Move {AMotionEvent_getHistorySize(p)} else {0};
            for h in 0..=history {
                let axis=|a| if h==history {AMotionEvent_getAxisValue(p,a,i)} else {AMotionEvent_getHistoricalAxisValue(p,a,i,h)};
                let tilt=axis(25).clamp(0.0,std::f32::consts::FRAC_PI_2);
                let orientation=axis(8);
                let sample=Sample {phase, x:axis(0), y:axis(1), pressure:axis(2),
                    tilt_x:(-orientation.sin()*tilt.sin()).atan2(tilt.cos()).to_degrees(),
                    tilt_y:(orientation.cos()*tilt.sin()).atan2(tilt.cos()).to_degrees(),
                    eraser:tool==4};
                if s.samples.len()>=4096 {
                    if let Some(index)=s.samples.iter().position(|a| matches!(a.phase,Phase::Move|Phase::Hover)) {s.samples.remove(index);}
                    else { s.samples.pop_front(); }
                }
                s.samples.push_back(sample);
            }
        }
    }
}
