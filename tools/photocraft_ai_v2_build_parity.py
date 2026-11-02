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
AI_MENU = ROOT / "adapters/photocraft/src/ai_menu.rs"
AI_STAGE = ROOT / "tools/photocraft_ai_preview_stage.py"
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


def self_test() -> None:
    stable = ACCEPTED.read_text(encoding="utf-8")
    rejected = REJECTED.read_text(encoding="utf-8")
    obsolete = OBSOLETE_PROOF.read_text(encoding="utf-8")
    ai_menu = AI_MENU.read_text(encoding="utf-8")
    ai_stage = AI_STAGE.read_text(encoding="utf-8")
    window_patch = WINDOW_PATCH.read_text(encoding="utf-8")
    accepted_recipe(stable)
    rejected_recipe(rejected)
    obsolete_proof_recipe(obsolete)
    ai_keyboard_boundary(ai_menu, ai_stage, window_patch)

    mutations = (
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
        (lambda text: ai_keyboard_boundary(text, ai_stage, window_patch), ai_menu + "\\nconsume_key(", "AI menu key interception"),
        (lambda text: ai_keyboard_boundary(ai_menu, text, window_patch), ai_stage.replace("artcraft_discard_prompt_owns_keyboard", "", 1), "discard keyboard guard missing"),
        (lambda text: ai_keyboard_boundary(ai_menu, ai_stage, text), window_patch + "\\nKey::W", "Window menu W interception"),
    )
    for validator, mutated, reason in mutations:
        try:
            validator(mutated)
        except ValueError:
            continue
        raise AssertionError("Fail-open source parity regression: " + reason)

    print("PASS: accepted android.4 recipe retains pinned keyboard, AI and 4 GiB/5000-font overlay")
    print("PASS: historical android.4 and rejected android.5 workflows remain disabled; seventeen negative mutations rejected")
    print("PASS: obsolete android.2 proof is disabled and cannot upload its disposable APK copy")
    print("PASS: PR93 AI overlay does not add Ctrl+W key interception; owner hardware retest still required")
    print("NOT PROVEN: Ctrl+W runtime root cause, in-place data preservation, or a future candidate")


if __name__ == "__main__":
    self_test()
