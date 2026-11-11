#!/usr/bin/env python3
"""Targeted CADCraft v0.19.0 Android-only UI compatibility overlay.

Apply only to a separately checked-out official Storytold CADCraft release.
Fail closed on upstream code changes; never modify other Craft apps.
"""
from pathlib import Path
import argparse


def apply(source: Path) -> None:
    menu = source / "crates/ui-egui/src/menus.rs"
    original = menu.read_text(encoding="utf-8")
    anchor = "                // Titles first, so a hovered title can take over before any menu is drawn."
    if original.count(anchor) != 1:
        raise SystemExit("CADCraft menu_bar changed upstream: refusing unreviewed patch")
    if "CADCRAFT_ANDROID_CC_MENU_V1" in original:
        raise SystemExit("CADCraft Cc menu already patched: refusing duplicate")

    # The extra menu is Android-only. It does not change CADCraft's desktop menus,
    # native keyboard shortcuts, CAD command registry or reference menu tree.
    # Every menu action reuses an existing CADCraft command, rather than a fake row.
    injected = """                // CADCRAFT_ANDROID_CC_MENU_V1: compact Android launcher menu.
                #[cfg(target_os = "android")]
                {
                    let cc = ui.add(
                        egui::Button::new(
                            egui::RichText::new("Cc")
                                .strong()
                                .color(egui::Color32::from_rgb(243, 228, 231))
                        )
                        .fill(egui::Color32::from_rgb(209, 49, 83))
                        .corner_radius(5.0)
                    ).on_hover_text("CADCraft Android");
                    egui::Popup::menu(&cc).show(|ui| {
                        ui.set_min_width(194.0);
                        ui.label(egui::RichText::new("CADCraft Android").strong());
                        ui.separator();
                        ui.menu_button("Appearance", |ui| {
                            for (label, id) in [
                                ("Follow System", "ui.theme.system"),
                                ("Light", "ui.theme.light"),
                                ("Dark", "ui.theme.dark"),
                            ] {
                                if ui.button(label).clicked() {
                                    clicked = Some(id.to_string());
                                    ui.close();
                                }
                            }
                        });
                        ui.separator();
                        if ui.button("About CADCraft").clicked() {
                            clicked = Some("ui.dialog.about".to_string());
                            ui.close();
                        }
                        // CADCraft's upstream manual update command is reused for
                        // this test. The future KosmosSG Android updater must be
                        // app-scoped and certificate-verified before publication.
                        if ui.button("Check Upstream Updates").clicked() {
                            clicked = Some("ui.updates.check".to_string());
                            ui.close();
                        }
                    });
                    ui.separator();
                }
"""
    revised = original.replace(anchor, injected + anchor, 1)
    menu.write_text(revised, encoding="utf-8")
    assert revised.count("CADCRAFT_ANDROID_CC_MENU_V1") == 1
    assert "ui.theme.dark" in revised
    print("PASS: CADCraft Android Cc menu + native Appearance/About/Update actions injected.")


def disable_reference_updater(template: Path) -> None:
    """Prevent the reference builder's global updater from advertising unrelated apps.

    Its Java version comparator checks the MostafaXS1 *builder* release rather than
    the installed CADCraft APK. It must not run automatically in this isolated test.
    The upstream manual CADCraft check remains available in the Cc menu.
    """
    text = template.read_text(encoding="utf-8")
    anchor = "    public static void start(final Activity activity) {"
    i = text.find(anchor)
    if i < 0:
        raise SystemExit("Reference Java updater changed: inspect before enabling a test build")
    first_brace = text.index("{", i)
    depth = 0
    end = None
    for j in range(first_brace, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end is None:
        raise SystemExit("Unbalanced reference Java updater start()")
    replacement = anchor + '\n        // CADCraft TEST ONLY: globally scoped builder updater disabled.\n    }'
    text = text[:i] + replacement + text[end:]
    template.write_text(text, encoding="utf-8")
    print("PASS: disabled unrelated builder-wide automatic update notifications in test APK.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path)
    args = p.parse_args()
    apply(args.source)
    disable_reference_updater(args.reference / "templates/android/UpdateCheck.java")


if __name__ == "__main__":
    main()
