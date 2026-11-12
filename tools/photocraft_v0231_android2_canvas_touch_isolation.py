#!/usr/bin/env python3
"""PhotoCraft v0.23.1-android.2 disposable-only GPU IMAGE canvas isolation.

The previous test disabled only GPU layer composition and did not prevent the
MagicPad 4 ANR. This test leaves eframe's WGPU window renderer untouched, but
does NOT attach WGPU to PhotoCraft's own image-canvas compositor. The output
isolates whether the first canvas touch blocks inside GPU image composition.
Keep prior Stylus Wheel/shortcut pad/IME/trackpad/AI/font adaptations intact.
A runtime test, not a proven permanent solution.
"""
import argparse
from pathlib import Path

SETUP = "                    app.set_wgpu(rs);"
REPLACEMENT = """                    // PHOTOCRAFT_ANDROID2_CANVAS_TOUCH_ANR_ISOLATION
                    // WGPU continues rendering the application UI/window.
                    // Do not attach its device to the separate PhotoCraft image
                    // canvas renderer in this one disposable, diagnostic build.
                    // Android's initial canvas touch previously blocked the
                    // native event thread even when only GPU layer composition
                    // was disabled. Preserve all input + stylus routing.
                    log::warn!(
                        "PcANRTest Android.2: using CPU image canvas; WGPU UI renderer stays enabled"
                    );"""

RAW_START = "    fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {"
RAW_ADD = """    fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        // Native input breadcrumb for field ANR diagnosis; no event mutation.
        if raw.events.iter().any(|event|
            matches!(event, egui::Event::PointerButton { pressed: true, .. })
        ) {
            log::warn!("PcANRTest Android.2: raw pointer press reached PhotoCraft wrapper");
        }"""

def once(source, old, new, why):
    if source.count(old) != 1:
        raise SystemExit(
            f"REJECT: {why} v0.23.1 anchor drift: count={source.count(old)}"
        )
    return source.replace(old, new, 1)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", type=Path, required=True)
    args = p.parse_args()
    path = args.adapter / "src/lib.rs"
    source = path.read_text(encoding="utf-8")
    for must in [
        "renderer: eframe::Renderer::Wgpu",
        "PhotocraftApp::new(",
        "if let Some(rs) = cc.wgpu_render_state.clone()",
        "impl eframe::App for PhotoCraftAndroidApp",
        "self.inner.raw_input_hook(ctx, raw);",
    ]:
        if must not in source:
            raise SystemExit(f"REJECT: expected Android UI/input anchor missing: {must}")
    if "PHOTOCRAFT_ANDROID2_CANVAS_TOUCH_ANR_ISOLATION" in source:
        raise SystemExit("REJECT: attempted duplicate CPU-image-canvas patch")
    source = once(source, SETUP, REPLACEMENT, "WGPU image canvas")
    source = once(source, RAW_START, RAW_ADD, "raw input")
    path.write_text(source, encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    assert SETUP not in text
    assert "renderer: eframe::Renderer::Wgpu" in text
    assert text.count("PcANRTest Android.2") == 2
    print("PASS Android.2: PhotoCraft GPU image canvas isolated; WGPU app renderer intact")
    print("PASS Android.2: touch input raw-event breadcrumb staged; all events preserved")
    print("NOTE: device ANR still requires testing; this is not proof of a permanent fix")

if __name__ == "__main__":
    main()
