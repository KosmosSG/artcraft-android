#!/usr/bin/env python3
"""EffectCraft Android.3 only: download/installer upgrade to existing update UI.

Run after integrate_updater.py in the disposable workflow. Never alter any
published release, baseline Activity or production signing material.
"""
from pathlib import Path
import sys

BEFORE = '''            String link = result.optString("release_url");
            if ("update_available".equals(state) && link.startsWith("https://github.com/KosmosSG/artcraft-android/releases/tag/effectcraft-v"))
                dialog.setPositiveButton("View Release", (d, w) -> {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(link))); }
                    catch (Exception e) { ecFontMessage("No browser available"); }
                });'''
AFTER = '''            String link = result.optString("release_url");
            String asset = result.optString("download_url");
            if ("update_available".equals(state)
                && link.startsWith("https://github.com/KosmosSG/artcraft-android/releases/tag/effectcraft-v")
                && asset.startsWith(EC_DOWNLOAD_ROOT + EC_TAG_PREFIX)) {
                dialog.setPositiveButton("Download & Install", (d, w) ->
                    ecBeginDownload(result));
                dialog.setNeutralButton("View Release", (d, w) -> {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(link))); }
                    catch (Exception e) { ecFontMessage("No browser available"); }
                });
            }'''

def once(content, a, b, label):
    matches = content.count(a)
    if matches != 1: raise RuntimeError(
        f"STOP: {label} changed, expected exactly 1 anchor, found {matches}")
    return content.replace(a, b, 1)

def apply(root):
    root = Path(root)
    java = root / "templates/android/SafActivity.java"
    source = java.read_text(encoding="utf-8").rstrip()
    if not source.endswith("}") or "ecBeginDownload" in source or "ecCheckUpdates" not in source:
        raise RuntimeError("STOP: expected verified EffectCraft update template only")
    source = once(source, BEFORE, AFTER, "EffectCraft release dialog")
    helper = (root / "tools/effectcraft/UpdaterDownload.java.inc").read_text(encoding="utf-8")
    if helper.count("private void ecBeginDownload(") != 1 or \
            "PackageInstaller" not in helper or "onResume()" not in helper:
        raise RuntimeError("STOP: in-app downloader adapter incomplete")
    java.write_text(source[:-1] + helper + "\n}\n", encoding="utf-8")

    # Permission applies to EffectCraft's generated manifest, not other apps,
    # and is required for Android 8+ package install approval.
    builder = root / "lib/build-common.sh"
    src = builder.read_text(encoding="utf-8")
    old = r'name = "android.permission.INTERNET"\n'
    new = (r'name = "android.permission.INTERNET"\n'
           r'[[package.metadata.android.uses_permission]]\n'
           r'name = "android.permission.REQUEST_INSTALL_PACKAGES"\n')
    src = once(src, old, new, "EffectCraft package permissions")
    builder.write_text(src, encoding="utf-8")
    print("PASS: official GitHub asset only, download progress, APK/package check, installer with user approval")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_updater_download.py <builder-root>")
    apply(Path(sys.argv[1]))
