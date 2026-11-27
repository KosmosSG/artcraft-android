package com.artcraft.launcher;

import org.junit.Test;
import static org.junit.Assert.*;

public final class CatalogClientTest {
    private CatalogClient.App app(String key) {
        for (CatalogClient.App app : CatalogClient.APPS) if (app.key.equals(key)) return app;
        return null;
    }

    @Test public void retainsOfficialCatalogAndAddsV07CommunityCatalog() {
        int official=0,community=0;
        for (CatalogClient.App app : CatalogClient.APPS) {
            if (app.community) community++; else official++;
        }
        assertEquals(13,official);
        assertEquals(28,community);
        assertEquals(41,CatalogClient.APPS.length);
    }

    @Test public void communityAppsNeverMatchOfficialSuiteReleaseFeed() {
        for (CatalogClient.App app : CatalogClient.APPS) {
            assertEquals(!app.community, CatalogClient.shouldMatchSuiteRelease(app));
        }
    }

    @Test public void communityAppsUseRealPackageIdsForInstalledDetection() {
        assertEquals("io.tangencylabs.solidcraft",app("solidcraft").packageName);
        assertEquals("org.rustgis.mobile",app("rustgis").packageName);
        assertEquals("dev.tracedraw.app",app("tracedraw").packageName);
        assertEquals("app.bramble.keydeck",app("keydeck").packageName);
        assertEquals("io.github.artcraftandroid.procraft",app("procraft").packageName);
        assertEquals("com.artcraft.pixelcraft",app("pixelcraft").packageName);
    }

    @Test public void everyCommunityEntryHasRepositoryAndPackage() {
        for (CatalogClient.App app : CatalogClient.APPS) {
            if (!app.community) continue;
            assertNotNull(app.repo);
            assertTrue(app.repo.contains("/"));
            assertNotNull(app.packageName);
            assertTrue(app.packageName.contains("."));
        }
    }
}
