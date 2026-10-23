package com.artcraft.designcraft;

public final class DesignCraftUpdatePolicyTest {
    private static final String VERSION = "0.12.0-android.1";
    private static final String TAG = "designcraft-v" + VERSION;
    private static final String APK = DesignCraftUpdatePolicy.REPOSITORY + "/releases/download/"
            + TAG + "/DesignCraft-" + VERSION + "-arm64-v8a.apk";

    private static long validate(String tag, String pkg, Object code, String certificate, String url) {
        return DesignCraftUpdatePolicy.validate(tag, 1, pkg, VERSION, code, certificate,
                "a".repeat(64), url, "b".repeat(40), "c".repeat(40), "d".repeat(40));
    }

    private static void reject(Runnable action) {
        try { action.run(); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Incompatible update accepted");
    }

    public static void main(String[] args) {
        long code = validate(TAG, "com.artcraft.designcraft", 16800002L, DesignCraftUpdatePolicy.CERT, APK);
        if (code != 16800002L || !DesignCraftUpdatePolicy.newer(16800001, code)
                || DesignCraftUpdatePolicy.newer(code, code) || DesignCraftUpdatePolicy.newer(code, 16800001))
            throw new AssertionError("Version ordering failed");
        reject(() -> validate("photocraft-v" + VERSION, "com.artcraft.designcraft", code, DesignCraftUpdatePolicy.CERT, APK));
        reject(() -> validate(TAG, "com.artcraft.designcraft.candidate", code, DesignCraftUpdatePolicy.CERT, APK));
        reject(() -> validate(TAG, "com.artcraft.designcraft", code, "0".repeat(64), APK));
        reject(() -> validate(TAG, "com.artcraft.designcraft", "16800002", DesignCraftUpdatePolicy.CERT, APK));
        reject(() -> validate(TAG, "com.artcraft.designcraft", 2100000001L, DesignCraftUpdatePolicy.CERT, APK));
        reject(() -> validate(TAG, "com.artcraft.designcraft", code, DesignCraftUpdatePolicy.CERT, "https://example.com/a.apk"));
        System.out.println("PASS: DesignCraft update identity, asset destination and version-code ordering");
    }
}
