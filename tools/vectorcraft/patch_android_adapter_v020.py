"""API compatibility patch for the *staged* v0.20 VectorCraft Android shell.

The installed VectorCraft v0.14 Android branch and production adapter are
unchanged. Fail closed on unknown release, mismatched source or duplicate patch.
"""
from pathlib import Path
import sys

OLD_MIME = '''        .and_then(|(_, exts)| exts.first().copied())
        .map(mime_for_extension)'''
NEW_MIME = '''        .and_then(|(_, exts)| exts.first().map(String::as_str))
        .map(mime_for_extension)'''
OLD_INPUT = "        self.inner.raw_input_hook(raw);"
NEW_INPUT = "        self.inner.raw_input_hook(ctx, raw);"


def patch_staged_source(manifest: str, source: str) -> str:
    if manifest.count('version = "0.20.0"') != 1:
        raise ValueError("Only official VectorCraft v0.20.0 is reviewed for this patch")
    if source.count(OLD_MIME) != 1:
        raise ValueError("VectorCraft MIME source anchor missing or duplicated")
    if source.count(OLD_INPUT) != 1:
        raise ValueError("VectorCraft input-hook source anchor missing or duplicated")
    # The compatibility changes are equivalent for v0.20 and preserve SAF
    # MIME selection and physical keyboard/IME event forwarding semantics.
    return source.replace(OLD_MIME, NEW_MIME, 1).replace(OLD_INPUT, NEW_INPUT, 1)


def apply(upstream: Path) -> None:
    manifest_path = upstream / "Cargo.toml"
    source_path = upstream / "apps/vectorcraft-android/src/lib.rs"
    patched = patch_staged_source(manifest_path.read_text(), source_path.read_text())
    source_path.write_text(patched)
    print("PASS: reviewed v0.20 MIME String and egui raw_input_hook API adaptations")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_android_adapter_v020.py PATH_TO_UPSTREAM_VECTORCRAFT")
    apply(Path(sys.argv[1]))
