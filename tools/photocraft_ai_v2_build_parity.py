#!/usr/bin/env python3
"""Read-only source parity guard for the accepted PhotoCraft V2 android.4 build.

The owner rejected android.5 on a real HONOR tablet because Ctrl+W stopped
responding. This checks *build recipe* invariants and blocks accidental
reactivation of that rejected recipe. It does not claim to reproduce or fix
the on-device keyboard bug. Never builds, signs, installs or publishes APKs.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT / ".github/workflows/photocraft-ai-v2-fontscan-android4-unsigned.yml"
REJECTED = ROOT / ".github/workflows/photocraft-ai-v2-candidate-unsigned.yml"
OBSOLETE_PROOF = ROOT / ".github/workflows/photocraft-ai-production-dryrun.yml"
AI_PREVIEW_WORKFLOW = ROOT / ".github/workflows/photocraft-ai-menu-pr93-test.yml"
AI_MENU = ROOT / "adapters/photocraft/src/ai_menu.rs"
JAVA_ACTIVITY = ROOT / "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java"
AI_STAGE = ROOT / "tools/photocraft_ai_preview_stage.py"
STABLE_STAGE = ROOT / "tools/photocraft_ai_v2_fontscan_android4_stage.py"
REJECTED_STAGE = ROOT / "tools/photocraft_ai_v2_candidate_stage.py"
WINDOW_PATCH = ROOT / "tools/photocraft_ai_window_patch.py"
BASELINE = "f708fff8a333c2246b6d342570b19db5b95f4be1"

COMMON = (
    f'BASE="{BASELINE}"',
    "python3 tools/keyboard/escape_focus_check.py photocraft",
    "cp tools/photocraft_ai_preview_stage.py",
    "cp tools/photocraft_ai_window_patch.py",
    'python3 "$RUNNER_TEMP/pr93-ai/window_patch.py" source/photocraft/crates/ui-egui/src/menus.rs',
    "artcraft_discard_prompt_owns_keyboard",
)
FONT_PARITY = (
    "cp tools/photocraft_ai_fontscan_4g_stage.py",
    'python3 "$RUNNER_TEMP/pr93-ai/fontscan_stage.py" "$GITHUB_WORKSPACE"',
    "FONT_SCAN_MAX_BYTES = 4L * 1024 * 1024 * 1024",
    "FONT_SCAN_MAX_FILES = 5000",
    "register_font_paths(",
)
REJECTED_GUARDS = (
    "if: ${{ false }}",
    "OWNER_REJECTED_VERSION, OWNER_REJECTED_CODE",
    "STOP: owner rejected android.5 on device",
)


def require(text: str, needles: tuple[str, ...], label: str) -> None:
    for needle in needles:
        if needle not in text:
            raise ValueError(f"{label}: missing source-only parity guard: {needle}")


def require_archived_single_job(text: str, label: str) -> None:
    """Fail closed if an archived workflow gains an unguarded second job.

    An arbitrary 'if: false' string is insufficient: a later active job,
    or a second job-level if, could still compile an unwanted APK.
    Only the exact one-job, one-false-guard shape is allowed.
    """
    if len(re.findall(r"(?m)^jobs:\s*$", text)) != 1:
        raise ValueError(f"{label}: missing or duplicate jobs block")
    jobs = text.split("\njobs:\n", 1)
    if len(jobs) != 2:
        raise ValueError(f"{label}: jobs block must use explicit YAML lines")
    block = jobs[1]
    names = re.findall(r"(?m)^  ([A-Za-z0-9_-]+):[ \t]*$", block)
    if names != ["arm64-preview"]:
        raise ValueError(f"{label}: expected only archived arm64-preview job, got {names}")
    guards = re.findall(r"(?m)^    if:[ \t]*(.*?)[ \t]*$", block)
    if guards != ["${{ false }}"]:
        raise ValueError(f"{label}: archived job must have one exact false guard, got {guards}")


def archived_ai_preview_recipe(text: str) -> None:
    """Owner-tested preview must not auto-build after ordinary PR93 edits."""
    require_archived_single_job(text, "archived AI preview")
    if "  push:" in text or "  workflow_dispatch:" not in text:
        raise ValueError("AI preview must be manual-only and owner-gated")
    require(text, (
        "if: ${{ false }}", "cancel-in-progress: false",
        "package: name='com.artcraft.photocraft.ai.preview'",
        "path: candidate/",
        "icon-verification/verification.json",
        "rm -f output/*.apk icon-verification/*.apk candidate/*.apk",
    ), "archived AI preview")
    # The preview artifact is allowed ONLY for its separate package identity.
    # The failure-diagnostics path must not recursively upload an APK copied
    # by verify_apk.py into icon-verification/.
    if re.search(r"(?m)^\s+icon-verification/\s*$", text):
        raise ValueError("preview failure diagnostics may expose disposable APK copies")


def accepted_recipe(text: str) -> None:
    require_archived_single_job(text, "accepted android.4 recipe")
    require(text, COMMON + FONT_PARITY + ("if: ${{ false }}",), "accepted android.4 recipe")
    # The exact historical recipe is retained for comparison, but must never
    # spend CI minutes rebuilding an already-published stable version.
    if "if: github.repository == 'KosmosSG/artcraft-android' && github.ref" in text:
        raise ValueError("historical android.4 ARM64 build must stay archived")


def rejected_recipe(text: str) -> None:
    require_archived_single_job(text, "rejected android.5 recipe")
    require(text, COMMON + REJECTED_GUARDS, "rejected android.5 recipe")
    # This old workflow intentionally omitted the 4 GiB font-scan overlay.
    # It is NOT a feature-parity template for future builds, even if someone
    # fixes the version string. Only the archived/no-build state is accepted.
    if 'PROPOSED_VERSION == "0.14.0-android.5"' in text:
        raise ValueError("Unexpected candidate self-test copied into workflow")


def obsolete_proof_recipe(text: str) -> None:
    require_archived_single_job(text, "obsolete android.2 proof")
    # Old original-certificate android.2 proof is below published V2 android.4.
    # verify_apk.py copies a disposable-signed APK into icon-verification;
    # only JSON may be uploaded, and cleanup must remove that copied APK.
    require(text, (
        "if: ${{ false }}",
        "rm -rf icon-verification/",
        "rm -f keys/artcraft-builder.jks keys/.keystore-password output/*.apk",
        "path: candidate-proof/production-identity-build-proof.json",
    ), "obsolete android.2 proof")
    if "path: |\\n            logs/\\n            icon-verification/" in text:
        raise ValueError("obsolete proof would upload disposable APK in failure diagnostics")


# Ctrl+W is a proven owner-device regression in android.5, not a proven
# keyboard-routing root cause. Protect the overlay's source boundary without
# claiming that static checks can reproduce a physical keyboard or IME.
KEY_INTERCEPTORS = (
    "consume_key(", "consume_shortcut(", "raw.events.clear(",
    "Key::W", "KeyCode::W", "KEYCODE_W", "dispatchKeyEvent(",
    "apply_android_modifiers(", "raw_input_hook(",
)


def ai_keyboard_boundary(menu: str, stage: str, window_patch: str) -> None:
    require(stage, (
        "artcraft_discard_prompt_owns_keyboard",
        "artcraft_finish_type_escape",
        "mod android_modifiers;",
        "self.ai_menu.show(ui, &mut self.inner.session)",
    ), "PR93 AI staging keyboard boundary")
    for name, source in (("AI menu", menu), ("Window AI toggle", window_patch)):
        for token in KEY_INTERCEPTORS:
            if token in source:
                raise ValueError(f"{name} may intercept Ctrl+W/keyboard routing: {token}")


def java_hardware_key_passthrough(activity: str) -> None:
    """Preserve accepted Android.4 physical-key pass-through into native winit.

    The 1-pixel IME host is for soft-keyboard text. Consuming hardware
    onKeyDown/onKeyUp here would prevent native Ctrl+W and other shortcuts.
    This checks Java source only; real HONOR keyboard acceptance is separate.
    """
    for name in ("onKeyDown", "onKeyUp"):
        pattern = (
            rf"(?s)@Override\\s+public boolean {name}"
            rf"\\(int keyCode, KeyEvent event\\)\\s*\\{{(.*?)\\n\\s*\\}}"
        )
        matches = list(re.finditer(pattern, activity))
        if len(matches) != 1:
            raise ValueError(f"PhotoCraft IME host: missing/duplicate {name}")
        body = matches[0].group(1)
        statements = [
            line.strip() for line in body.splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        if statements != ["return false;"]:
            raise ValueError(f"PhotoCraft IME host must not consume physical {name}")


def ai_hidden_consent_boundary(menu: str) -> None:
    """Hide must revoke the temporary token, consent and pending dialog.

    This is a source-only privacy regression gate, not a device lifecycle
    test. Never claim that it proves Android foreground/background behavior.
    """
    marker = "if !photocraft_ui_egui::menus::artcraft_ai_tools_visible() {"
    if menu.count(marker) != 1 or "        let layer_changed" not in menu:
        raise ValueError("AI visibility transition anchor changed")
    hidden = menu.split(marker, 1)[1].split("        let layer_changed", 1)[0]
    actions = (
        "self.cancel_cpu_job();",
        "self.cpu_consent = false;",
        "self.cpu_token.clear();",
        "self.show_background_setup = false;",
    )
    positions = [hidden.find(action) for action in actions]
    if -1 in positions or positions != sorted(positions):
        raise ValueError("Hiding AI Tools must cancel, revoke consent/token and close dialog")



def ai_one_shot_token_boundary(menu: str) -> None:
    """A per-image consent token must not linger in the dialog after Start.

    Moving the token into the one background worker preserves local inference
    while requiring fresh entry for a later image. This source-only check does
    not claim to erase worker memory before the request completes.
    """
    if menu.count("    fn start_cpu_job(") != 1 or menu.count("    fn poll_cpu_result(") != 1:
        raise ValueError("AI background worker anchors changed")
    start = menu.split("    fn start_cpu_job(", 1)[1].split("    fn poll_cpu_result(", 1)[0]
    move = "let token = std::mem::take(&mut self.cpu_token);"
    # Snapshot validation can fail before any worker starts. A token must
    # already have left the editable UI on that early-error path as well.
    anchors = (move, "ai_background_editor::active_snapshot(session)",
               "std::thread::spawn(move ||")
    positions = [start.find(anchor) for anchor in anchors]
    if (start.count(move) != 1 or "self.cpu_token.clone()" in start or
        -1 in positions or positions != sorted(positions)):
        raise ValueError("AI token must be consumed before snapshot and worker start")




def ai_local_backend_disclosure(menu: str) -> None:
    """Do not tell users the separately enabled U2NetP tool is unavailable.

    ComfyUI image generation remains unconnected; the local U2NetP route
    requires per-image consent. This is a UI-text check, not a device test.
    """
    require(menu, (
        'ui.button("Remove Background · Local CPU Preview…")',
        'ui.checkbox(&mut self.cpu_consent,',
        'ui.label("Experimental: only a local Linux Lab server at 127.0.0.1:18793 is accepted.")',
        'ui.label("ComfyUI image generation and Generative Fill are not connected. Local U2NetP Background Removal is available only from AI Tools with per-image consent.");',
    ), "AI UI backend disclosure")
    if "Background Removal and Generative Fill remain disabled" in menu:
        raise ValueError("AI UI incorrectly says the available local background tool is disabled")


def stage_transform_parity(stable: str, rejected: str) -> None:
    """Guard actual staging operations shared by accepted .4 and rejected .5.

    This excludes an observed staging-script keyboard-patch difference; it
    does not reproduce Ctrl+W on the owner's Android hardware or rule out
    different packaging, fonts, focus state, or input-method behavior.
    """
    require(stable, ('PROPOSED_VERSION = "0.14.0-android.4"',
                     'record["version_code"] = 16790007'), "android.4 stage identity")
    require(rejected, ('PROPOSED_VERSION = "0.14.0-android.5"',
                       'PROPOSED_CODE = 16790008',
                       'V2_STABLE_CODE = 16790007'), "android.5 stage identity")

    def normalized_stage(source: str) -> str:
        start, end = "def stage(root: Path) -> None:", "def self_test() -> None:"
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("Stage function boundaries changed")
        body = source.split(start, 1)[1].split(end, 1)[0]
        lines = []
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith(("#", "print(")):
                continue
            line = line.replace("0.14.0-android.4", "0.14.0-android.CANDIDATE")
            line = line.replace("0.14.0-android.5", "0.14.0-android.CANDIDATE")
            line = line.replace('record["version_code"] = 16790007',
                                'record["version_code"] = PROPOSED_CODE')
            lines.append(line)
        return "\n".join(lines)

    if normalized_stage(stable) != normalized_stage(rejected):
        raise ValueError("Android.5 stage transformations diverge from accepted Android.4")


def self_test() -> None:
    stable = ACCEPTED.read_text(encoding="utf-8")
    rejected = REJECTED.read_text(encoding="utf-8")
    obsolete = OBSOLETE_PROOF.read_text(encoding="utf-8")
    ai_preview = AI_PREVIEW_WORKFLOW.read_text(encoding="utf-8")
    ai_menu = AI_MENU.read_text(encoding="utf-8")
    java_activity = JAVA_ACTIVITY.read_text(encoding="utf-8")
    ai_stage = AI_STAGE.read_text(encoding="utf-8")
    window_patch = WINDOW_PATCH.read_text(encoding="utf-8")
    stable_stage = STABLE_STAGE.read_text(encoding="utf-8")
    rejected_stage = REJECTED_STAGE.read_text(encoding="utf-8")
    accepted_recipe(stable)
    rejected_recipe(rejected)
    obsolete_proof_recipe(obsolete)
    archived_ai_preview_recipe(ai_preview)
    ai_keyboard_boundary(ai_menu, ai_stage, window_patch)
    java_hardware_key_passthrough(java_activity)
    ai_hidden_consent_boundary(ai_menu)
    ai_one_shot_token_boundary(ai_menu)
    ai_local_backend_disclosure(ai_menu)
    stage_transform_parity(stable_stage, rejected_stage)

    mutations = (
        (lambda text: stage_transform_parity(stable_stage, text),
         rejected_stage.replace("build_text = exactly(build_text, guard, replacement)",
                                "build_text = build_text.replace(guard, replacement)", 1),
         "android.5 staging bypasses checked builder anchor"),
        (lambda text: stage_transform_parity(stable_stage, text),
         rejected_stage.replace("setup = exactly(setup, selector,",
                                "setup = setup.replace(selector,", 1),
         "android.5 staging bypasses checked prepare anchor"),
        (archived_ai_preview_recipe, ai_preview.replace("    if: ${{ false }}", "    if: ${{ true }}", 1), "preview ARM64 job reenabled"),
        (archived_ai_preview_recipe, ai_preview.replace("  workflow_dispatch:", "  push:\\n  workflow_dispatch:", 1), "preview push trigger restored"),
        (archived_ai_preview_recipe, ai_preview.replace("cancel-in-progress: false", "cancel-in-progress: true", 1), "preview run cancellation restored"),
        (archived_ai_preview_recipe, ai_preview.replace("            icon-verification/verification.json\n          if-no-files-found: ignore", "            icon-verification/\n          if-no-files-found: ignore", 1), "preview failure upload includes disposable APK"),
        (archived_ai_preview_recipe, ai_preview.replace("rm -f output/*.apk icon-verification/*.apk candidate/*.apk", "", 1), "preview disposable APK copies retained"),
        (archived_ai_preview_recipe, ai_preview.replace("package: name='com.artcraft.photocraft.ai.preview'", "package: name='com.artcraft.photocraft'", 1), "preview production package identity substitution"),
        (accepted_recipe, stable.replace(FONT_PARITY[0], "", 1), "missing font scanner"),
        (accepted_recipe, stable.replace(FONT_PARITY[1], "", 1), "font scanner not applied"),
        (accepted_recipe, stable.replace(FONT_PARITY[3], "", 1), "font file count missing"),
        (accepted_recipe, stable.replace(COMMON[0], 'BASE="unreviewed"', 1), "keyboard baseline changed"),
        (accepted_recipe, stable.replace(COMMON[1], ""), "keyboard focus check missing"),
        (accepted_recipe, stable.replace("if: ${{ false }}", "if: ${{ true }}", 1), "stable android.4 rebuild reenabled"),
        (rejected_recipe, rejected.replace(REJECTED_GUARDS[0], "if: ${{ true }}", 1), "android.5 reenabled"),
        (rejected_recipe, rejected.replace(REJECTED_GUARDS[2], "", 1), "android.5 rejection missing"),
        (obsolete_proof_recipe, obsolete.replace("if: ${{ false }}", "if: ${{ true }}", 1), "obsolete proof reenabled"),
        (obsolete_proof_recipe, obsolete.replace("rm -rf icon-verification/", "", 1), "disposable APK copy not cleaned"),
        (obsolete_proof_recipe, obsolete.replace("path: candidate-proof/production-identity-build-proof.json", "path: icon-verification/", 1), "unsafe artifact path"),
        (accepted_recipe, stable + "\n  accidental-arm64:\n    runs-on: ubuntu-24.04\n    steps: []\n", "extra unguarded stable job"),
        (rejected_recipe, rejected.replace("    if: ${{ false }}", "    if: ${{ false }}\n    if: ${{ true }}", 1), "second job-level if bypasses rejection"),
        (obsolete_proof_recipe, obsolete.replace("    if: ${{ false }}", "      if: ${{ false }}", 1), "disabled condition moved to a step"),
        (lambda text: ai_hidden_consent_boundary(text), ai_menu.replace("self.cpu_token.clear();", "", 1), "hidden AI menu retained bearer token"),
        (lambda text: ai_hidden_consent_boundary(text), ai_menu.replace("self.show_background_setup = false;", "", 1), "hidden AI dialog could reopen"),
        (lambda text: ai_hidden_consent_boundary(text), ai_menu.replace("self.cpu_consent = false;", "", 1), "hidden AI menu retained consent"),
        (ai_one_shot_token_boundary, ai_menu.replace("let token = std::mem::take(&mut self.cpu_token);", "let token = self.cpu_token.clone();", 1), "one-use token retained in dialog after Start"),
        (ai_one_shot_token_boundary, ai_menu.replace(
            "let token = std::mem::take(&mut self.cpu_token);\n        let (document, origin)",
            "let (document, origin)", 1).replace(
            "Err(error) => { self.cpu_status = error; return; }\n        };",
            "Err(error) => { self.cpu_status = error; return; }\n        };\n        let token = std::mem::take(&mut self.cpu_token);", 1),
         "snapshot error retains token in editable dialog"),
        (ai_local_backend_disclosure, ai_menu.replace(
            'ComfyUI image generation and Generative Fill are not connected. Local U2NetP Background Removal is available only from AI Tools with per-image consent.',
            'Background Removal and Generative Fill remain disabled until non-destructive layer integration is verified.', 1),
         "local U2NetP feature incorrectly marked disabled"),
        (ai_local_backend_disclosure, ai_menu.replace(
            'ui.checkbox(&mut self.cpu_consent,', 'ui.label("No consent needed");', 1),
         "local U2NetP consent disclosure removed"),
        (lambda text: ai_keyboard_boundary(text, ai_stage, window_patch), ai_menu + "\\nconsume_key(", "AI menu key interception"),
        (lambda text: ai_keyboard_boundary(ai_menu, text, window_patch), ai_stage.replace("artcraft_discard_prompt_owns_keyboard", "", 1), "discard keyboard guard missing"),
        (lambda text: ai_keyboard_boundary(ai_menu, ai_stage, text), window_patch + "\\nKey::W", "Window menu W interception"),
        (java_hardware_key_passthrough, java_activity.replace("return false;", "return true;", 1), "IME host consumes physical key down"),
        (java_hardware_key_passthrough, java_activity.replace("onKeyUp(int keyCode", "onKeyLost(int keyCode", 1), "IME host key-up override removed"),
        (java_hardware_key_passthrough, java_activity.replace("return false;", "event.getKeyCode();\\n                    return false;", 1), "IME host adds hardware-key side effect"),
    )
    for validator, mutated, reason in mutations:
        try:
            validator(mutated)
        except ValueError:
            continue
        raise AssertionError("Fail-open source parity regression: " + reason)

    print("PASS: accepted android.4 recipe retains pinned keyboard, AI and 4 GiB/5000-font overlay")
    print("PASS: historical android.4 and rejected android.5 workflows remain disabled; thirty-three negative mutations rejected")
    print("PASS: owner-tested isolated AI Preview ARM64 workflow is archived, no automatic builds")
    print("PASS: obsolete android.2 proof is disabled and cannot upload its disposable APK copy")
    print("PASS: hiding AI Tools revokes ephemeral token, consent and pending dialog (source-only)")
    print("PASS: starting AI processing consumes the one-use UI token without retaining a dialog copy")
    print("PASS: ComfyUI and local U2NetP availability/consent disclosures match actual UI wiring")
    print("PASS: PR93 AI overlay and Java IME host preserve physical-key passthrough; owner hardware retest still required")
    print("PASS: accepted .4 and rejected .5 source transforms match apart from version metadata; two mutations rejected")
    print("NOT PROVEN: Ctrl+W runtime root cause, in-place data preservation, or a future candidate")


if __name__ == "__main__":
    self_test()
