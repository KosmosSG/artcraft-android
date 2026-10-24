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


    /**
     * Do not trust a repository-wide release's arbitrary APK asset. Both the
     * PhotoCraft-specific tag and the APK filename must identify the SAME version.
     * Covers legacy photocraft-0.10.4.apk and PhotoCraft.Android.v0.10.1.apk
     * as well as PhotoCraft-v0.12.0-android.1-arm64-release.apk.
     */
    static boolean isPhotoCraftApkAsset(String tag, String assetName) {
        String version = versionFromTag(tag);
        if (version == null || assetName == null) return false;
        return Pattern.compile("(?i)^photocraft(?:[.-][a-z0-9]+)*[.-]v?"
                + Pattern.quote(version) + "(?:[.-][a-z0-9]+)*\\.apk$")
                .matcher(assetName).matches();
    }

    /**
     * Never call an older upstream/version-name release an update merely because
     * a temporary Android test APK has a smaller versionCode.
     * Unknown or malformed versions fail closed; Android versionCode is still
     * checked independently before suggesting an in-place install.
     */
    static int compareVersions(String candidate, String installed) {
        int[] a = numericVersion(candidate), b = numericVersion(installed);
        if (a == null || b == null) return -1;
        for (int i = 0; i < a.length; i++) {
            if (a[i] != b[i]) return Integer.compare(a[i], b[i]);
        }
        return 0;
    }

    private static int[] numericVersion(String version) {
        if (version == null || !version.matches("[0-9]+\\.[0-9]+\\.[0-9]+(?:-android\\.[1-9][0-9]*)?"))
            return null;
        String[] parts = version.replace("-android.", ".").split("\\.");
        int[] result = new int[4];
        try {
            for (int i = 0; i < parts.length; i++) result[i] = Integer.parseInt(parts[i]);
        } catch (NumberFormatException error) { return null; }
        return result;
    }

    static boolean isNewer(long candidateCode, long installedCode) {
        return installedCode > 0 && candidateCode > installedCode;
    }
}
