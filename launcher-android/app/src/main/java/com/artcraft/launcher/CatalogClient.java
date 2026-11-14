package com.artcraft.launcher;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Read-only catalog backed by the owner's published public GitHub releases. */
public final class CatalogClient {
    static final String RELEASES = "https://api.github.com/repos/KosmosSG/artcraft-android/releases";
    static final String DOWNLOAD_PREFIX = "https://github.com/KosmosSG/artcraft-android/releases/download/";
    static final class App {
        final String name, key, letters, packageName;
        final int accent;
        App(String name, String letters, int accent) {
            this.name=name; this.key=name.toLowerCase(Locale.ROOT); this.letters=letters;
            this.packageName="com.artcraft."+key; this.accent=accent;
        }
    }
    static final App[] APPS = {
        new App("PhotoCraft","Pc",0xff21bad7),
        new App("VectorCraft","Vc",0xff649ce3),
        new App("DesignCraft","Dc",0xffb77cbb),
        new App("EffectCraft","Ec",0xff927be0),
        new App("LightCraft","Lc",0xffe1a754),
        new App("FilmCraft","Fc",0xffe5847b),
        new App("WordCraft","Wc",0xff5c9ce4),
        new App("GridCraft","Gc",0xff55bb91),
        new App("PDFCraft","Pdf",0xffdc7d78),
        new App("DeckCraft","Dk",0xffdd7f8b),
        new App("CADCraft","Cc",0xff9c8bc9),
        new App("SoundCraft","Sc",0xff58b2be),
        new App("FigCraft","Fg",0xff93a7b7)
    };

    static final class Release {
        final String version, tag, filename, apkUrl, checksumsUrl, notesUrl;
        final boolean preview;
        Release(String version,String tag,String filename,String apkUrl,String checksumsUrl,String notesUrl,boolean preview) {
            this.version=version; this.tag=tag; this.filename=filename; this.apkUrl=apkUrl;
            this.checksumsUrl=checksumsUrl; this.notesUrl=notesUrl; this.preview=preview;
        }
    }

    static Map<String,Release> fetch(boolean previews) throws Exception {
        Map<String,Release> found = new HashMap<>();
        for (int page=1;page<=5;page++) {
            String raw = getText(RELEASES+"?per_page=100&page="+page);
            JSONArray data = new JSONArray(raw);
            for (int i=0;i<data.length();i++) {
                JSONObject r = data.getJSONObject(i);
                if (r.optBoolean("draft",true) || (!previews && r.optBoolean("prerelease",false))) continue;
                String tag=r.optString("tag_name","");
                JSONArray assets=r.optJSONArray("assets");
                if (assets==null) continue;
                for (App app:APPS) {
                    String version=ReleaseRules.versionForTag(app.key,tag);
                    if (version==null) continue;
                    String apkName=null,apkUrl=null,checksums=null;
                    int matches=0;
                    for(int j=0;j<assets.length();j++) {
                        JSONObject a=assets.getJSONObject(j);
                        if (!"uploaded".equals(a.optString("state","uploaded")) || a.optLong("size",0)<=0) continue;
                        String name=a.optString("name","");
                        String url=a.optString("browser_download_url","");
                        if (!url.startsWith(DOWNLOAD_PREFIX+tag+"/")) continue;
                        if (ReleaseRules.isApkFor(app.name,app.key,version,name)) {
                            matches++; apkName=name; apkUrl=url;
                        } else if ("SHA256SUMS.txt".equals(name)) checksums=url;
                    }
                    // Require one unambiguous uploaded candidate and a published checksum asset.
                    if (matches!=1 || checksums==null) continue;
                    Release next=new Release(version,tag,apkName,apkUrl,checksums,
                        r.optString("html_url",""),r.optBoolean("prerelease",false));
                    Release prior=found.get(app.key);
                    if(prior==null || ReleaseRules.compareVersions(next.version,prior.version)>0)
                        found.put(app.key,next);
                }
            }
            if (data.length()<100) break;
        }
        return found;
    }

    /**
     * Future launcher updates require an independently published release with exact
     * tag, canonical ARM64 APK, SHA256SUMS.txt and matching signing identity.
     * No GitHub Actions disposable artifact qualifies as a production update.
     */
    static Release fetchLauncher(boolean includePreviews) throws Exception {
        Release best=null;
        for(int page=1;page<=5;page++) {
            JSONArray releases=new JSONArray(getText(RELEASES+"?per_page=100&page="+page));
            for(int i=0;i<releases.length();i++) {
                JSONObject release=releases.getJSONObject(i);
                if(release.optBoolean("draft",true) ||
                    (!includePreviews && release.optBoolean("prerelease",false))) continue;
                String tag=release.optString("tag_name","");
                String version=ReleaseRules.launcherVersionForTag(tag);
                if(version==null) continue;
                JSONArray assets=release.optJSONArray("assets");
                if(assets==null) continue;
                String apkName=null,apkUrl=null,checksumUrl=null;
                int matches=0;
                for(int j=0;j<assets.length();j++) {
                    JSONObject asset=assets.getJSONObject(j);
                    if(!"uploaded".equals(asset.optString("state","uploaded")) ||
                        asset.optLong("size",0)<=0) continue;
                    String name=asset.optString("name","");
                    String url=asset.optString("browser_download_url","");
                    if(!url.startsWith(DOWNLOAD_PREFIX+tag+"/")) continue;
                    if(ReleaseRules.isLauncherApkFor(version,name)) {
                        matches++;apkName=name;apkUrl=url;
                    } else if("SHA256SUMS.txt".equals(name)) checksumUrl=url;
                }
                if(matches!=1 || checksumUrl==null) continue;
                Release candidate=new Release(version,tag,apkName,apkUrl,
                    checksumUrl,release.optString("html_url",""),
                    release.optBoolean("prerelease",false));
                if(best==null || ReleaseRules.compareVersions(candidate.version,best.version)>0)
                    best=candidate;
            }
            if(releases.length()<100)break;
        }
        return best;
    }

    static String expectedSha256(Release release) throws Exception {
        String sums=getText(release.checksumsUrl);
        Pattern sum=Pattern.compile("^([0-9a-fA-F]{64})\\s+\\*?(.+)$");
        String answer=null;
        for(String line:sums.split("\\R")) {
            Matcher match=sum.matcher(line.trim());
            if(!match.matches()) continue;
            String checkName=match.group(2).trim();
            if(checkName.equals(release.filename) || checkName.equals("./"+release.filename)) {
                if(answer!=null && !answer.equalsIgnoreCase(match.group(1)))
                    throw new IllegalStateException("Conflicting SHA-256 entries");
                answer=match.group(1).toLowerCase(Locale.ROOT);
            }
        }
        if (answer==null) throw new IllegalStateException("Published SHA-256 for APK is missing");
        return answer;
    }

    private static String getText(String address) throws Exception {
        URL url=new URL(address);
        if (!"https".equals(url.getProtocol())) throw new IllegalArgumentException("HTTPS required");
        HttpURLConnection connection=(HttpURLConnection)url.openConnection();
        connection.setConnectTimeout(7000);
        connection.setReadTimeout(12000);
        connection.setRequestProperty("Accept","application/vnd.github+json");
        connection.setRequestProperty("User-Agent","ArtCraft-Android-Launcher/0.1");
        try {
            int status=connection.getResponseCode();
            if(status!=200) throw new IllegalStateException("GitHub HTTP "+status);
            if(connection.getContentLengthLong()>8_000_000L)
                throw new IllegalStateException("Unexpectedly large response");
            try(BufferedReader br=new BufferedReader(new InputStreamReader(connection.getInputStream(),StandardCharsets.UTF_8))) {
                StringBuilder out=new StringBuilder();
                String line;
                while((line=br.readLine())!=null) {
                    out.append(line).append('\n');
                    if(out.length()>8_000_000) throw new IllegalStateException("Response exceeds size limit");
                }
                return out.toString();
            }
        } finally { connection.disconnect(); }
    }
}
