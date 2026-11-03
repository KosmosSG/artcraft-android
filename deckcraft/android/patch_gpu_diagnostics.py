"""Add runtime GPU/backend diagnostics to DeckCraft Android staging only.

Pinned sources use eframe 0.37 wgpu CreationContext::wgpu_render_state and
egui_wgpu::RenderState::adapter; never guess an adapter from device model.
Preserve existing renderer/backend selection, DCS and official CPU rasterizer.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1])
src = root / "source/deckcraft/crates/ui-egui/src"

def edit(path, old, new):
    p = path
    s = p.read_text()
    if s.count(old) != 1:
        raise ValueError(f"GPU patch anchor changed in {p}: {old[:110]!r}; count={s.count(old)}")
    p.write_text(s.replace(old, new, 1))

edit(src / "lib.rs",
    '    ("app.about", "About DeckCraft", None, "{}"),',
    '    ("app.about", "About DeckCraft", None, "{}"),\n'
    '    ("app.gpuDiagnostics", "GPU Diagnostics…", None, "{}"),')

edit(src / "menus.rs",
    '("About DeckCraft", "app.about"),',
    '("About DeckCraft", "app.about"), ("GPU Diagnostics…", "app.gpuDiagnostics"),')

edit(src / "app/commands.rs",
    '            "app.about" => self.dialog = Some(dialogs::Dialog::new("about")),',
    '            "app.about" => self.dialog = Some(dialogs::Dialog::new("about")),\n'
    '            "app.gpuDiagnostics" => self.dialog = Some(dialogs::Dialog::new("gpuDiagnostics")),')

edit(src / "dialogs.rs",
    '        "about" => "About DeckCraft",',
    '        "about" => "About DeckCraft",\n'
    '        "gpuDiagnostics" => "GPU Diagnostics",')

edit(src / "dialogs/body.rs",
    '        "about" => dlg_about(app, ui, d),',
    """        "about" => dlg_about(app, ui, d),
        "gpuDiagnostics" => {
            let adapter = ui.ctx().data(|data| data.get_temp::<String>(
                egui::Id::new("deckcraft.android.gpu.adapter")));
            ui.heading("DeckCraft Android GPU");
            ui.label(adapter.unwrap_or_else(|| "GPU adapter unavailable (non-Android or renderer not initialized)".into()));
            ui.separator();
            ui.label("UI compositor: wgpu (GPU textures)");
            ui.label("Slide rasterizer: vello_cpu (CPU rendering, uploaded to GPU cache)");
            ui.label(format!("UI frame: {:.1} ms | Slide raster: {:.1} ms | FPS: {:.1}",
                app.perf.frame_ms, app.perf.render_ms, app.perf.fps));
            ui.label(egui::RichText::new("These are diagnostic estimates, not GPU compute timings.").small());
            let (ok, cancel) = buttons(ui, "Close");
            ok || cancel
        },""")

builder = root / "lib/build-common.sh"
hook = '''        "deckcraft": """            let details = if let Some(state) = cc.wgpu_render_state.as_ref() {
                let info = state.adapter.get_info();
                let limits = state.adapter.limits();
                format!("GPU: {} | Backend: {:?} | Device type: {:?} | Max texture: {} px",
                    info.name, info.backend, info.device_type, limits.max_texture_dimension_2d)
            } else {
                "WGPU rendering state unavailable".to_owned()
            };
            log::info!("DeckCraft Android GPU diagnostics: {details}");
            cc.egui_ctx.data_mut(|data| data.insert_temp(
                egui::Id::new("deckcraft.android.gpu.adapter"), details));
""",
'''
edit(builder, '    }.get(app, "")', hook+'    }.get(app, "")')

print("PASS: DeckCraft Help GPU Diagnostics, exact adapter selected by WGPU, safe CPU raster path")
