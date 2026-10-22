package com.artcraft.photocraft;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Fail-closed update policy for the public, signed PhotoCraft Android releases.
 * Version names are informational; Android upgrades are ordered by versionCode.
 * The release must explicitly state its code. Never guess it from semver.
 */
final class PhotoCraftUpdatePolicy {
    private static final String PREFIX = "photocraft-v";
    private static final Pattern TAG = Pattern.compile(
            "photocraft-v[0-9]+\\.[0-9]+\\.[0-9]+(?:-android\\.[1-9][0-9]*)?");
    private static final Pattern VERSION_CODE = Pattern.compile(
            "(?i)\\bversion\\s*[-_]?\\s*code\\b\\s*[:=]?\\s*`?([0-9]{1,12})`?");

    private PhotoCraftUpdatePolicy() { }

    static String versionFromTag(String tag) {
        if (tag == null || !TAG.matcher(tag).matches()) return null;
        return tag.substring(PREFIX.length());
    }

    static long declaredVersionCode(String releaseNotes) {
        if (releaseNotes == null) return -1;
        Matcher match = VERSION_CODE.matcher(releaseNotes);
        if (!match.find()) return -1;
        try {
            long value = Long.parseLong(match.group(1));
            return value > 0 ? value : -1;
        } catch (NumberFormatException ignored) {
            return -1;
        }
    }

    static boolean isNewer(long candidateCode, long installedCode) {
        return installedCode > 0 && candidateCode > installedCode;
    }
}
