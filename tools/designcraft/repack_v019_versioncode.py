#!/usr/bin/env python3
"""Prepare an AndroidManifest override for DesignCraft v0.19.0 original-package payload.

Only operates on the disposable runner builder *after* its successful first
compilation. cargo-apk2 generates an AndroidManifest with versionCode derived
from semver, which can be LOWER than published Android releases. The
cargo-apk2 backend deliberately panics if version_code is set directly in TOML.
An XML manifest_override preserves every existing permission, Activity,
intent-filter, updater setting and app identity while reserving monotonic
versionCode 16800012. The subsequent apk2 repack reuses built native code.
"""
from pathlib import Path
import sys
import tomllib
import xml.etree.ElementTree as ET

ANDROID = "http://schemas.android.com/apk/res/android"
OLD_AUTO_CODE = 16782080  # (1 << 24) | (19 << 8), cargo-apk2 v1.5
PRODUCTION_CODE = 16800012
VERSION = "0.19.0-android.1"
PACKAGE = "com.artcraft.designcraft"
OVERRIDE = "AndroidManifest.monotonic.xml"

def main(builder: Path):
    builder = builder.resolve()
    if builder.name != "designcraft-builder" or "RUNNER_TEMP" not in __import__("os").environ:
        raise SystemExit("This script only runs in the disposable GitHub Actions builder")
    manifest_path = builder / "source/designcraft/apps/designcraft-android/Cargo.toml"
    if not manifest_path.is_file():
        raise SystemExit("Generated DesignCraft Android Cargo.toml missing")
    data = tomllib.loads(manifest_path.read_text())
    assert data["package"]["version"] == VERSION, "Unexpected versionName in Cargo.toml"
    assert data["package"]["metadata"]["android"]["package"] == PACKAGE, "Wrong Android package"
    meta = data["package"]["metadata"]["android"]
    assert "version_code" not in meta and "manifest_override" not in meta, "Preexisting override must be reviewed"

    target = builder / "build/designcraft/target"
    candidates = []
    for file in target.rglob("AndroidManifest.xml"):
        try:
            doc = ET.parse(file)
            root = doc.getroot()
        except ET.ParseError:
            continue
        if (root.tag == "manifest" and root.get("package") == PACKAGE
            and root.get(f"{{{ANDROID}}}versionName") == VERSION):
            candidates.append((file,doc))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected exactly one generated DesignCraft manifest, found {len(candidates)}")
    source, doc = candidates[0]
    root=doc.getroot()
    auto_code=int(root.get(f"{{{ANDROID}}}versionCode", "0"))
    if auto_code != OLD_AUTO_CODE:
        raise RuntimeError(f"Unexpected cargo-apk2 auto versionCode {auto_code}; expected {OLD_AUTO_CODE}")
    root.set(f"{{{ANDROID}}}versionCode", str(PRODUCTION_CODE))
    ET.register_namespace("android", ANDROID)
    output = manifest_path.parent / OVERRIDE
    doc.write(output, encoding="utf-8", xml_declaration=True)
    reparsed=ET.parse(output).getroot()
    if reparsed.get("package")!=PACKAGE or reparsed.get(f"{{{ANDROID}}}versionCode")!=str(PRODUCTION_CODE):
        raise RuntimeError("Manifest override failed verification")
    cargo=manifest_path.read_text()
    anchor="[package.metadata.android]\n"
    if cargo.count(anchor)!=1:
        raise RuntimeError("Metadata section changed; refusing override")
    cargo=cargo.replace(anchor, anchor+f'manifest_override = "{OVERRIDE}"\n',1)
    tomllib.loads(cargo)
    manifest_path.write_text(cargo)
    print(f"Preserved original generated manifest {source} with monotonic versionCode={PRODUCTION_CODE}")
    print("The subsequent cargo apk2 build will only package in a temporary workspace; production signer remains separate.")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: repack_v019_versioncode.py TEMP_DESIGNCRAFT_BUILDER")
    main(Path(sys.argv[1]))
