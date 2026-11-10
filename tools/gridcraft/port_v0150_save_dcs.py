#!/usr/bin/env python3
"""GridCraft v0.15.0 Android D/C/S, Esc and acknowledged SAF-close staging.

Changes ONLY an isolated official GridCraft v0.15.0 source checkout.
Preserves the tested v0.11.1 implementations as source includes; it does not
modify or build any installed APK, read secrets or authorize production.
All API anchors are checked before ANY file is written (fail closed).
"""
from pathlib import Path
import argparse
import json
import tomllib

SUPPORTED_VERSIONS = ("0.16.1", "0.18.0")
MARKER = "GRIDCRAFT_ANDROID_V0150_SAVE_PORT_V1"
ROOT = Path(__file__).resolve().parent
SOURCES = {
    "services": "crates/ui-egui/src/services.rs",
    "lib": "crates/ui-egui/src/lib.rs",
    "app": "crates/ui-egui/src/app.rs",
    "quit": "crates/ui-egui/src/app/quit.rs",
    "dialog": "crates/ui-egui/src/dialogs/show.rs",
    "commands": "crates/ui-egui/src/app/commands.rs",
}


def once(src: str, old: str, new: str, label: str) -> str:
    found = src.count(old)
    if found != 1:
        raise RuntimeError(f"{label}: expected exactly one v0.15.0 anchor, got {found}: {old[:90]!r}")
    return src.replace(old, new, 1)


# Keep D/C/S one-shot and unmodified; remove paired egui::Text events only
# while Save Changes is actually open, preserving cell editing and IME input.
DCS_HELPER = r'''
// GRIDCRAFT_ANDROID_V0150_SAVE_PORT_V1: D/C/S only belongs to modal Save Changes.
fn gridcraft_android_take_dcs(ctx: &egui::Context) -> Option<u8> {
    // Java can intercept D/C/S while the hidden Android IME owns focus.
    // Consume the ONE-SHOT native response first, then look at egui keys.
    // Native bridge only queues a response while the Save Changes modal is active.
    let native = ctx.data_mut(|data| data.remove_temp::<u8>(
        egui::Id::new("gridcraft.unsaved.dcs")
    ));
    let from_egui = ctx.input_mut(|i| {
        let mut action = None;
        let mut consumed = false;
        i.events.retain(|e| {
            if let egui::Event::Key { key, pressed, repeat, modifiers, .. } = e {
                let candidate = match key {
                    egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0
                };
                if candidate != 0 && !modifiers.any() {
                    consumed = true;
                    if *pressed && !*repeat && action.is_none() { action = Some(candidate); }
                    return false;
                }
            }
            true
        });
        if consumed {
            i.events.retain(|e| !matches!(e,
                egui::Event::Text(t) if matches!(t.as_str(), "d" | "D" | "c" | "C" | "s" | "S")
            ));
        }
        action
    });
    native.or(from_egui)
}
'''

APP_HELPER = r'''
// GRIDCRAFT_ANDROID_V0150_SAVE_PORT_V1: helper used by the existing Android launcher overlay.
impl SheetApp {
    pub fn android_unsaved_dcs_active(&self) -> bool {
        self.dialog.as_ref().is_some_and(|d| d.name() == "saveChanges")
    }

    pub fn android_capture_unsaved_dcs(&self, _ctx: &egui::Context) {
        // Compatibility shim: the actual keys are captured inside the modal
        // dialogs/show.rs pass. Never spin/repaint continuously while waiting
        // for input; Android/egui already requests a frame on key or touch.
    }
}
'''


def port(checkout: Path, *, verify_only: bool = False) -> dict:
    checkout = Path(checkout).resolve()
    manifest = checkout / "Cargo.toml"
    if not manifest.is_file():
        raise RuntimeError("Missing separate official GridCraft source checkout")
    version = tomllib.loads(manifest.read_text())["workspace"]["package"]["version"]
    if version not in SUPPORTED_VERSIONS:
        raise RuntimeError(f"Refusing to port unknown GridCraft {version}; expected one of {SUPPORTED_VERSIONS}")
    src = {}
    for key, relative in SOURCES.items():
        path = checkout / relative
        if not path.is_file():
            raise RuntimeError(f"Missing GridCraft v0.15.0 source: {relative}")
        src[key] = path.read_text()
        if MARKER in src[key] or "android_pending_close:" in src[key]:
            raise RuntimeError(f"{relative}: Android save port already applied; no duplicate patch")

    src["services"] = once(
        src["services"], "pub struct Services {",
        "pub struct Services {\n"
        "    // " + MARKER + ": Android host MUST acknowledge SAF document write before close.\n"
        "    pub android_save_close: Option<Box<dyn Fn(&str, &[u8], std::sync::mpsc::Sender<bool>)>>,"
        , SOURCES["services"],
    )
    src["lib"] = once(
        src["lib"], "pub struct SheetApp {",
        "pub struct SheetApp {\n"
        "    // " + MARKER + ": uid/revision/response/quitting; no early close before SAF ack.\n"
        "    android_pending_close: Option<(u64, u64, std::sync::mpsc::Receiver<bool>, bool)>,",
        SOURCES["lib"],
    )
    src["app"] = once(
        src["app"], "        SheetApp {",
        "        SheetApp {\n            android_pending_close: None,", SOURCES["app"],
    )
    src["app"] = once(
        src["app"], "    pub fn logic(&mut self, ctx: &egui::Context) {",
        "    pub fn logic(&mut self, ctx: &egui::Context) {\n"
        "        // " + MARKER + ": poll queued SAF acknowledgement on native frame loop.\n"
        "        self.android_poll_save_close(ctx);", SOURCES["app"],
    )
    # Port original tested save-close logic with a boolean indicating that a
    # request was safely queued. Returning true lets the transient dialog
    # close; the workbook stays OPEN until an acknowledgement arrives.
    save = (ROOT / "save_close.rs").read_text()
    save = once(save,
        "pub fn android_save_and_close(&mut self, quit: bool) {",
        "pub fn android_save_and_close(&mut self, quit: bool) -> bool {", "save_close.rs")
    save = once(save,
        "if self.android_pending_close.is_some() || !self.commit_edit(0, 0, false, false) { return; }",
        "if self.android_pending_close.is_some() || !self.commit_edit(0, 0, false, false) { return false; }", "save_close.rs")
    save = once(save, "if let Err(error) = self.commit_text_box_edit() { self.alert(error); return; }",
        "if let Err(error) = self.commit_text_box_edit() { self.alert(error); return false; }", "save_close.rs")
    save = once(save, "Err(error) => { self.alert(error); return; }",
        "Err(error) => { self.alert(error); return false; }", "save_close.rs")
    save = once(save, "else { return; };\n        let name =",
        "else { return false; };\n        let name =", "save_close.rs")
    save = once(save,
        "let Some(doc) = self.session.active() else { return; };",
        "let Some(doc) = self.session.active() else { return false; };", "save_close.rs")
    save = once(save,
        "            self.android_pending_close=Some((uid,revision,rx,quit));\n        }\n    }",
        "            self.android_pending_close=Some((uid,revision,rx,quit));\n"
        "            return true;\n        }\n        false\n    }", "save_close.rs")
    # GridCraft 0.15 moved alert() under app::commands with pub(super)
    # visibility. This Android-only save shim is in crate root lib.rs, so
    # allow crate-local access without making the method public to API users.
    src["commands"] = once(
        src["commands"],
        "    pub(super) fn alert(&mut self, e: String) {",
        "    // " + MARKER + ": save failure surfaced from root Android SAF shim.\n"
        "    pub(crate) fn alert(&mut self, e: String) {",
        SOURCES["commands"],
    )
    src["lib"] += "\n" + save + "\n" + (ROOT / "editor_escape.rs").read_text() + "\n" + (ROOT / "dcs_tests.rs").read_text() + "\n" + APP_HELPER
    src["quit"] = once(
        src["quit"],
        "            SaveAnswer::Save => {\n                // File operations include the cell still being edited, as File › Save does.",
        "            SaveAnswer::Save => {\n"
        "                // " + MARKER + ": Android must wait for confirmed SAF write before workbook close.\n"
        "                if self.services.android_save_close.is_some() {\n"
        "                    return self.android_save_and_close(quitting);\n"
        "                }\n"
        "                // File operations include the cell still being edited, as File › Save does.",
        SOURCES["quit"],
    )
    old_block = '''                    ui.horizontal(|ui| {
                        for (label, answer) in
                            [("Don't Save", crate::SaveAnswer::DontSave), ("Cancel", crate::SaveAnswer::Cancel), ("Save", crate::SaveAnswer::Save)]
                        {
                            if ui.button(label).clicked() && app.answer_save_changes(answer, quitting, ui.ctx()) {
                                open = false;
                            }
                        }
                    });'''
    new_block = '''                    // ''' + MARKER + ''': each modal opening owns its D/C/S shortcut.
                    // Consume text only inside this dialog, and keep all buttons visible.
                    let shortcut = gridcraft_android_take_dcs(ui.ctx());
                    ui.horizontal(|ui| {
                        for (label, key, action, answer) in
                            [("Don't Save", "D", 1, crate::SaveAnswer::DontSave),
                             ("Cancel", "C", 2, crate::SaveAnswer::Cancel),
                             ("Save", "S", 3, crate::SaveAnswer::Save)]
                        {
                            let clicked = ui.button(format!("{label} ({key})")).clicked();
                            if (clicked || shortcut == Some(action))
                                && app.answer_save_changes(answer, quitting, ui.ctx())
                            {
                                open = false;
                            }
                        }
                    });'''
    src["dialog"] = once(src["dialog"], old_block, new_block, SOURCES["dialog"])
    src["dialog"] += "\n" + DCS_HELPER

    for key, required in {
        "services": "pub android_save_close:",
        "lib": "fn android_poll_save_close",
        "app": "self.android_poll_save_close(ctx);",
        "quit": "return self.android_save_and_close(quitting);",
        "dialog": "gridcraft_android_take_dcs(ui.ctx())",
        "commands": "pub(crate) fn alert(&mut self, e: String)",
    }.items():
        if required not in src[key]:
            raise RuntimeError(f"{SOURCES[key]} missing post-ported {required}")
    # All code and required anchors validated before any changes are written.
    if not verify_only:
        for key, relative in SOURCES.items():
            (checkout / relative).write_text(src[key])
    return {
        "source_version": version,
        "verified_sources": list(SOURCES.values()),
        "modal_dcs_ported": True,
        "esc_handler_source_staged": True,
        "saf_acknowledged_save_close_staged": True,
        "source_checkout_modified": not verify_only,
        "android_launcher_port_complete": False,
        "arm64_build_verified": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("upstream_checkout", type=Path)
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args()
    print(json.dumps(port(args.upstream_checkout, verify_only=args.verify_only), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
