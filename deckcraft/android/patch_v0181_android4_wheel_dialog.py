#!/usr/bin/env python3
"""DeckCraft Android.4 test-only customization dialog polish.

Run after the successful Android.3 launcher hub/slider stage. Only the
Android-only wheel's settings UI and default preferences are modified.
Protected production release and signing assets stay untouched.
"""
from pathlib import Path
import sys
if len(sys.argv)!=2:
    raise SystemExit("usage: patch_v0181_android4_wheel_dialog.py <disposable-builder>")
root=Path(sys.argv[1])
wheel=root/"source/deckcraft/crates/ui-egui/src/android_wheel.rs"
if not wheel.is_file():
    raise RuntimeError("Android.3 wheel must exist before UI polish")
text=wheel.read_text(encoding="utf-8")
def replace_one(before,after):
    global text
    n=text.count(before)
    if n!=1:
        raise RuntimeError(f"DeckCraft.4 unsafe anchor (count={n}): {before[:100]!r}")
    text=text.replace(before,after,1)

# Default applies to new installs and Restore Defaults; user-selected values
# loaded from persistent settings are intentionally NOT overridden.
replace_one("const STATE: &str = \"deckcraft.stylus.wheel.v1\";",
'''const DEFAULT_SIZE: f32 = 75.0;
const DEFAULT_OPACITY: f32 = 85.0;
const STATE: &str = "deckcraft.stylus.wheel.v1";''')
replace_one("slots: DEFAULT, size: 100.0, opacity: 85.0,",
            "slots: DEFAULT, size: DEFAULT_SIZE, opacity: DEFAULT_OPACITY,")
# The popup markup below replaces the complete old Android.3 settings block.
startmarker='        let win=egui::Window::new("Stylus Wheel — Default")'
endmarker='        if changed {w.save();ctx.request_repaint();}'
if text.count(startmarker)!=1 or text.count(endmarker)!=1:
    raise RuntimeError("DeckCraft.4 settings markup has changed upstream")
start=text.index(startmarker)
end=text.index(endmarker,start)
old=text[start:end]
if ('PhotoCraft-style wheel' not in old
    or 'changed |= deckcraft_slider(ui, "Wheel size"' not in old
    or 'w.settings=show;' not in old):
    raise RuntimeError("DeckCraft.4 preceding Android.3 UI not recognized")

new='''        let mut done=false;
        let win=egui::Window::new("Customize Stylus Wheel")
            .id(Id::new("deckcraft-wheel-settings"))
            .default_width(428.0)
            .open(&mut show)
            .resizable(false)
            .collapsible(false)
            .show(ctx, |ui| {
                ui.set_min_width(406.0);
                let dark=ui.visuals().dark_mode;
                let panel=if dark {
                    Color32::from_rgb(48,43,48)
                } else {
                    Color32::from_rgb(255,250,251)
                };
                let outline=if dark {
                    Color32::from_rgb(114,77,87)
                } else {
                    Color32::from_rgb(224,195,203)
                };
                let dim=if dark {
                    Color32::from_rgb(195,186,190)
                } else {
                    Color32::from_rgb(102,89,94)
                };

                // Calm, branded header in both Light and Dark appearance.
                egui::Frame::new()
                    .fill(panel)
                    .stroke(Stroke::new(0.9,outline))
                    .corner_radius(egui::CornerRadius::same(9))
                    .inner_margin(egui::Margin::symmetric(11,8))
                    .show(ui,|ui| {
                        ui.label(egui::RichText::new("Eight customizable shortcuts")
                            .size(15.0).strong());
                        ui.label(egui::RichText::new(
                            "Choose an action for each segment. An existing action swaps positions."
                        ).size(11.0).color(dim));
                    });
                ui.add_space(9.0);
                ui.label(egui::RichText::new("Wheel slots")
                    .size(16.0).strong());
                ui.add_space(3.0);

                // The labelled locations correspond to the real radial angles
                // (-90° + slot*45°), not the PDFCraft slot ordering.
                const POSITIONS:[&str;8]=[
                    "Top", "Upper right", "Right", "Lower right",
                    "Bottom", "Lower left", "Left", "Upper left"
                ];
                for slot in 0..8 {
                    egui::Frame::new()
                        .fill(panel)
                        .stroke(Stroke::new(1.0,outline))
                        .corner_radius(egui::CornerRadius::same(7))
                        .inner_margin(egui::Margin::symmetric(9,5))
                        .show(ui,|ui| {
                            ui.horizontal(|ui| {
                                ui.add_sized([34.0,24.0],egui::Label::new(
                                    egui::RichText::new(format!("{:02}",slot+1))
                                        .strong().color(PINK)));
                                ui.add_sized([106.0,24.0],egui::Label::new(
                                    egui::RichText::new(POSITIONS[slot]).color(dim)));
                                let mut selected=w.slots[slot];
                                egui::ComboBox::from_id_salt(("deck-wheel-slot",slot))
                                    .selected_text(LABELS[selected])
                                    .width(176.0)
                                    .show_ui(ui,|ui| {
                                        for (i,label) in LABELS.iter().enumerate() {
                                            ui.selectable_value(&mut selected,i,*label);
                                        }
                                    });
                                if selected!=w.slots[slot] {
                                    if let Some(old)=w.slots.iter().position(|i| *i==selected) {
                                        w.slots[old]=w.slots[slot];
                                    }
                                    w.slots[slot]=selected;
                                    changed=true;
                                }
                            });
                        });
                    ui.add_space(3.0);
                }

                ui.add_space(7.0);
                ui.label(egui::RichText::new("Appearance")
                    .size(16.0).strong());
                ui.add_space(3.0);
                egui::Frame::new()
                    .fill(panel)
                    .stroke(Stroke::new(1.0,outline))
                    .corner_radius(egui::CornerRadius::same(9))
                    .inner_margin(egui::Margin::symmetric(10,7))
                    .show(ui,|ui| {
                        changed |= deckcraft_slider(ui,"Wheel size",&mut w.size,75.0,125.0);
                        changed |= deckcraft_slider(ui,"Opacity",&mut w.opacity,60.0,100.0);
                        ui.add_space(3.0);
                        ui.label(egui::RichText::new(
                            "Size: 75–125%  ·  Opacity: 60–100%"
                        ).size(10.5).color(dim));
                    });
                ui.add_space(7.0);
                ui.label(egui::RichText::new(
                    "The wheel preview updates live. Changes save automatically."
                ).size(11.0).color(dim));
                ui.add_space(7.0);
                ui.horizontal(|ui| {
                    if ui.button("Reset defaults").clicked() {
                        w.slots=DEFAULT;
                        w.size=DEFAULT_SIZE;
                        w.opacity=DEFAULT_OPACITY;
                        changed=true;
                    }
                    ui.with_layout(
                        egui::Layout::right_to_left(egui::Align::Center),
                        |ui| {
                            if ui.add(egui::Button::new(
                                egui::RichText::new("Done").strong()
                                    .color(Color32::WHITE)
                            ).fill(PINK).min_size(vec2(75.0,26.0))).clicked() {
                                done=true;
                            }
                        });
                });
            });
        w.settings=show && !done;
'''
text=text[:start]+new+text[end:]
# Verify users' existing custom settings are preserved by the read-before-use
# preference parser and that all unrelated interactions stay intact.
for required in (
    'if let Some(text) = settings_path().and_then',
    'w.size = n.clamp(75.0, 125.0)',
    'w.opacity = n.clamp(60.0, 100.0)',
    'slot in 0..8',
    'changed |= deckcraft_slider(ui,"Wheel size"',
    'changed |= deckcraft_slider(ui,"Opacity"',
    'if ui.button("Reset defaults").clicked()',
    'w.size=DEFAULT_SIZE;',
    'w.opacity=DEFAULT_OPACITY;',
    'pub(crate) fn capture(ctx: &Context, raw: &mut RawInput)',
    'crate::icons::paint_monochrome',
    'approved_dk_logo(ui.ctx())',
    'paint(ctx,&w,p,None,"deckcraft-wheel-actual-size-preview")',
):
    if required not in text: raise RuntimeError(f"Wheel UI regression: missing {required}")
if 'PhotoCraft-style wheel' in text:
    raise RuntimeError("User requested removal of visible PhotoCraft-style label")
if 'size: 100.0' in text or 'w.size=100.0;' in text:
    raise RuntimeError("Old 100% default accidentally retained")
wheel.write_text(text,encoding="utf-8")
print("PASS: eight individually bordered wheel slot rows with true positions and branded controls")
print("PASS: fresh-install and Reset Defaults use wheel size 75% and opacity 85%")
print("PASS: no PhotoCraft attribution in dialog; persisted custom values untouched")
print("PASS: hover isolation, launcher-brand hub, white icons and live preview retained")
