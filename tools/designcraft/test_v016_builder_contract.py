#!/usr/bin/env python3
"""Source-only regression checks for the DesignCraft v0.16 Android review branch.

These checks inspect source contracts; they do NOT prove an APK has built or that
features work on an Android device. Production publication remains a separate gate.
"""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "lib" / "build-common.sh"
LOCK = ROOT / "configs" / "upstream" / "designcraft-v016.json"


class DesignCraftV016SourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = BUILDER.read_text(encoding="utf-8")
        cls.lock = json.loads(LOCK.read_text(encoding="utf-8"))

    def test_stable_upstream_lock(self):
        self.assertEqual(self.lock["schema_version"], 1)
        self.assertEqual(self.lock["official_upstream"], "storytold/designcraft")
        self.assertEqual(self.lock["stable_tag"], "v0.16.0")
        self.assertEqual(self.lock["upstream_workspace_version"], "0.16.0")
        self.assertRegex(self.lock["tag_commit"], r"^[a-f0-9]{40}$")
        self.assertFalse(self.lock["android_source_port_complete"])
        self.assertFalse(self.lock["android_build_verified"])
        self.assertFalse(self.lock["permanent_signing_authorized"])
        self.assertFalse(self.lock["production_release_authorized"])

    def test_pinned_checkout_does_not_overwrite_existing_sources(self):
        self.assertIn('git clone --depth 1 --branch v0.16.0 "$REPO" "$SRC"', self.shell)
        self.assertIn('ACTUAL_SOURCE_SHA', self.shell)
        self.assertIn('"$DESIGNCRAFT_LOCKED_COMMIT"', self.shell)
        self.assertIn("Preserve it: run this in a separate clean builder checkout", self.shell)
        self.assertIn('echo "Source is not automatically reset or updated."', self.shell)

    def test_review_build_is_debug_only(self):
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true && "$APP" != "designcraft" ]]', self.shell)
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true && "$MODE" != "debug" ]]', self.shell)
        self.assertIn("production/release signing is blocked", self.shell)

    def test_recovery_persisted_per_designcraft_instance(self):
        self.assertIn('let recovery_root = dir.join("Recovery");', self.shell)
        self.assertIn('inner.session.recovery_dir = Some(run_dir);', self.shell)
        self.assertIn('"file.recovery.open"', self.shell)
        self.assertIn('"file.recovery.save"', self.shell)
        self.assertIn('inner.session.documents().iter().any(|d| d.is_dirty())', self.shell)

    def test_existing_android_behaviors_remain_in_source(self):
        activity = (ROOT / "templates" / "android" / "SafActivity.java").read_text()
        self.assertIn("private File newStageFile(String name, Uri uri)", activity)
        self.assertIn('stem + " (" + attempt + ")" + extension', activity)
        self.assertIn('com.artcraft.', self.shell)
        self.assertIn('designcraft deckcraft gridcraft', self.shell)
        self.assertIn('"designcraft": {', self.shell)
        self.assertTrue((ROOT / "templates" / "android" / "ime_bridge.rs").is_file())
        self.assertTrue((ROOT / "templates" / "android" / "system_fonts.rs").is_file())

    def test_egui_v037_uses_pinned_compatible_winit_fork(self):
        # The suite's older vendored 0.30.13 winit is NOT compatible with
        # official v0.16's custom egui-winit IME-reset event and window API.
        # The pinned fork is verified before selectively restoring mouse input.
        self.assertIn('DESIGNCRAFT_WINIT_REV="a517b3846ee8457d84ee4975110bfda6797c44dc"', self.shell)
        self.assertIn("grep -q 'ImeResetCompleted'", self.shell)
        self.assertIn("grep -q 'reset_ime_with_request'", self.shell)
        self.assertIn('overlay_winit_android_mouse.py', self.shell)
        overlay = (ROOT / "tools" / "designcraft" / "overlay_winit_android_mouse.py").read_text()
        self.assertIn("MotionAction::Scroll", overlay)
        self.assertIn("MotionAction::HoverMove", overlay)
        self.assertIn("target = target[:x] + motion + target[y:]", overlay)

    def test_overlay_accepts_official_android_ime_reset_hook(self):
        # Official Storytold winit deliberately implements this on Android.
        # The helper must keep it, not reject the pinned source at preparation.
        overlay = (ROOT / "tools" / "designcraft" / "overlay_winit_android_mouse.py").read_text()
        self.assertIn('if "pub fn reset_ime_with_request" not in target:', overlay)
        self.assertNotIn('if "pub fn reset_ime_with_request" in target:', overlay)
        self.assertIn("Pinned Storytold Android IME reset hook was lost", overlay)

    def test_designcraft_shell_is_constructed_by_eframe_app_creator(self):
        # eframe 0.37 manages Resumed/Suspended internally. Its AppCreator
        # runs on the first Resumed; our launcher must not construct UI early.
        self.assertIn('if saf and app == "designcraft":', self.shell)
        self.assertIn('Called from eframe\'s first Resumed', self.shell)
        self.assertIn("let shell = AndroidShell::new(", self.shell)
        self.assertIn("Box::new(move |cc| {{", self.shell)
        self.assertIn('GENERATOR_VERSION = "25" if app == "designcraft" else "24"', self.shell)

    def test_raw_input_hook_matches_v016_egui_context_signature(self):
        # DesignCraft v0.16's public raw-input method takes (ctx, raw).
        # Older apps may still have the one-argument method: do not break
        # their generated launchers when fixing DesignCraft.
        self.assertIn('raw_hook_has_ctx = bool(re.search(', self.shell)
        self.assertIn('"self.inner.raw_input_hook(ctx, raw);"', self.shell)
        self.assertIn('"let _ = ctx;\\n        self.inner.raw_input_hook(raw);"', self.shell)
        # This conditional is the exact v0.16 ARM64 compile regression fix.
        self.assertIn("if raw_hook_has_ctx", self.shell)

    def test_debug_ci_compiles_only_on_opt_in_and_never_publishes(self):
        workflow = (ROOT / ".github" / "workflows" / "designcraft-v016-review.yml").read_text()
        self.assertIn("[designcraft-debug]", workflow)
        self.assertIn("bash build-debug.sh -designcraft -designcraft-v016", workflow)
        self.assertIn("UNVERIFIED-DesignCraft-v0.16.0-android.4-DEBUG-arm64-not-for-updates", workflow)
        self.assertIn("retention-days: 3", workflow)
        self.assertNotIn("actions/create-release", workflow)
        self.assertNotIn("softprops/action-gh-release", workflow)
        self.assertNotIn("secrets.", workflow)

    def test_android_graphics_start_is_deferred_to_first_resumed(self):
        # A native Android window is unavailable before Resumed. The pinned
        # eframe renderer owns Suspended/Resumed surface lifecycle, while the
        # DesignCraft shell is created only by its AppCreator callback.
        marker = '    if saf and app == "designcraft":'
        self.assertEqual(self.shell.count(marker), 1)
        entry = self.shell.split(marker, 1)[1].split("    elif saf:", 1)[0]
        self.assertIn("android_app: Some(android_app)", entry)
        self.assertIn("eframe::run_native(", entry)
        creator = entry.index("        Box::new(move |cc| {{")
        constructed = entry.index("            {inner_decl} = {construct_expr};")
        self.assertLess(creator, constructed)
        self.assertIn("let shell = AndroidShell::new(", entry)
        self.assertNotIn("native_window()", entry)
        self.assertNotIn("wgpu::Surface", entry)

    def test_v016_device_reported_android_parity_staged(self):
        # Run only source/contract checks here; no Android build or signing.
        import ast
        stage = ROOT / "tools" / "designcraft" / "patch_v016_android.py"
        source = stage.read_text()
        ast.parse(source, filename=str(stage))
        font_ui = (ROOT / "tools" / "designcraft" / "v016_android.rs").read_text()
        self.assertIn('python3 "$ROOT/tools/designcraft/patch_v016_android.py"', self.shell)
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true ]]', self.shell)
        self.assertIn('ui_brand(src, "designcraft")', source)
        self.assertIn('approved_branding.check_assets()', source)
        self.assertIn('icon = "@mipmap/ic_launcher"', source)
        self.assertIn('android.permission.INTERNET', source)
        self.assertIn('"ui:app.artcraftImportFont"', source)
        self.assertIn("take_android_font_import", source)
        self.assertIn('"closeDocument" && result.is_none()', source)
        self.assertIn('egui::Key::D', source)
        self.assertIn('egui::Key::C', source)
        self.assertIn('egui::Key::S', source)
        self.assertIn('crates/fonts/src/fontdb/system.rs', source)
        self.assertIn('v016_android::accept_font(&name, &bytes)', source)
        self.assertIn('pub fn ui(', font_ui)
        self.assertIn('fn request_import(', font_ui)
        self.assertIn('font.reload', font_ui)
        self.assertIn('TTF/OTF/TTC', font_ui)
        self.assertIn('std::fs::OpenOptions::new().write(true).create_new(true)', font_ui)

    def test_device_candidate_version_and_size_controls(self):
        stage = (ROOT / "tools" / "designcraft" / "patch_v016_android.py").read_text()
        self.assertIn('candidate_version = "0.16.0-android.4"', stage)
        self.assertIn('let cargo-apk2 calculate the integer code', stage)
        self.assertNotIn('version_code = 16900001', stage)
        self.assertIn('apk_name = "designcraft-', stage)
        self.assertIn('APP_VERSION="0.16.0-android.4"', self.shell)
        self.assertIn('export CARGO_PROFILE_DEV_DEBUG=0', self.shell)
        self.assertIn('export CARGO_PROFILE_DEV_STRIP=debuginfo', self.shell)
        self.assertIn('export CARGO_PROFILE_DEV_OPT_LEVEL=s', self.shell)
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true ]]; then', self.shell)
        self.assertIn('approved_branding.check_assets()', stage)
        self.assertIn('android.permission.INTERNET', stage)

    def test_source_review_cannot_claim_publication(self):
        self.assertFalse(self.lock.get("production_release_authorized", False))
        self.assertFalse(self.lock.get("permanent_signing_authorized", False))

    def test_indirect_designcraft_dialog_dependency_has_android_backend(self):
        # DesignCraft v0.16 imports craft-dialogs, which imports rfd indirectly:
        # the old source-grep-only guard missed it and ARM64 compilation failed.
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true ]] || grep -rqE', self.shell)
        self.assertIn('cp -a "$ROOT/vendor/rfd" "$SRC/vendor/rfd"', self.shell)
        backend = (ROOT / "vendor" / "rfd" / "src" / "backend.rs").read_text()
        self.assertIn('#[cfg(target_os = "android")]', backend)
        self.assertIn('mod android;', backend)


if __name__ == "__main__":
    unittest.main()
