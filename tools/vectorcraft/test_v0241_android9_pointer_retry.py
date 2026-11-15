"""Preflight Android.9 TYPE_NULL source against Android.11 pointer retry overlay.

Run before SDK/NDK installation. Do not import the APK builder or modify the
protected baseline. Uses exact pinned source files and a disposable temp tree.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sys

from patch_android11_pointer_retry import patch


def main(owner: Path, upstream: Path) -> None:
    adapter = owner / "adapters/vectorcraft"
    upstream_cursor = upstream / "crates/ui-egui/src/cursors.rs"
    if not upstream_cursor.is_file():
        raise RuntimeError("Pinned upstream cursor source unavailable")
    with TemporaryDirectory(prefix="vc-android9-pointer-preflight-") as td:
        root = Path(td)
        shutil.copytree(adapter, root / "adapters/vectorcraft")
        target = root / "source/vectorcraft/crates/ui-egui/src/cursors.rs"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(upstream_cursor, target)
        before_host=(root / "adapters/vectorcraft/src/lib.rs").read_text()
        assert before_host.count('egui::Id::new("vectorcraft-android-glass-pan-hide-cursor")') == 1
        patch(root)
        host=(root / "adapters/vectorcraft/src/lib.rs").read_text()
        java=(root / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        cursor=(root / "adapters/vectorcraft/src/adaptive_cursor.rs").read_text()
        assert 'C::None => 0' in cursor
        assert cursor.count('C::None => 0') == 1
        assert "vc_pointer_retry_at: Option<std::time::Instant>" in host
        assert "native_pointer_icon(vc_resolved_cursor)" in host
        assert 'egui::Id::new("vectorcraft-android-glass-pan-hide-cursor")' in host
        assert 'vcPointerAppliedSurface = nativeSurface;' in java
        assert 'nativeSurface.setPointerIcon(PointerIcon.getSystemIcon(this, pointerType));' in java
        assert "if (nativeSurface == vcPointerAppliedSurface && pointerType == nativePointerIconType) return;" in java
        assert 'vcInstallPenHoverListener();' in java
        assert 'PointerIcon.getSystemIcon(this, requestedPointerType)' not in java
        assert 'target_os = "android"' in target.read_text()
        print("PASS: native TYPE_NULL mapping and Android.11 pointer retry coexist, preserving glass-pan marker")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: test_v0241_android9_pointer_retry.py OWNER_ROOT UPSTREAM_ROOT")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
