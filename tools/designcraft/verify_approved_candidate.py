"""Verify DesignCraft .5 disposable candidate contains the owner's approved icon."""
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image


def pixels(data):
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    return (image.size, hashlib.sha256(image.tobytes()).hexdigest())


def verify(apk: Path, aapt: Path) -> dict:
    source = Path(__file__).parents[1] / "approved-branding/assets"
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["app"] != "designcraft":
        raise ValueError("Wrong approved app icon manifest")
    master = source / manifest["filename"]
    if hashlib.sha256(master.read_bytes()).hexdigest() != manifest["source_sha256"]:
        raise ValueError("Approved icon artwork checksum mismatch")
    badging = subprocess.check_output([str(aapt), "dump", "badging", str(apk)], text=True)
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging, re.M)
    if not package or package.groups() != ("com.artcraft.designcraft.candidate", "16800006", "0.12.0-android.5"):
        raise ValueError("Unexpected APK application identity")
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        compiled = {pixels(archive.read(p)) for p in names
                    if p.startswith("res/") and p.endswith((".png", ".webp"))}
        for relative, digest in manifest["resources"].items():
            if not relative.endswith(".png"):
                continue
            approved = source / relative
            raw = approved.read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError(f"Approved derivative changed: {relative}")
            if pixels(raw) not in compiled:
                raise ValueError(f"Approved logo absent from compiled APK: {relative}")
        library = "lib/arm64-v8a/libdesigncraft_android.so"
        if library not in names:
            raise ValueError("Missing ARM64 DesignCraft library")
        native = archive.read(library)
        rgba = Image.open(source / "res/drawable-nodpi/ic_inapp_brand_128.png").convert("RGBA").tobytes()
        if rgba not in native:
            raise ValueError("Approved in-app logo bytes not embedded in native library")
    return {
        "app": manifest["app"],
        "package": package.group(1),
        "version": package.group(3),
        "source_icon_sha256": manifest["source_sha256"],
        "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
        "approved_launcher_pixels": True,
        "in_app_brand_bytes_embedded": True,
        "top_left_home_hook_source": "source patch checked separately",
        "device_tested": False,
    }


if __name__ == "__main__":
    result = verify(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
