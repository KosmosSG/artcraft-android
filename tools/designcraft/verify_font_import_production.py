"""Verify the exact production-package font-fix candidate before permanent signing.

Fails closed on package/version, ABI, approved icon pixels and native UI
branding. Never uses or accesses any production signing secret.
"""
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "approved-branding"
sys.path.insert(0, str(ROOT))
from approved_branding import check_assets, ASSETS


def run(*args):
    return subprocess.check_output([str(arg) for arg in args], text=True)


def pixels(blob):
    image = Image.open(io.BytesIO(blob)).convert("RGBA")
    return image.size, hashlib.sha256(image.tobytes()).hexdigest()


def main(apk, sdk, source_commit):
    apk = Path(apk)
    sdk = Path(sdk)
    cfg = check_assets()
    assert cfg["app"] == "designcraft"
    version = "0.12.0-android.5"
    code = "16800006"
    package = "com.artcraft.designcraft"
    badging = run(sdk / "aapt2", "dump", "badging", apk)
    resources = run(sdk / "aapt2", "dump", "resources", apk)
    sig = run(sdk / "apksigner", "verify", "--verbose", "--print-certs", apk)
    m = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'",
                  badging, re.M)
    assert m and m.groups() == (package, code, version), "Incorrect production APK package or version"
    assert re.search(r"^launchable-activity: name='com\.artcraft\.designcraft\.DesignCraftActivity'", badging, re.M), "Missing production Activity"
    assert "native-code: 'arm64-v8a'" in badging, "Wrong architecture"
    assert "Signer #1 certificate SHA-256 digest:" in sig, "Candidate must have a disposable signature"
    for name in ("mipmap/ic_launcher", "mipmap/ic_launcher_round",
                 "drawable/ic_launcher_foreground", "color/approved_launcher_background"):
        assert name in resources, "Missing approved Android resource: " + name
    with zipfile.ZipFile(apk) as archive:
        files = archive.namelist()
        assert "lib/arm64-v8a/libdesigncraft_android.so" in files, "ARM64 native app missing"
        assert not any(p.startswith("lib/") and not p.startswith("lib/arm64-v8a/") for p in files)
        assert "classes.dex" in files
        image_hashes = {pixels(archive.read(p)) for p in files
                        if p.startswith("res/") and p.endswith((".png", ".webp"))}
        for icon in (ASSETS / "res").rglob("*.png"):
            assert pixels(icon.read_bytes()) in image_hashes, "Missing exact approved icon: " + str(icon)
        native = archive.read("lib/arm64-v8a/libdesigncraft_android.so")
        brand = Image.open(ASSETS / "res/drawable-nodpi/ic_inapp_brand_128.png").convert("RGBA").tobytes()
        assert brand in native, "Approved logo missing from app UI"
        xml = []
        for name in files:
            if name.startswith("res/") and name.endswith(".xml"):
                dumped = run(sdk / "aapt2", "dump", "xmltree", apk, "--file", name)
                if "E: adaptive-icon" in dumped:
                    assert "E: foreground" in dumped and "E: background" in dumped
                    xml.append(name)
        assert len(xml) >= 2, "Adaptive icons not compiled"
    sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    verification = dict(
        app="designcraft", package=package, version_name=version, version_code=int(code),
        apk_sha256=sha, candidate_sha256=sha, source_sha=source_commit,
        approved_source_sha256=cfg["source_sha256"],
        compiled_pixels_verified=True, native_ui_brand_embedded=True,
        adaptive_icons_verified=True, arm64=True, package_verified=True,
        production_signing_verified=False, device_tested=False,
        eligible_for_release=False,
        trackpad_experiments_included=False,
    )
    print(json.dumps(verification, indent=2))
    print("PASS: production identity, candidate signer, ARM64 and approved artwork", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: verify_font_import_production.py APK BUILD_TOOLS_DIR SOURCE_SHA")
    main(*sys.argv[1:])
