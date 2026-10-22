"""Stage a separate PhotoCraft Test app identity inside a temporary CI checkout."""
from pathlib import Path
import argparse
import tomllib

TEST_PACKAGE = "com.artcraft.photocraft.candidate"
JAVA_FILES = ("PhotoCraftActivity.java", "PhotoCraftUpdatePolicy.java")

def stage(root):
    parent = Path(root) / "adapters/photocraft"
    manifest = parent / "Cargo.toml"
    s = manifest.read_text()
    old = 'package = "com.artcraft.photocraft"'
    if s.count(old) != 1 or s.count('label = "PhotoCraft"') != 2:
        raise ValueError("Unexpected production manifest")
    updated = s.replace(old, 'package = "com.artcraft.photocraft.candidate"', 1)
    updated = updated.replace('label = "PhotoCraft"', 'label = "PhotoCraft Test"')
    a = tomllib.loads(updated)["package"]["metadata"]["android"]
    if a["package"] != TEST_PACKAGE or a["application"]["activity"][0]["name"] != ".PhotoCraftActivity":
        raise ValueError("Activity configuration changed")
    changes = []
    for name in JAVA_FILES:
        p = parent / "java/com/artcraft/photocraft" / name
        original = p.read_text()
        first = "package com.artcraft.photocraft;"
        if not original.startswith(first + "\n") or original.count(first) != 1:
            raise ValueError("Unexpected Java source package: " + name)
        changes.append((p, original.replace(first, "package com.artcraft.photocraft.candidate;", 1)))
    manifest.write_text(updated)
    for path, new in changes:
        path.write_text(new)
    print("PASS: separated PhotoCraft Test from the production package")

def verify(root):
    parent = Path(root) / "adapters/photocraft"
    a = tomllib.loads((parent / "Cargo.toml").read_text())["package"]["metadata"]["android"]
    if a["package"] != TEST_PACKAGE or a["application"]["label"] != "PhotoCraft Test":
        raise ValueError("Test package mismatch")
    for name in JAVA_FILES:
        s = (parent / "java/com/artcraft/photocraft" / name).read_text()
        if not s.startswith("package com.artcraft.photocraft.candidate;\n"):
            raise ValueError("Test Java identity mismatch")
    print("PASS: Java and launcher identity verified")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("stage", "verify"))
    parser.add_argument("--root", type=Path, default=Path("."))
    a = parser.parse_args()
    (stage if a.command == "stage" else verify)(a.root)
