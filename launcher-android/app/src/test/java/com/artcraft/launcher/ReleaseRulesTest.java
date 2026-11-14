package com.artcraft.launcher;

import org.junit.Test;
import static org.junit.Assert.*;

public final class ReleaseRulesTest {
    @Test public void exactTagScope() {
        assertEquals("0.24.1-android.7", ReleaseRules.versionForTag("vectorcraft", "vectorcraft-v0.24.1-android.7"));
        assertNull(ReleaseRules.versionForTag("vectorcraft", "photocraft-v0.24.1-android.7"));
        assertNull(ReleaseRules.versionForTag("photocraft", "photocraft-v0.24.1-android.7-v2-preview"));
        assertNull(ReleaseRules.versionForTag("photocraft", "photocraft-v0.24.1-android.7-not-signed"));
    }
    @Test public void exactAssets() {
        assertTrue(ReleaseRules.isApkFor("PhotoCraft","photocraft","0.23.1-android.5","PhotoCraft-v0.23.1-android.5-arm64-v8a.apk"));
        assertFalse(ReleaseRules.isApkFor("PhotoCraft","photocraft","0.23.1-android.5","PhotoCraft-v0.23.1-android.5-test-only.apk"));
        assertFalse(ReleaseRules.isApkFor("PhotoCraft","photocraft","0.23.1-android.5","VectorCraft-v0.23.1-android.5-arm64-v8a.apk"));
        assertTrue(ReleaseRules.isApkFor("PDFCraft","pdfcraft","0.21.1-android.10","PDFCraft-v0.21.1-arm64-release.apk"));
    }
    @Test public void launcherReleasesMustBeExact() {
        assertEquals("0.1.0-android.7",
            ReleaseRules.launcherVersionForTag("artcraft-launcher-v0.1.0-android.7"));
        assertNull(ReleaseRules.launcherVersionForTag("photocraft-v0.1.0-android.7"));
        assertNull(ReleaseRules.launcherVersionForTag("artcraft-launcher-v0.1.0-android.7-preview"));
        assertNull(ReleaseRules.launcherVersionForTag("artcraft-launcher-v0.1.0-android.7-test"));
        assertTrue(ReleaseRules.isLauncherApkFor("0.1.0-android.7",
            "ArtCraft-Launcher-v0.1.0-android.7-arm64-v8a.apk"));
        assertFalse(ReleaseRules.isLauncherApkFor("0.1.0-android.7",
            "ArtCraft-Launcher-v0.1.0-android.7-TEST-ONLY.apk"));
        assertFalse(ReleaseRules.isLauncherApkFor("0.1.0-android.7",
            "ArtCraft-Launcher-v0.1.0-android.8-arm64-v8a.apk"));
        assertFalse(ReleaseRules.isLauncherApkFor("0.1.0-android.7","unknown.apk"));
    }

    @Test public void increasingVersions() {
        assertTrue(ReleaseRules.compareVersions("0.24.1-android.1","0.23.0-android.99")>0);
        assertTrue(ReleaseRules.compareVersions("0.24.1-android.10","0.24.1-android.9")>0);
        assertEquals(0, ReleaseRules.compareVersions("0.24.1-android.1","0.24.1-android.1"));
    }
}
