"""Fail closed on APK signature, identity, version or ARM64 launcher mismatch."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


def verify(apk, aapt, apksigner, version, code, cert):
    certificate = re.sub(r"[:\s]", "", cert).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", certificate):
        raise ValueError("Expected a SHA256 certificate fingerprint")
    signed = subprocess.check_output([apksigner, "verify", "--verbose", "--print-certs", apk], text=True)
    signers = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)", signed)
    if [s.lower() for s in signers] != [certificate]:
        raise ValueError("APK certificate does not match the supplied permanent signing identity")
    badging = subprocess.check_output([aapt, "dump", "badging", apk], text=True)
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging, re.M)
    if not package or package.groups() != ("com.artcraft.vectorcraft", str(code), version):
        raise ValueError("APK package/version metadata does not match the requested build")
    if not re.search(r"^launchable-activity: name='com\.artcraft\.vectorcraft\.VectorCraftActivity'", badging, re.M):
        raise ValueError("VectorCraft launcher is missing")
    with zipfile.ZipFile(apk) as archive:
        if "lib/arm64-v8a/libvectorcraft_android.so" not in archive.namelist():
            raise ValueError("VectorCraft ARM64 library is missing")
    return {"package": package[1], "version_code": code, "version_name": version,
            "certificate_sha256": certificate, "apk_sha256": hashlib.sha256(Path(apk).read_bytes()).hexdigest(),
            "device_validation": "pending: install, font import, open/save, keyboard and lifecycle"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for arg in ("apk", "aapt", "apksigner", "version", "version_code", "certificate"):
        p.add_argument(arg)
    a = p.parse_args()
    print(json.dumps(verify(a.apk, a.aapt, a.apksigner, a.version, int(a.version_code), a.certificate), indent=2))
