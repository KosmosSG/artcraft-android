#!/usr/bin/env python3
"""Fail-closed PhotoCraft v0.14.0 Android source preparation; NO APK or signing."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/photocraft-v0.14.0-android.1.json"
SOURCE = ROOT / "source/photocraft"
EXPECTED_SHA = "ff4738810134d7f7e68b49f2e4f231b686282ff3"
EXPECTED_TAG = "v0.14.0"
EXPECTED_VERSION = "0.14.0-android.1"
EXPECTED_PACKAGE = "com.artcraft.photocraft"
UPSTREAM = "https://github.com/storytold/photocraft.git"


def die(message: str) -> None:
    raise SystemExit("PhotoCraft v0.14.0 safety check failed: " + message)


def command(*args: str, cwd: Path = ROOT, capture: bool = False) -> str:
    result = subprocess.run(
        list(args), cwd=cwd, text=True, check=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def config() -> dict:
    try:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        die(f"invalid pinned-source config: {exc}")
    expected = {
        "upstream_repository": UPSTREAM,
        "upstream_tag": EXPECTED_TAG,
        "upstream_commit": EXPECTED_SHA,
        "upstream_workspace_version": "0.14.0",
        "upstream_rust_toolchain": "1.95.0",
        "android_version_name": EXPECTED_VERSION,
        "android_package": EXPECTED_PACKAGE,
        "android_target": "aarch64-linux-android",
        "android_min_sdk": 28,
        "android_target_sdk": 35,
        "production_signing_allowed": False,
        "production_apk_build_allowed": False,
        "test_apk_build_allowed": True,
        "automatic_upstream_sync_allowed": False,
        "existing_signed_version_code_floor_exclusive": 16790002,
        "publishing_allowed": False,
    }
    for key, correct in expected.items():
        if value.get(key) != correct or type(value.get(key)) is not type(correct):
            die(f"config {key} does not match the reviewed pin")
    return value


def preflight() -> None:
    cfg = config()
    manifest = tomllib.loads((ROOT / "adapters/photocraft/Cargo.toml").read_text())
    android = manifest["package"]["metadata"]["android"]
    if android.get("package") != EXPECTED_PACKAGE:
        die("existing Android package identity changed")
    if android.get("build_targets") != [cfg["android_target"]]:
        die("existing ARM64 target changed")
    if android["sdk"]["min_sdk_version"] != 28 or android["sdk"]["target_sdk_version"] != 35:
        die("existing Android SDK range changed")
    if manifest["package"].get("version", {}).get("workspace") is not True:
        die("adapter must keep inherited version until explicitly prepared")
    prepare = (ROOT / "adapters/photocraft/prepare.sh").read_text()
    if "ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME" not in prepare:
        die("Android-only versionName override is missing")
    shell = (ROOT / "adapters/photocraft/src/lib.rs").read_text()
    features = {
        "TTF/OTF import and restore": ["register_custom_font(", "register_font_data(", "load_custom_fonts("],
        "shared font folder": ["request_font_folder(", "process_shared_font_result(", "launch_shared_fonts("],
        "SAF open/save": ["request_open(", "request_save(", "commit_if_mapped("],
        "in-app update check": ["check_for_updates(", "poll_update_result(", "open_update_page("],
        "IME and keyboard modifiers": ["mod ime_bridge;", "apply_android_modifiers("],
        "GPU diagnostics and compositor": ["app.perf.gpu_info.set_adapter(", "app.set_wgpu(rs)", "effective_rendering_mode()", "PHOTOCRAFT_CPU_CANVAS"],
        "Both hardware modifier sides": ["mod android_modifiers;", "modifiers: AndroidModifiers"],
        "Touch Shortcut Pad": ["mod shortcut_pad;", "shortcut_pad: shortcut_pad::ShortcutPad", "artcraft_shortcut_pad_allowed"],
        "Native font/update menus": ["native_message(", "startup_update_enabled(", 'take("artcraft.shared_fonts_select")'],
        "Android shell": ["PhotoCraftAndroidApp", "impl eframe::App for PhotoCraftAndroidApp"],
    }
    for feature, tokens in features.items():
        missing = [token for token in tokens if token not in shell]
        if missing:
            die(f"baseline feature {feature} has missing markers: {missing}")
    for path in (
        "templates/android/system_fonts.rs",
        "templates/android/ime_bridge.rs",
        "patches/photocraft-menus.patch",
        "tools/photocraft_v014_menu_port.py",
        "adapters/photocraft/prepare.sh",
        "vendor/winit",
        "vendor/android-activity",
    ):
        if not (ROOT / path).exists():
            die(f"existing Android dependency missing: {path}")
    if not list((ROOT / "adapters/photocraft/java").rglob("*.java")):
        die("Android Java SAF Activity missing")
    patch = (ROOT / "patches/photocraft-menus.patch").read_text()
    for token in ("window.artcraftCustomFonts", "help.artcraftCheckUpdates", "window.artcraftTouchShortcutPad", "help.artcraftUpdateSettings"):
        if token not in patch:
            die(f"existing Android menu feature missing: {token}")
    icon = ROOT / "assets/photocraft/launcher-pc.png"
    if icon.is_file():
        digest = hashlib.sha256(icon.read_bytes()).hexdigest()
        if digest != cfg["approved_icon_sha256"]:
            die("launcher Pc PNG exists but its SHA-256 does not match approved artwork")
        print("Approved Pc icon checksum verified.")
    else:
        die("exact approved Pc icon is required for the v0.12 preservation branch")
    print("PASS: static feature-preservation markers, package, SDK, and source pin.")


def verify_source() -> None:
    if not (SOURCE / ".git").exists():
        die("source/photocraft is not an existing Git checkout; run checkout first")
    origin = command("git", "remote", "get-url", "origin", cwd=SOURCE, capture=True)
    if origin.removesuffix(".git") != UPSTREAM.removesuffix(".git"):
        die(f"unexpected source origin: {origin}")
    head = command("git", "rev-parse", "HEAD", cwd=SOURCE, capture=True)
    tag = command("git", "rev-parse", f"{EXPECTED_TAG}^{{commit}}", cwd=SOURCE, capture=True)
    if head != EXPECTED_SHA or tag != EXPECTED_SHA:
        die(f"source HEAD/tag does not match reviewed {EXPECTED_TAG} commit")
    root_manifest = tomllib.loads((SOURCE / "Cargo.toml").read_text())
    workspace = root_manifest["workspace"]["package"]
    if (workspace.get("version"), workspace.get("rust-version"), workspace.get("edition")) != (
        "0.14.0", "1.95", "2024"
    ):
        die("upstream workspace version, Rust requirement, or edition changed")
    if workspace.get("license") != "MIT OR Apache-2.0":
        die("upstream workspace license needs renewed review")
    print(f"PASS: official PhotoCraft {EXPECTED_TAG} is pinned to {EXPECTED_SHA}.")


def checkout() -> None:
    preflight()
    if SOURCE.exists():
        # Never delete, reset, or silently update an existing checkout.
        verify_source()
        print("Reused matching pinned source without resetting local changes.")
        return
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    command(
        "git", "clone", "--depth", "1", "--branch", EXPECTED_TAG,
        "--no-checkout", UPSTREAM, str(SOURCE)
    )
    command("git", "checkout", "--detach", EXPECTED_SHA, cwd=SOURCE)
    verify_source()


def add_cargo_patch(name: str, path: str) -> None:
    manifest = SOURCE / "Cargo.toml"
    text = manifest.read_text()
    header = "[patch.crates-io]"
    lines = text.splitlines()
    index = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    entry = f'{name} = {{ path = "{path}" }}'
    if index is None:
        lines.extend(["", header, entry])
    else:
        end = next((i for i in range(index + 1, len(lines)) if re.match(r"^\s*\[", lines[i])), len(lines))
        lines[index + 1:end] = [
            line for line in lines[index + 1:end]
            if not re.match(rf"^\s*{re.escape(name)}\s*=", line)
        ] + [entry]
    updated = "\n".join(lines) + "\n"
    tomllib.loads(updated)
    manifest.write_text(updated)


def prepare() -> None:
    preflight()
    verify_source()
    # Rebase Android menu commands onto the exact, verified v0.14 source.
    # Fail closed when upstream anchors drift. Keep the original builder and patch untouched.
    subprocess.run(
        ["python3", str(ROOT / "tools/photocraft_v014_menu_port.py"),
         str(SOURCE / "crates/ui-egui/src/menus.rs")],
        cwd=ROOT, check=True
    )
    env = dict(os.environ, ARTCRAFT_PHOTOCRAFT_ANDROID_VERSION_NAME=EXPECTED_VERSION)
    subprocess.run(
        ["bash", "adapters/photocraft/prepare.sh", "photocraft", "PhotoCraft", "source/photocraft", "debug"],
        cwd=ROOT, env=env, check=True,
    )
    # Use existing builder's Android input and ANR fixes, but only in this
    # ephemeral, pinned source checkout. Never edit or replace builder/vendor originals.
    dest = SOURCE / "vendor"
    dest.mkdir(exist_ok=True)
    existing_winit = dest / "winit"
    builder_winit = ROOT / "vendor/winit"
    if existing_winit.exists():
        android_backend = existing_winit / "src/platform_impl/android"
        if android_backend.exists():
            shutil.rmtree(android_backend)
        shutil.copytree(builder_winit / "src/platform_impl/android", android_backend)
    else:
        shutil.copytree(builder_winit, existing_winit)
    add_cargo_patch("winit", "vendor/winit")
    existing_activity = dest / "android-activity"
    if existing_activity.exists():
        die("upstream already vendors android-activity; manual compatibility review required")
    shutil.copytree(ROOT / "vendor/android-activity", existing_activity)
    add_cargo_patch("android-activity", "vendor/android-activity")
    verify_prepared()
    print("PASS: v0.14.0 Android adapter, menu, font, IME, and SAF sources staged for cargo check.")


def verify_prepared() -> None:
    verify_source()
    app = SOURCE / "apps/photocraft-android/Cargo.toml"
    if not app.is_file():
        die("prepared Android crate missing")
    data = tomllib.loads(app.read_text())
    if data["package"].get("version") != EXPECTED_VERSION:
        die("prepared Android versionName mismatch")
    android = data["package"]["metadata"]["android"]
    if android.get("package") != EXPECTED_PACKAGE or android.get("build_targets") != ["aarch64-linux-android"]:
        die("prepared Android identity/architecture mismatch")
    menu = (SOURCE / "crates/ui-egui/src/menus.rs").read_text()
    for command_id in ("window.artcraftCustomFonts", "window.artcraftSharedFontsSelect",
                       "window.artcraftSharedFontsRefresh", "window.artcraftTouchShortcutPad",
                       "help.artcraftUpdateSettings", "help.artcraftCheckUpdates"):
        if command_id not in menu:
            die(f"Android menu action disappeared during v0.14 port: {command_id}")
    if not (SOURCE / "apps/photocraft-android/src/lib.rs").exists():
        die("prepared Android shell missing")
    staged_icon = SOURCE / "apps/photocraft-android/res/drawable/ic_launcher.png"
    if hashlib.sha256(staged_icon.read_bytes()).hexdigest() != config()["approved_icon_sha256"]:
        die("staged launcher icon differs from the approved original")
    print("PASS: prepared versionName, package, architecture and Android menus.")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"preflight", "checkout", "prepare", "verify"}:
        die("usage: photocraft_v012_compat.py preflight|checkout|prepare|verify")
    cmd = sys.argv[1]
    if cmd == "preflight":
        preflight()
    elif cmd == "checkout":
        checkout()
    elif cmd == "prepare":
        prepare()
    else:
        preflight()
        verify_prepared()


if __name__ == "__main__":
    main()
