"""Source-only LightCraft v0.17 integration gate tests. No APK or Android build."""
import tempfile
import unittest
from pathlib import Path

from v017_compatibility import inspect


class V017AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.builder = self.root / "builder"
        self.write(self.source, "crates/ui-egui/src/app.rs",
                   "pub fn new(mut session: Session, services: Services)\n"
                   "pub fn logic(&mut self, ctx: &egui::Context)\n"
                   "pub fn ui(&mut self, ui: &mut egui::Ui)")
        self.write(self.source, "crates/ui-egui/src/services.rs",
                   "pub picker: Option<pick::Picker>\n"
                   "pub pick_files: Option<PickFiles>\n"
                   "pub pick_folder: Option<PickFolder>\n"
                   "pub write: Option<WriteFn>\n"
                   "pub write_new: Option<WriteFn>\n"
                   "pub write_shared: Option<SharedWrite>")
        self.write(self.source, "crates/ui-egui/src/menus/ui_commands.rs",
                   '"app.checkForUpdates"')
        self.write(self.source, "crates/ui-egui/src/menus/menubar.rs",
                   '"app.checkForUpdates", "app.about"')
        self.write(self.source, "crates/ui-egui/src/dialogs/updates_ui.rs",
                   "craft_update")
        self.write(self.builder, "lib/build-common.sh",
                   '"lightcraft": { fn saf_write_and_commit( '
                   "PickKind::Files PickKind::Save picker: Some( write: Some( scrolling.sh")
        self.write(self.builder, "lib/scrolling.sh", "# read-only test fixture")

    @staticmethod
    def write(root, name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def test_source_contract_not_release_permission(self):
        report = inspect(self.source, self.builder)
        self.assertTrue(report["all_source_contracts_present"])
        self.assertTrue(all(report["checks"].values()))
        for field in ("v017_android_port_complete", "arm64_apk_built",
                      "production_signing_performed", "device_verified",
                      "release_authorized", "legacy_v011_ui_patch_compatible"):
            self.assertIs(report[field], False, field)
        self.assertTrue(report["release_blockers"])

    def test_missing_atomic_writer_is_reported_not_ignored(self):
        self.write(self.source, "crates/ui-egui/src/services.rs",
                   "pub picker: Option<pick::Picker>\n"
                   "pub pick_files: Option<PickFiles>\n"
                   "pub pick_folder: Option<PickFolder>\n"
                   "pub write: Option<WriteFn>\n"
                   "pub write_shared: Option<SharedWrite>")
        report = inspect(self.source, self.builder)
        self.assertFalse(report["checks"]["new_atomic_write_api"])
        self.assertFalse(report["all_source_contracts_present"])

    def test_legacy_ui_layout_is_not_mistaken_for_v017(self):
        self.write(self.source, "crates/ui-egui/src/panels/dialogs.rs", "")
        self.write(self.source, "crates/ui-egui/src/menubar.rs", "")
        self.assertFalse(inspect(self.source, self.builder)["all_source_contracts_present"])


if __name__ == "__main__":
    unittest.main()
