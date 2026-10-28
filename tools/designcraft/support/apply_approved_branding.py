"""Apply exact approved DesignCraft icon resources without downgrading candidate metadata.

The approved resource manifest is the owner's source of truth for artwork.
This adapter retains the generated APK's package, version and signing setup.
"""
import re
import sys
from pathlib import Path


def replace_exact(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("Reviewed DesignCraft branding anchor changed: " + old[:90])
    return text.replace(old, new, 1)


def apply(builder: Path, android: Path, version: str):
    builder = builder.resolve()
    android = android.resolve()
    if not re.fullmatch(r"\d+\.\d+\.\d+-android\.[1-9]\d*", version):
        raise ValueError("Invalid candidate Android version")
    sys.path.insert(0, str(builder / "designcraft-approved"))
    import approved_branding
    cfg = approved_branding.check_assets()
    if cfg["app"] != "designcraft":
        raise ValueError("Approved branding must match DesignCraft")
    source = builder / "source/designcraft"
    manifest = android / "Cargo.toml"
    before = manifest.read_text()
    # Existing published artwork is versioned .4; apply its graphics to .5
    # without letting its old version metadata replace the generated candidate.
    approved_branding.apply(builder, source, android, "designcraft")
    after = manifest.read_text()
    approved_version = 'version = "' + cfg["version_name"] + '"'
    after = replace_exact(after, approved_version, 'version = "' + version + '"')
    if 'icon = "@mipmap/ic_launcher"' not in after:
        raise ValueError("Approved launcher icon was not installed")
    manifest.write_text(after)
    if cfg["package"] not in before and "com.artcraft.designcraft.candidate" not in before:
        # Android package identity may be generated outside Cargo.toml; do not
        # change it here and leave APK identity validation to apksigner/aapt.
        pass

    brand_file = source / "crates/ui-egui/src/android_approved_brand.rs"
    brand = brand_file.read_text()
    home_fn = """
/// Android navigation button using the exact approved app mark.
pub fn home_button(ui: &mut egui::Ui, side: f32) -> egui::Response {
    let (rect, response) =
        ui.allocate_exact_size(egui::vec2(side, side), egui::Sense::click());
    paint(ui.painter(), rect);
    response.on_hover_text("Home")
}
"""
    if "pub fn home_button(" in brand:
        raise ValueError("DesignCraft branded Home button installed twice")
    brand_file.write_text(brand + home_fn)
    chrome = source / "crates/ui-egui/src/chrome.rs"
    text = chrome.read_text()
    original = '''                        if icons::button(ui, "home", home, app.session.active().is_none(), crate::i18n::tr(&app.ui.language, "Home")).clicked() {'''
    replacement = '''                        // Android shows DesignCraft's approved mark in the top-left,
                        // preserving the existing Home navigation on tap.
                        let home_response = {
                            #[cfg(target_os = "android")]
                            { crate::android_approved_brand::home_button(ui, home) }
                            #[cfg(not(target_os = "android"))]
                            { icons::button(ui, "home", home, app.session.active().is_none(), crate::i18n::tr(&app.ui.language, "Home")) }
                        };
                        if home_response.clicked() {'''
    chrome.write_text(replace_exact(text, original, replacement))
    print("PASS: exact approved launcher artwork, native About logo, and top-left Home logo installed; candidate version retained")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: apply_approved_branding.py BUILDER ANDROID_DIR VERSION")
    apply(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
