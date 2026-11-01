#!/usr/bin/env python3
"""Regression contract for read-only Companion Phase 1 Android integration.

These tests are intentionally source-only: they cannot exercise a real Android
SAF provider, JNI runtime, egui keyboard focus, or signed in-place upgrades.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA_ROOT = ROOT / "adapters/photocraft/java/com/artcraft/photocraft"
ACTIVITY = (JAVA_ROOT / "PhotoCraftActivity.java").read_text(encoding="utf-8")
INSPECTOR = (JAVA_ROOT / "CompanionPluginCatalog.java").read_text(encoding="utf-8")
RUST_SHELL = (ROOT / "adapters/photocraft/src/lib.rs").read_text(encoding="utf-8")
RUST_UI = (ROOT / "adapters/photocraft/src/companion_catalog.rs").read_text(encoding="utf-8")
CARGO = (ROOT / "adapters/photocraft/Cargo.toml").read_text(encoding="utf-8")
PREPARE = (ROOT / "adapters/photocraft/prepare.sh").read_text(encoding="utf-8")


def method_slice(source: str, start: str, end: str) -> str:
    begin = source.find(start)
    finish = source.find(end, begin + len(start))
    if begin == -1 or finish == -1:
        raise AssertionError(f"Could not find ordered method boundaries: {start}, {end}")
    return source[begin:finish]


class CompanionAndroidPhase1Contract(unittest.TestCase):
    def test_distinct_saf_request_code_and_result_queue(self):
        for expression in (
            'REQ_OPEN = 0x5043;', 'REQ_SAVE = 0x5044;',
            'REQ_COMPANION = 0x5045;',
            'ConcurrentLinkedQueue<String> companionResults',
        ):
            self.assertIn(expression, ACTIVITY)

    def test_companion_picker_only_asks_for_read_permission(self):
        picker = method_slice(
            ACTIVITY, 'public void pcRequestCompanionPlugin(long id)',
            'private void rememberCompanionMetadata')
        self.assertIn('Intent.ACTION_OPEN_DOCUMENT', picker)
        self.assertIn('Intent.FLAG_GRANT_READ_URI_PERMISSION', picker)
        for forbidden in (
            'Intent.FLAG_GRANT_WRITE_URI_PERMISSION',
            'Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION',
            'takePersistableUriPermission',
            'Intent.EXTRA_ALLOW_MULTIPLE',
            'rememberUri',
        ):
            self.assertNotIn(forbidden, picker)

    def test_companion_result_never_uses_document_results(self):
        selected = method_slice(
            ACTIVITY, 'private void companionPicked(long id, Intent data)',
            'public void pcRequestOpen(long id, boolean multiple)')
        self.assertIn('CompanionPluginCatalog.inspect(stream)', selected)
        self.assertIn('companionResults.offer(result.toString())', selected)
        for forbidden in (
            'results.offer(', 'intentPaths.offer(', 'rememberUri(',
            'copyUriToFile(', 'newStageFile(', 'openOutputStream(',
            'takePersistableUriPermission(', 'startActivity(',
        ):
            self.assertNotIn(forbidden, selected)

    def test_extension_and_provider_size_gate_before_read(self):
        selected = method_slice(
            ACTIVITY, 'private void companionPicked(long id, Intent data)',
            'public void pcRequestOpen(long id, boolean multiple)')
        self.assertIn('endsWith(".pcpl")', selected)
        self.assertIn('OpenableColumns.SIZE', selected)
        self.assertIn('MAX_COMPANION_ARCHIVE_BYTES', selected)
        self.assertLess(selected.index('endsWith(".pcpl")'), selected.index('openInputStream(uri)'))

    def test_persistent_catalog_only_stores_metadata_fields(self):
        selected = method_slice(
            ACTIVITY, 'private void rememberCompanionMetadata(JSONObject plugin)',
            'private void enqueueCompanionError')
        for name in ('"id"', '"name"', '"version"', '"plugin_type"', '"catalog_status"'):
            self.assertIn(name, selected)
        for forbidden in (
            'uri.toString()', 'getBytes(', 'models', 'script', 'entrypoint',
            'commands', 'OutputStream', 'openFileOutput',
        ):
            self.assertNotIn(forbidden, selected)
        self.assertIn('MAX_COMPANION_ENTRIES', selected)

    def test_archive_does_not_extract_or_run_plugins(self):
        for forbidden in (
            'DexClassLoader', 'ProcessBuilder', 'Runtime.getRuntime',
            'Class.forName', 'HttpURLConnection',
            'ZipFile.extract', 'FileOutputStream', 'Files.copy',
        ):
            self.assertNotIn(forbidden, INSPECTOR)
        self.assertIn('ZipInputStream', INSPECTOR)
        self.assertIn('LimitedStream', INSPECTOR)
        self.assertIn('validateJson(', INSPECTOR)
        self.assertIn('Duplicate JSON key', INSPECTOR)

    def test_manifest_labels_execution_permanently_disabled(self):
        for line in (
            'metadata.put("catalog_status", "metadata_only")',
            'metadata.put("execution_enabled", false)',
            'metadata.put("installed", false)',
            'metadata.put("network_used", false)',
            'metadata.put("model_downloaded", false)',
        ):
            self.assertIn(line, INSPECTOR)

    def test_jni_interface_matches_java_methods(self):
        expected = (
            ('pcRequestCompanionPlugin', '(J)V'),
            ('pcCompanionPollResult', '()Ljava/lang/String;'),
            ('pcCompanionCatalogSnapshot', '()Ljava/lang/String;'),
        )
        for method, signature in expected:
            self.assertIn(f'jni_str!("{method}")', RUST_UI)
            self.assertIn(f'jni_sig!("{signature}")', RUST_UI)
            self.assertRegex(ACTIVITY, rf'public (?:String|void) {method}\(')

    def test_rust_ui_does_not_offer_execution(self):
        for label in (
            'metadata_only', 'Not installed · execution disabled',
            'Import .pcpl descriptor (SAF)',
            'Plugin metadata added. Execution remains disabled.',
        ):
            self.assertIn(label, RUST_UI)
        for forbidden in (
            'TcpListener', 'reqwest::', 'Command::new(',
            'std::process::Command', 'libloading::',
            'android_main(', 'Session::new(', 'inbox.push',
        ):
            self.assertNotIn(forbidden, RUST_UI)

    def test_editor_file_keyboard_gpu_behavior_kept(self):
        for marker in (
            'self.picker.poll(&self.bridge, ctx)',
            'drain_incoming(&self.bridge, &self.intent_inbox',
            'self.staged_prune_tick()',
            'self.inner.logic(ctx, frame)',
            'self.inner.ui(ui, _frame)',
            'apply_android_modifiers(&mut self.modifiers, raw)',
            'self.inner.raw_input_hook(ctx, raw)',
            'app.set_wgpu(rs)',
            'system_fonts::install_system_fonts(ui.ctx())',
        ):
            self.assertIn(marker, RUST_SHELL)
        self.assertIn('self.companion.poll(&self.bridge, ctx)', RUST_SHELL)
        self.assertIn('self.companion.show(ui.ctx(), &self.bridge)', RUST_SHELL)

    def test_launcher_and_signing_identity_untouched(self):
        self.assertIn('package = "com.artcraft.photocraft"', CARGO)
        self.assertIn('label = "PhotoCraft"', CARGO)
        self.assertIn('build_targets = ["aarch64-linux-android"]', CARGO)
        self.assertIn('icon = "@drawable/ic_launcher"', CARGO)
        self.assertNotIn('signing', CARGO.lower())

    def test_android_staging_copies_native_java_and_rust_sources(self):
        self.assertIn('cp -a "$ADAPTER/." "$DEST/"', PREPARE)
        self.assertIn('mod companion_catalog;', RUST_SHELL)
        self.assertIn('companion: companion_catalog::CompanionCatalog::default()', RUST_SHELL)

    def test_companion_overlay_is_opt_in_and_touch_accessible(self):
        self.assertIn('egui::Area::new(', RUST_UI)
        self.assertIn('egui::Window::new(', RUST_UI)
        self.assertIn('RIGHT_BOTTOM', RUST_UI)
        self.assertIn('if ui.button("Plugins · Preview").clicked()', RUST_UI)
        self.assertIn('self.open = !self.open', RUST_UI)
        self.assertIn('self.pending.is_none()', RUST_UI)
        self.assertIn('Some("cancel")', RUST_UI)
        self.assertIn('if self.pending.is_none()', RUST_UI)
        self.assertIn('!= self.pending', RUST_UI)
        self.assertIn('.order(egui::Order::Middle)', RUST_UI)


if __name__ == "__main__":
    unittest.main(verbosity=2)
