package com.artcraft.photocraft;

/** Run with javac/java on the review branch; no Android SDK or signing keys needed. */
public final class PhotoCraftUpdatePolicyTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        check("0.10.0-android.2".equals(PhotoCraftUpdatePolicy.versionFromTag(
                "photocraft-v0.10.0-android.2")), "Android release tag");
        check("0.10.4".equals(PhotoCraftUpdatePolicy.versionFromTag(
                "photocraft-v0.10.4")), "legacy release tag");
        check(PhotoCraftUpdatePolicy.versionFromTag("photocraft-v0.10.0-android.0") == null,
                "invalid Android revision must be rejected");
        check(PhotoCraftUpdatePolicy.versionFromTag("other-v0.12.0") == null,
                "other apps must be excluded");
        check(PhotoCraftUpdatePolicy.versionFromTag("photocraft-v0.12.0-android.1-extra") == null,
                "malformed release tag must be excluded");

        check(PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "photocraft-v0.12.0-android.1", "PhotoCraft-v0.12.0-android.1-arm64-release.apk"),
                "new PhotoCraft ARM64 naming convention");
        check(PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "photocraft-v0.10.0-android.2", "PhotoCraft-0.10.0-android.2-arm64-v8a.apk"),
                "published Android .2 asset");
        check(PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "photocraft-v0.10.1", "PhotoCraft.Android.v0.10.1.apk"),
                "legacy PhotoCraft Android asset");
        check(PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "photocraft-v0.10.4", "photocraft-0.10.4.apk"),
                "legacy PhotoCraft naming");
        check(!PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "photocraft-v0.12.0-android.1", "WordCraft-v0.12.0-android.1-arm64-release.apk"),
                "ignore unrelated ArtCraft APK even when placed on PhotoCraft release");
        check(!PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "photocraft-v0.12.0-android.1", "PhotoCraft-v0.11.1-arm64-release.apk"),
                "ignore PhotoCraft APK for wrong release version");
        check(!PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "photocraft-v0.12.0-android.1", "PhotoCraft-v0.12.0-android.1-arm64-release.zip"),
                "only APKs qualify");
        check(!PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                "deckcraft-v0.12.0-android.1", "PhotoCraft-v0.12.0-android.1-arm64-release.apk"),
                "reject non-PhotoCraft release tags");

        String latestNotes = "Native update feedback and optional check. "
                + "VersionCode-based metadata support. "
                + "Original certificate retained; versionCode 16790001 exceeds the previous build.";
        check(PhotoCraftUpdatePolicy.declaredVersionCode(latestNotes) == 16790001L,
                "published Android .2 versionCode");
        check(PhotoCraftUpdatePolicy.declaredVersionCode("Version Code: 16779778") == 16779778L,
                "legacy release version code");
        check(PhotoCraftUpdatePolicy.declaredVersionCode("Version code: `16790002`") == 16790002L,
                "Markdown code value");
        check(PhotoCraftUpdatePolicy.declaredVersionCode("PhotoCraft v0.10.4 signed") == -1,
                "missing code must fail closed");
        check(PhotoCraftUpdatePolicy.declaredVersionCode("VersionCode-based update") == -1,
                "prose alone must not imply versionCode");
        check(PhotoCraftUpdatePolicy.declaredVersionCode("versionCode 0") == -1,
                "invalid zero code");
        check(PhotoCraftUpdatePolicy.isNewer(16790001, 16781035),
                "higher Android code is an update even if upstream semver is lower");
        check(!PhotoCraftUpdatePolicy.isNewer(16781035, 16790001),
                "older signed release must not be suggested as an update");
        check(!PhotoCraftUpdatePolicy.isNewer(16790001, 16790001),
                "same Android code must not be suggested");
        check(!PhotoCraftUpdatePolicy.isNewer(16790001, 0),
                "unknown installed version code must fail closed");
        System.out.println("PASS: PhotoCraft Android release-tag and versionCode policy.");
    }
}
