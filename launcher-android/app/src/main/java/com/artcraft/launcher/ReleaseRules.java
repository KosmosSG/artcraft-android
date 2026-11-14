package com.artcraft.launcher;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Strict app-scoped public release selection. No arbitrary APK asset matching. */
public final class ReleaseRules {
    private static final Pattern VERSION = Pattern.compile("^(\\d+)\\.(\\d+)\\.(\\d+)-android\\.(\\d+)$");
    private ReleaseRules() {}

    public static String versionForTag(String appKey, String tag) {
        if (tag == null || appKey == null) return null;
        String prefix = appKey.toLowerCase(Locale.ROOT) + "-v";
        if (!tag.startsWith(prefix)) return null;
        String v = tag.substring(prefix.length());
        return VERSION.matcher(v).matches() ? v : null;
    }

    /** Launcher versions have their own exact namespace, never mixed with Craft apps. */
    public static String launcherVersionForTag(String tag) {
        return versionForTag("artcraft-launcher",tag);
    }

    public static boolean isLauncherApkFor(String version,String name) {
        return version!=null && VERSION.matcher(version).matches()
            && ("ArtCraft-Launcher-v"+version+"-arm64-v8a.apk").equals(name);
    }

    public static boolean isApkFor(String appName, String key, String version, String filename) {
        if (filename == null || version == null) return false;
        String canonical = appName + "-v" + version + "-arm64-v8a.apk";
        if (filename.equals(canonical)) return true;
        // Legacy published PDFCraft release asset: revision appears in the tag but not the file name.
        if ("pdfcraft".equals(key)) {
            Matcher m = VERSION.matcher(version);
            return m.matches() && filename.equals("PDFCraft-v" + m.group(1) + "." + m.group(2) + "." + m.group(3) + "-arm64-release.apk");
        }
        return false;
    }

    public static int compareVersions(String a, String b) {
        Matcher ma = VERSION.matcher(a == null ? "" : a);
        Matcher mb = VERSION.matcher(b == null ? "" : b);
        if (!ma.matches() || !mb.matches()) return 0;
        for (int i = 1; i <= 4; i++) {
            int cmp = Integer.compare(Integer.parseInt(ma.group(i)), Integer.parseInt(mb.group(i)));
            if (cmp != 0) return cmp;
        }
        return 0;
    }
}
