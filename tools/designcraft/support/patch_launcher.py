"""Extend only the staged DesignCraft launcher; upstream source stays unchanged."""
from pathlib import Path
import sys


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Reviewed launcher API changed: {old[:80]}")
    return text.replace(old, new)


def patch(root):
    path = root / "src/lib.rs"
    source = path.read_text()
    source = replace_once(source, "struct AndroidShell {", "mod tablet;\nstruct AndroidShell {\n    tablet: tablet::Tablet,")
    source = replace_once(source, "Self { inner, app, ime,", "Self { tablet: tablet::Tablet::default(), inner, app, ime,")
    source = replace_once(source, "        system_fonts::install_system_fonts(ui.ctx());", "        self.tablet.ui(ui, &mut self.inner, &self.saf_bridge, &self.saf_state);\n        system_fonts::install_system_fonts(ui.ctx());")
    source = replace_once(source, "Box::new(move |_cc| Ok(Box::new(shell)))", "Box::new(move |cc| { tablet::record_gpu(cc); Ok(Box::new(shell)) })")
    old = 'inbox.lock().unwrap_or_else(|error| error.into_inner()).push(ImportedFile { request: request.clone(), name, bytes });'
    source = replace_once(source, old, '''if request.purpose == "android-font" {
                                if let Err(error) = tablet::install_font(&name, &bytes) {
                                    log::error!("Font import: {error}");
                                    tablet::font_result(Err(error));
                                } else {
                                    tablet::font_result(Ok(()));
                                }
                            } else {
                                ''' + old + '''
                            }''')
    path.write_text(source)
    (root / "src/tablet.rs").write_text(Path(__file__).with_name("tablet.rs").read_text())


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
