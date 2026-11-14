#!/usr/bin/env python3
"""Align EffectCraft's guarded in-app updater with PhotoCraft's user interface.
Apply after patch_updater_download.py on a disposable build checkout.
"""
from pathlib import Path
import sys

def once(content, anchor, replacement, label):
    count = content.count(anchor)
    if count != 1:
        raise RuntimeError(f"STOP: {label} anchor drift ({count} matches)")
    return content.replace(anchor, replacement, 1)

PHOTOCRAFT_DIALOG = r'''
    /** Condense the release notes just like PhotoCraft's update offer. */
    private static String ecReleaseSummary(String notes) {
        if (notes == null) return "";
        String text = notes.replace("\r", "");
        int section = text.indexOf("## New in this build");
        if (section >= 0) {
            int start = text.indexOf('\n', section);
            if (start >= 0) text = text.substring(start + 1);
            int next = text.indexOf("\n## ");
            if (next >= 0) text = text.substring(0, next);
        }
        text = text.replace("**", "").replace(String.valueOf((char)96), "")
            .replaceAll("(?m)^[-*] ", "• ")
            .replaceAll("\\n[ \\t]*(?![•\\n])", " ")
            .trim();
        return text.length() > 900 ? text.substring(0, 900) + "…" : text;
    }

    /** PhotoCraft UI: quiet startup check; Install/Later/Skip if newer;
      * brief toast if manual check finds nothing newer or a network error. */
    private void ecPresentUpdate(org.json.JSONObject result, boolean manual) {
        String state = result.optString("state", "error");
        if (!manual && !"update_available".equals(state)) return;
        runOnUiThread(() -> {
            if (isFinishing()) return;
            String installed = result.optString("installed_version", "");
            if ("up_to_date".equals(state)) {
                if (manual) ecFontMessage("EffectCraft is up to date (" + installed + ").");
                return;
            }
            if ("no_release".equals(state)) {
                if (manual) ecFontMessage(
                    "No published EffectCraft update found for the selected channel.");
                return;
            }
            if (!"update_available".equals(state)) {
                if (manual) ecFontMessage("Couldn't check for updates: "
                    + result.optString("message", "Network unavailable"));
                return;
            }
            String version = result.optString("latest_version", "");
            String tag = result.optString("tag_name", "");
            String notes = ecReleaseSummary(result.optString("release_notes", ""));
            if (ecVersion(version) == null || !tag.equals(EC_TAG_PREFIX + version)) {
                if (manual) ecFontMessage("Invalid EffectCraft release information.");
                return;
            }
            android.content.SharedPreferences prefs =
                getSharedPreferences("effectcraft_updates", MODE_PRIVATE);
            if (!manual && tag.equals(prefs.getString("skipped_tag", ""))) return;
            String message = "You have " + installed + ".\n\n"
                + (notes.isEmpty() ? "An EffectCraft update is available." : notes)
                + "\n\nDownload and install it now? Save your work first: "
                + "EffectCraft closes to update.";
            if (!"com.artcraft.effectcraft".equals(getPackageName())) {
                message += "\n\nThis temporary TEST app cannot replace "
                    + "your published EffectCraft installation.";
            }
            new android.app.AlertDialog.Builder(
                this, android.app.AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                .setTitle("EffectCraft " + version + " is available")
                .setMessage(message)
                .setPositiveButton("Install", (dialog, which) ->
                    ecBeginDownload(result))
                .setNegativeButton("Later", null)
                .setNeutralButton("Skip This Version", (dialog, which) ->
                    prefs.edit().putString("skipped_tag", tag).apply())
                .show();
        });
    }
'''

def apply(root):
    activity = Path(root) / "templates/android/SafActivity.java"
    original = activity.read_text(encoding="utf-8")
    if "ecBeginDownload" not in original or "ecTrustedReleaseAsset" not in original:
        raise RuntimeError("STOP: guarded updater missing")
    current = once(original, "                String selectedDownload = null;",
        "                String selectedDownload = null;\n"
        "                String selectedNotes = null;\n"
        "                String selectedTag = null;", "release metadata")
    current = once(current, "                        selectedDownload = requiredUrl;",
        '                        selectedDownload = requiredUrl;\n'
        '                        selectedNotes = release.optString("body", "");\n'
        '                        selectedTag = tag;', "release selection")
    current = once(current, '                    result.put("latest_version", selectedVersion);',
        '                    result.put("latest_version", selectedVersion);\n'
        '                    result.put("tag_name", selectedTag);\n'
        '                    result.put("release_notes", selectedNotes);',
        "release result")
    if current.count('getBoolean("startup", false)') != 2:
        raise RuntimeError("STOP: old startup update settings have drifted")
    current = current.replace('getBoolean("startup", false)', 'getBoolean("startup", true)')
    start = current.find("    private void ecPresentUpdate(org.json.JSONObject result, boolean manual) {")
    # End exactly at the close of ecPresentUpdate's runOnUiThread lambda.
    # The Magic-Pencil bridge follows it in this Activity. Never delete the
    # code between the updater method and the later downloader helpers.
    boundary = "        });\n    }\n"
    closing = current.find(boundary, start)
    if start < 0 or closing < 0 or current.count("    private void ecPresentUpdate(") != 1:
        raise RuntimeError("STOP: update dialog boundary changed")
    end = closing + len(boundary)
    preserved_suffix = current[end:]
    if "ecWheelDeviceIds" not in preserved_suffix or "ecTrustedReleaseAsset" not in preserved_suffix:
        raise RuntimeError("STOP: would truncate the verified stylus or downloader bridge")
    current = current[:start] + PHOTOCRAFT_DIALOG + current[end:]
    assert "ecBeginDownload(result)" in current
    assert "ecTrustedReleaseAsset" in current
    assert 'setNeutralButton("Skip This Version"' in current
    activity.write_text(current, encoding="utf-8")
    print("PASS: PhotoCraft dialog/install/later/skip, quiet checks, notes and startup preferences")

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("Usage: patch_updater_photocraft_dialog.py <repo-root>")
    apply(Path(sys.argv[1]))
