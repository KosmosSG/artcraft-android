package com.artcraft.designcraft;

/** Pure identity policy shared by the Activity and host-Java tests. No APK installation. */
final class DesignCraftUpdatePolicy {
    static final String REPOSITORY = "https://github.com/KosmosSG/artcraft-android";
    static final String CERT = "c45236b436cbfbfbeade716b11cb24a50a795a6af3f147132ce6f19753fea394";

    static long integer(Object value) {
        if (!(value instanceof Integer) && !(value instanceof Long))
            throw new IllegalArgumentException("Expected an integer JSON value");
        return ((Number) value).longValue();
    }

    static long validate(String tag, Object schema, String pkg, String version, Object code,
                         String certificate, String digest, String apkUrl,
                         String source, String builder, String automation) {
        if (integer(schema) != 1 || !"com.artcraft.designcraft".equals(pkg)
                || !version.matches("(?:0|[1-9][0-9]*)\\.(?:0|[1-9][0-9]*)\\.(?:0|[1-9][0-9]*)-android\\.[1-9][0-9]*")
                || !("designcraft-v" + version).equals(tag) || !CERT.equals(certificate)
                || !digest.matches("[0-9a-f]{64}") || !source.matches("[0-9a-f]{40}")
                || !builder.matches("[0-9a-f]{40}") || !automation.matches("[0-9a-f]{40}"))
            throw new IllegalArgumentException("Incompatible DesignCraft update metadata");
        long result = integer(code);
        if (result < 1 || result > 2100000000L)
            throw new IllegalArgumentException("Invalid Android version code");
        String canonical = REPOSITORY + "/releases/download/" + tag
                + "/DesignCraft-v" + version + "-arm64-v8a.apk";
        String legacy = REPOSITORY + "/releases/download/" + tag
                + "/DesignCraft-" + version + "-arm64-v8a.apk";
        // Old permanently signed DesignCraft v0.12.0-android.1 accepts only
        // the legacy APK URL. Preserve that release update chain with an
        // identical-bytes alias; prefer the canonical v-prefixed APK name.
        if (!canonical.equals(apkUrl) && !legacy.equals(apkUrl))
            throw new IllegalArgumentException("Unexpected APK destination");
        return result;
    }

    static boolean newer(long installed, long candidate) {
        if (installed < 1 || installed > 2100000000L || candidate < 1 || candidate > 2100000000L)
            throw new IllegalArgumentException("Invalid version code comparison");
        return candidate > installed;
    }
}
