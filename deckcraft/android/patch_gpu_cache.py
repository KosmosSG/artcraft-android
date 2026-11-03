"""Android.14: reuse an already uploaded GPU slide texture when a smaller
visible pasteboard region fits in it, rather than re-rasterizing unchanged CPU
slides on every pan. Preserve existing cache invalidation and image accuracy.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1])
source = root / "source/deckcraft/crates/ui-egui/src"
p = source / "textures.rs"
s = p.read_text()

def replace_once(old, new):
    global s
    if s.count(old) != 1:
        raise ValueError(f"DeckCraft cache patch anchor changed {old[:110]!r}: count={s.count(old)}")
    s = s.replace(old, new, 1)

helper = r'''
/// A panned viewport may request a smaller region than an already resident
/// texture covers. Reuse only if the same slide, master, zoom, style, animation,
/// and active text-edit state produced the original image. Never change a cache
/// entry's region/UVs on reuse; its actual texture origin remains unchanged.
fn android_gpu_can_reuse_canvas(old: &Key, covered: &Region, requested: &Key) -> bool {
    old.slide == requested.slide
        && old.master == requested.master
        && old.size == requested.size
        && old.edit == requested.edit
        && old.extra == requested.extra
        && old.editing_text == requested.editing_text
        && covered.contains(&requested.want)
}

'''
replace_once('#[derive(Default)]\npub struct Textures {', helper+'#[derive(Default)]\npub struct Textures {')
replace_once('    pub canvas_renders: u64,',
             '    pub canvas_renders: u64,\n'
             '    /// GPU slide texture reuse hits across all canvas display frames.\n'
             '    pub android_gpu_reuse_hits: u64,')
old = '''        if let Some(e) = &self.canvas
            && e.key == key
        {
            return Some((e.tex.clone(), e.region));
        }'''
new = '''        // A cached GPU texture can cover the new visible pasteboard even when
        // its region key differs (panning back into previously rendered space).
        // Avoid both expensive CPU rasterization and a redundant GPU upload.
        let cached = self.canvas.as_ref().filter(|e| {
            e.key == key || android_gpu_can_reuse_canvas(&e.key, &e.region, &key)
        }).map(|e| (e.tex.clone(), e.region));
        if let Some(hit) = cached {
            self.android_gpu_reuse_hits += 1;
            return Some(hit);
        }'''
replace_once(old, new)
s += r'''

#[cfg(test)]
mod android_gpu_cache_tests {
    use super::*;

    fn make_key(want: Region) -> Key {
        Key {
            slide: 22,
            master: 12,
            size: (1920, 1080),
            edit: true,
            extra: 0,
            want,
            editing_text: None,
        }
    }

    #[test]
    fn android_gpu_pan_reuses_only_unmodified_scene_inside_cached_coverage() {
        let old = make_key(Region { x: -400, y: -200, w: 2600, h: 1500 });
        let covered = old.want;
        let pan_back = make_key(Region { x: -250, y: -150, w: 2200, h: 1400 });
        assert!(android_gpu_can_reuse_canvas(&old, &covered, &pan_back));
        assert!(!android_gpu_can_reuse_canvas(&old, &covered,
            &make_key(Region { x: -600, y: -150, w: 2200, h: 1400 })));
        let mut changed = pan_back.clone();
        changed.slide = 23;
        assert!(!android_gpu_can_reuse_canvas(&old, &covered, &changed));
        changed = pan_back.clone();
        changed.extra = 1; // animation/GIF/grayscale changed
        assert!(!android_gpu_can_reuse_canvas(&old, &covered, &changed));
        changed = pan_back.clone();
        changed.size = (2048, 1152); // slide zoom changed
        assert!(!android_gpu_can_reuse_canvas(&old, &covered, &changed));
        changed = pan_back.clone();
        changed.edit = false; // slides vs editor render
        assert!(!android_gpu_can_reuse_canvas(&old, &covered, &changed));
        changed = pan_back;
        changed.master = 13;
        assert!(!android_gpu_can_reuse_canvas(&old, &covered, &changed));
    }
}
'''
p.write_text(s)

dialog = source / "dialogs/body.rs"
s = dialog.read_text()
old = '''            ui.small("These are diagnostic estimates, not GPU compute timings.");
            let (ok, cancel) = buttons(ui, "Close");
            ok || cancel'''
# Android.13 deliberately uses RichText instead of ui.small on pinned egui.
old = '''            ui.label(egui::RichText::new("These are diagnostic estimates, not GPU compute timings.").small());
            let (ok, cancel) = buttons(ui, "Close");
            ok || cancel'''
new = '''            ui.label(format!("Canvas raster passes: {} | GPU texture cache hits: {}",
                app.textures.canvas_renders, app.textures.android_gpu_reuse_hits));
            ui.label(egui::RichText::new("UI FPS is an app-pass estimate, not the tablet refresh rate. Raster cost is the last CPU render, not a live GPU timer.").small());
            ui.add_space(8.0);
            ui.button("Close").clicked()'''
if s.count(old) != 1:
    raise ValueError(f"GPU dialog change anchor: count={s.count(old)}")
dialog.write_text(s.replace(old,new,1))
print("PASS: verified GPU texture coverage reuse, scene change safety and meaningful diagnostic counters")
