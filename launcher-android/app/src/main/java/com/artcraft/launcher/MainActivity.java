package com.artcraft.launcher;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.res.Configuration;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ImageView;
import android.widget.PopupMenu;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.File;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Standalone tablet-first Craft suite dashboard. No changes to the managed apps. */
public final class MainActivity extends Activity {
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final Map<String,CatalogClient.Release> available=new HashMap<>();
    private SharedPreferences settings;
    private DownloadManager downloads;
    private LinearLayout root, list;
    private TextView banner, summary, downloadTitle, downloadInfo, downloadButton;
    private ProgressBar downloadProgress;
    private LinearLayout downloadPanel;
    private ScrollView scroller;
    private boolean dark,checking,checkingDownload, receiverRegistered;
    private File readyInstall;
    private String readyPackage;
    /** UI-only poll while a system DownloadManager transfer is active. */
    private final Runnable progressPoll=new Runnable() {
        @Override public void run() {
            updateDownloadProgress();
            if(settings!=null && (settings.getLong("download_id",-1L)>0 || checkingDownload))
                ui.postDelayed(this,750);
        }
    };

    private int bg,surface,border,foreground,muted,accent;
    private final BroadcastReceiver downloadReceiver=new BroadcastReceiver() {
        @Override public void onReceive(Context context,Intent intent) {
            if(!DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction())) return;
            long completed=intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID,-1);
            if(completed==settings.getLong("download_id",-2)) {
                inspectDownload();
                updateDownloadProgress();
            }
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        settings=getSharedPreferences("launcher",MODE_PRIVATE);
        downloads=(DownloadManager)getSystemService(DOWNLOAD_SERVICE);
        dark=(getResources().getConfiguration().uiMode&Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        if(settings.contains("dark_theme")) dark=settings.getBoolean("dark_theme",true);
        initPalette();
        buildLayout();
        IntentFilter filter=new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if(Build.VERSION.SDK_INT>=33) registerReceiver(downloadReceiver,filter,Context.RECEIVER_EXPORTED);
        else registerReceiver(downloadReceiver,filter);
        receiverRegistered=true;
        if(settings.getBoolean("startup_check",false)) refreshCatalog();
    }

    @Override protected void onResume() {
        super.onResume();
        if(root!=null) {
            updateCards(); inspectDownload(); updateDownloadProgress();
            ui.removeCallbacks(progressPoll); ui.postDelayed(progressPoll,750);
        }
        if(readyInstall!=null && (Build.VERSION.SDK_INT<26 || getPackageManager().canRequestPackageInstalls())) {
            File file=readyInstall; String pkg=readyPackage;
            readyInstall=null; readyPackage=null;
            openInstaller(file,pkg);
        }
    }

    @Override protected void onDestroy() {
        if(receiverRegistered) unregisterReceiver(downloadReceiver);
        ui.removeCallbacks(progressPoll);
        worker.shutdownNow();
        super.onDestroy();
    }

    private void initPalette() {
        bg=Color.parseColor(dark?"#0B1422":"#F4F7FB");
        surface=Color.parseColor(dark?"#17263B":"#FFFFFF");
        border=Color.parseColor(dark?"#2A4057":"#DAE4ED");
        foreground=Color.parseColor(dark?"#EDF6FD":"#182C40");
        muted=Color.parseColor(dark?"#A7B8CA":"#657587");
        accent=Color.parseColor("#40BFD7");
        getWindow().setStatusBarColor(bg);
        getWindow().setNavigationBarColor(bg);
        getWindow().getDecorView().setSystemUiVisibility(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    }

    private int dp(float n) { return (int)(n*getResources().getDisplayMetrics().density+0.5f); }
    private GradientDrawable shape(int fill,int stroke,int radius) {
        GradientDrawable d=new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(dp(radius));
        if(stroke!=Color.TRANSPARENT) d.setStroke(dp(1),stroke);
        return d;
    }

    /** Shared icon treatment: same rounded-square gradient and lettering as ArtCraft's Ac badge. */
    private int mix(int base,int tint,float part) {
        float rest=1f-part;
        return Color.rgb(
            Math.round(Color.red(base)*rest+Color.red(tint)*part),
            Math.round(Color.green(base)*rest+Color.green(tint)*part),
            Math.round(Color.blue(base)*rest+Color.blue(tint)*part));
    }
    private TextView artCraftBadge(String letters,int diameterDp,int tint) {
        int typeSize=letters.length()>2?14:diameterDp>=50?25:20;
        TextView badge=text(letters,typeSize,Color.WHITE,true);
        badge.setTypeface(Typeface.create("sans-serif-medium",Typeface.BOLD));
        badge.setGravity(Gravity.CENTER);
        int darkStop=mix(Color.rgb(19,43,69),tint,0.44f);
        int lightStop=mix(Color.rgb(23,61,91),tint,0.88f);
        GradientDrawable background=new GradientDrawable(
            GradientDrawable.Orientation.TL_BR,new int[]{darkStop,lightStop});
        background.setCornerRadius(dp(diameterDp*0.29f));
        background.setStroke(dp(1),mix(Color.WHITE,tint,0.73f));
        badge.setBackground(background);
        return badge;
    }

    private TextView text(String value,int sp,int color,boolean bold) {
        TextView t=new TextView(this);
        t.setText(value); t.setTextColor(color); t.setTextSize(sp);
        t.setGravity(Gravity.CENTER_VERTICAL);
        if(bold) t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return t;
    }
    private LinearLayout vertical() {
        LinearLayout l=new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);return l;
    }
    private LinearLayout horizontal() {
        LinearLayout l=new LinearLayout(this);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);return l;
    }

    private TextView action(String label,boolean primary,int color,Runnable click) {
        TextView button=text(label,13,primary?Color.WHITE:foreground,true);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(13),dp(10),dp(13),dp(10));
        button.setBackground(shape(primary?color:surface,primary?Color.TRANSPARENT:border,11));
        button.setOnClickListener(v->click.run());
        return button;
    }

    private void buildLayout() {
        root=vertical();root.setBackgroundColor(bg);
        setContentView(root);
        LinearLayout head=horizontal();
        head.setPadding(dp(18),dp(16),dp(18),dp(13));
        root.addView(head,new LinearLayout.LayoutParams(-1,dp(82)));
        TextView emblem=artCraftBadge("Ac",52,Color.parseColor("#28BBD4"));
        head.addView(emblem,new LinearLayout.LayoutParams(dp(52),dp(52)));
        LinearLayout heading=vertical();
        heading.setPadding(dp(12),0,0,0);
        head.addView(heading,new LinearLayout.LayoutParams(0,-2,1f));
        heading.addView(text("ArtCraft",25,foreground,true));
        heading.addView(text("ANDROID SUITE  ·  LAUNCHER",10,muted,true));
        TextView refresh=action("Check Updates",true,Color.parseColor("#207B9E"),this::refreshCatalog);
        head.addView(refresh);
        TextView menu=text(" ⋮ ",25,foreground,true);
        menu.setGravity(Gravity.CENTER);
        menu.setPadding(dp(9),0,dp(1),0);
        head.addView(menu,new LinearLayout.LayoutParams(dp(43),dp(48)));
        menu.setOnClickListener(v->openMenu(menu));

        scroller=new ScrollView(this);
        scroller.setFillViewport(true);scroller.setClipToPadding(false);
        root.addView(scroller,new LinearLayout.LayoutParams(-1,0,1f));
        LinearLayout page=vertical();page.setPadding(dp(17),dp(7),dp(17),dp(20));
        scroller.addView(page);
        LinearLayout welcome=vertical();
        welcome.setPadding(dp(19),dp(17),dp(19),dp(17));
        welcome.setBackground(shape(surface,border,18));
        page.addView(welcome,new LinearLayout.LayoutParams(-1,-2));
        welcome.addView(text("Your creative workspace, all in one place",19,foreground,true));
        TextView descriptor=text("Open installed apps, check published GitHub releases, and manage updates with Android's installer.",13,muted,false);
        descriptor.setPadding(0,dp(7),0,dp(8));
        welcome.addView(descriptor);
        summary=text("",12,accent,true);
        welcome.addView(summary);
        TextView section=text("YOUR APPS",12,muted,true);
        section.setPadding(dp(4),dp(23),0,dp(12));
        page.addView(section);
        list=vertical();page.addView(list);
        downloadPanel=vertical();
        downloadPanel.setPadding(dp(18),dp(12),dp(18),dp(12));
        downloadPanel.setBackground(shape(surface,border,12));
        LinearLayout.LayoutParams downloadLp=new LinearLayout.LayoutParams(-1,-2);
        downloadLp.setMargins(dp(18),0,dp(18),dp(8));
        root.addView(downloadPanel,downloadLp);
        LinearLayout downloadRow=horizontal();
        downloadPanel.addView(downloadRow,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout downloadText=vertical();
        downloadRow.addView(downloadText,new LinearLayout.LayoutParams(0,-2,1f));
        downloadTitle=text("Downloading…",14,foreground,true);
        downloadInfo=text("Starting download",12,muted,false);
        downloadInfo.setPadding(0,dp(2),0,0);
        downloadText.addView(downloadTitle);
        downloadText.addView(downloadInfo);
        downloadButton=action("Cancel",false,accent,this::cancelDownload);
        LinearLayout.LayoutParams buttonLp=new LinearLayout.LayoutParams(dp(96),dp(38));
        buttonLp.setMargins(dp(8),0,0,0);
        downloadRow.addView(downloadButton,buttonLp);
        downloadProgress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
        downloadProgress.setMax(100);
        downloadProgress.setProgressTintList(android.content.res.ColorStateList.valueOf(accent));
        LinearLayout.LayoutParams barLp=new LinearLayout.LayoutParams(-1,dp(5));
        barLp.setMargins(0,dp(10),0,0);
        downloadPanel.addView(downloadProgress,barLp);
        downloadPanel.setVisibility(View.GONE);
        banner=text("Updates are checked manually. You can enable startup checking in settings.",12,foreground,false);
        banner.setPadding(dp(18),dp(12),dp(18),dp(12));
        banner.setBackground(shape(surface,border,0));
        root.addView(banner,new LinearLayout.LayoutParams(-1,-2));
        updateCards();
    }

    private void updateCards() {
        if(list==null)return;
        int position=scroller==null?0:scroller.getScrollY();
        list.removeAllViews();
        int columns=getResources().getConfiguration().screenWidthDp>=950?3:2;
        int installed=0,updates=0;
        for(CatalogClient.App app:CatalogClient.APPS) {
            PackageInfo pkg=installed(app.packageName);
            if(pkg!=null) installed++;
            CatalogClient.Release remote=available.get(app.key);
            if(pkg!=null && remote!=null && ReleaseRules.compareVersions(remote.version,pkg.versionName)>0) updates++;
        }
        String intro=installed+" of "+CatalogClient.APPS.length+" apps installed   •   "+
            (checking?"Checking releases…":updates+" updates identified");
        summary.setText(intro);
        for(int i=0;i<CatalogClient.APPS.length;i+=columns) {
            LinearLayout row=horizontal();
            row.setGravity(Gravity.TOP);
            list.addView(row,new LinearLayout.LayoutParams(-1,-2));
            for(int j=0;j<columns;j++) {
                int idx=i+j;
                if(idx>=CatalogClient.APPS.length) {
                    View blank=new View(this);
                    row.addView(blank,new LinearLayout.LayoutParams(0,dp(1),1f));
                    continue;
                }
                CatalogClient.App app=CatalogClient.APPS[idx];
                LinearLayout.LayoutParams cardLp=new LinearLayout.LayoutParams(0,-2,1f);
                cardLp.setMargins(dp(4),dp(4),dp(4),dp(8));
                row.addView(appCard(app),cardLp);
            }
        }
        if(scroller!=null)scroller.post(()->scroller.scrollTo(0,position));
    }

    /**
     * Use the installed app's actual Android launcher artwork, including adaptive
     * or illustrative icons, instead of approximating it with colored initials.
     * Keep the Ac-style placeholder only when an app has no accessible icon.
     */
    private View appIcon(CatalogClient.App app) {
        try {
            android.graphics.drawable.Drawable actual =
                getPackageManager().getApplicationIcon(app.packageName);
            if (actual != null) {
                ImageView icon = new ImageView(this);
                icon.setImageDrawable(actual);
                icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
                icon.setContentDescription(app.name + " app icon");
                return icon;
            }
        } catch (PackageManager.NameNotFoundException | SecurityException ignored) {
            // App not installed, package not visible or icon inaccessible.
        }
        return artCraftBadge(app.letters,46,app.accent);
    }

    private View appCard(CatalogClient.App app) {
        PackageInfo installed=installed(app.packageName);
        CatalogClient.Release remote=available.get(app.key);
        LinearLayout card=vertical();
        card.setPadding(dp(13),dp(14),dp(13),dp(14));
        card.setBackground(shape(surface,border,17));
        LinearLayout row=horizontal();card.addView(row);
        View icon=appIcon(app);
        row.addView(icon,new LinearLayout.LayoutParams(dp(46),dp(46)));
        LinearLayout title=vertical();title.setPadding(dp(10),0,0,0);
        row.addView(title,new LinearLayout.LayoutParams(0,-2,1f));
        title.addView(text(app.name,15,foreground,true));
        title.addView(text(installed!=null?"Installed":"Not installed",11,muted,false));
        String note;
        if(remote==null)note="No eligible published APK";
        else note=(remote.preview?"Preview ":"Release ")+"v"+remote.version;
        TextView detail=text(note,11,muted,false);
        detail.setMaxLines(2);
        detail.setPadding(0,dp(11),0,dp(9));
        card.addView(detail);
        if(installed!=null) {
            TextView current=text("On device: v"+safe(installed.versionName),11,muted,false);
            current.setMaxLines(1);current.setEllipsize(android.text.TextUtils.TruncateAt.END);
            card.addView(current);
        }
        boolean needsUpdate=installed!=null && remote!=null &&
            ReleaseRules.compareVersions(remote.version,installed.versionName)>0;
        LinearLayout buttons=horizontal();
        buttons.setPadding(0,dp(12),0,0);
        card.addView(buttons);
        String label=needsUpdate?"Update":installed!=null?"Open":remote!=null?"Install":"Releases";
        Runnable onPrimary;
        if(needsUpdate || (installed==null && remote!=null))
            onPrimary=()->confirmDownload(app,remote);
        else if(installed!=null)onPrimary=()->openApp(app);
        else onPrimary=()->openReleases();
        TextView primary=action(label,true,app.accent,onPrimary);
        buttons.addView(primary,new LinearLayout.LayoutParams(0,dp(40),1f));
        TextView secondary=action(installed!=null?"Info":"Details",false,app.accent,
            ()->{ if(remote==null) openReleases(); else openUrl(remote.notesUrl); });
        LinearLayout.LayoutParams secondLp=new LinearLayout.LayoutParams(0,dp(40),1f);
        secondLp.setMargins(dp(6),0,0,0);
        buttons.addView(secondary,secondLp);
        return card;
    }

    private PackageInfo installed(String name) {
        try {
            int flags=Build.VERSION.SDK_INT>=28?PackageManager.GET_SIGNING_CERTIFICATES:PackageManager.GET_SIGNATURES;
            return getPackageManager().getPackageInfo(name,flags);
        } catch(PackageManager.NameNotFoundException e) {return null;}
    }
    private String safe(String s) { return s==null?"unknown":s; }

    private void openApp(CatalogClient.App app) {
        Intent intent=getPackageManager().getLaunchIntentForPackage(app.packageName);
        if(intent==null) {notice("Installed app has no launchable activity");return;}
        try { startActivity(intent); }
        catch(Exception e) {notice("Unable to launch "+app.name);}
    }
    private void openUrl(String url) {
        if(url==null || !url.startsWith("https://github.com/KosmosSG/artcraft-android/releases/")) {
            openReleases();return;
        }
        startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));
    }
    private void openReleases() {
        startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://github.com/KosmosSG/artcraft-android/releases")));
    }

    private void openMenu(View anchor) {
        PopupMenu popup=new PopupMenu(this,anchor);
        popup.getMenu().add(0,1,0,"Check for Updates");
        popup.getMenu().add(0,2,1,"Startup checks: "+(settings.getBoolean("startup_check",false)?"ON":"OFF"));
        popup.getMenu().add(0,3,2,"Channel: "+(settings.getBoolean("preview",true)?"Stable + Preview":"Stable only"));
        popup.getMenu().add(0,4,3,"Theme: "+(dark?"Dark":"Light"));
        popup.getMenu().add(0,5,4,"GitHub Releases");
        popup.getMenu().add(0,7,5,"Downloads");
        popup.getMenu().add(0,6,6,"About ArtCraft Launcher");
        popup.setOnMenuItemClickListener(item->{
            int id=item.getItemId();
            if(id==1)refreshCatalog();
            else if(id==2) { boolean next=!settings.getBoolean("startup_check",false);
                settings.edit().putBoolean("startup_check",next).apply();
                notice("Startup checks "+(next?"enabled":"disabled")); }
            else if(id==3) {settings.edit().putBoolean("preview",!settings.getBoolean("preview",true)).apply();refreshCatalog();}
            else if(id==4) {settings.edit().putBoolean("dark_theme",!dark).apply();recreate();}
            else if(id==5)openReleases();
            else if(id==7) {
                updateDownloadProgress();
                if(downloadPanel.getVisibility()==View.GONE)
                    notice("No active downloads. Select Install or Update on an app card.");
            }
            else if(id==6)new AlertDialog.Builder(this)
                .setTitle("ArtCraft Android Launcher")
                .setMessage("v0.1.0-android.4  •  ARM64 TEST ONLY\n\nA separate hub for 13 ArtCraft Android apps. This launcher does not modify your existing application data. APK installs require your approval.")
                .setPositiveButton("OK",null).show();
            return true;
        });
        popup.show();
    }

    private void refreshCatalog() {
        if(checking) return;
        checking=true;
        notice("Checking published ArtCraft releases…");
        updateCards();
        final boolean includePreviews=settings.getBoolean("preview",true);
        worker.execute(()->{
            try {
                Map<String,CatalogClient.Release> result=CatalogClient.fetch(includePreviews);
                ui.post(()->{
                    checking=false;available.clear();available.putAll(result);
                    updateCards();notice("Found matching releases for "+result.size()+" apps");
                });
            } catch(Exception e) {
                ui.post(()->{checking=false;updateCards();notice("Update check unavailable: "+e.getMessage());});
            }
        });
    }

    private void confirmDownload(CatalogClient.App app,CatalogClient.Release release) {
        if(settings.getLong("download_id",-1)>0) {
            notice("Finish the current APK download first");return;
        }
        PackageInfo installed=installed(app.packageName);
        if(installed!=null && ReleaseRules.compareVersions(release.version,installed.versionName)<=0) {
            notice("No strictly newer release detected; browse release details");openUrl(release.notesUrl);return;
        }
        String msg=(installed==null?"Install ":"Update ")+app.name+" v"+release.version+"?"+
            "\n\nFrom KosmosSG GitHub Releases"+(release.preview?" (Preview channel)":" (Stable channel)")+
            "\n\nThe launcher verifies SHA-256, app package, versionCode and signing compatibility before asking Android to install. No silent changes.";
        new AlertDialog.Builder(this).setTitle("Review APK download")
            .setMessage(msg).setNegativeButton("Cancel",null)
            .setPositiveButton("Download APK",(d,w)->startDownload(app,release)).show();
    }

    private void startDownload(CatalogClient.App app,CatalogClient.Release release) {
        notice("Verifying published checksum for "+app.name+"…");
        worker.execute(()->{
            try {
                String sha=CatalogClient.expectedSha256(release);
                ui.post(()->enqueue(app,release,sha));
            } catch(Exception e) {
                ui.post(()->notice("Cannot verify "+app.name+" release: "+e.getMessage()));
            }
        });
    }

    private void enqueue(CatalogClient.App app,CatalogClient.Release release,String sha) {
        if(settings.getLong("download_id",-1)>0) {notice("Another download is in progress");return;}
        try {
            if(!release.apkUrl.startsWith(CatalogClient.DOWNLOAD_PREFIX+release.tag+"/"))
                throw new IllegalStateException("Unexpected GitHub asset URL");
            File directory=getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            if(directory==null) throw new IllegalStateException("Storage unavailable");
            String filename="ArtCraft-"+app.key+"-"+release.version+".apk";
            File local=new File(directory,filename);
            if(local.exists() && !local.delete()) throw new IllegalStateException("Old APK could not be replaced");
            DownloadManager.Request request=new DownloadManager.Request(Uri.parse(release.apkUrl));
            request.setTitle(app.name+" v"+release.version);
            request.setDescription("ArtCraft Launcher – verified GitHub release");
            request.setAllowedOverMetered(true);
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalFilesDir(this,Environment.DIRECTORY_DOWNLOADS,filename);
            long id=downloads.enqueue(request);
            settings.edit().putLong("download_id",id).putString("download_file",filename)
                .putString("download_sha",sha).putString("download_package",app.packageName)
                .putString("download_version",release.version).apply();
            notice("Downloading "+app.name+" inside ArtCraft Launcher…");
            updateDownloadProgress();
            ui.removeCallbacks(progressPoll);
            ui.postDelayed(progressPoll,750);
        } catch(Exception e) {notice("Download failed to start: "+e.getMessage());}
    }

    private void inspectDownload() {
        if(checkingDownload || downloads==null || settings==null)return;
        long id=settings.getLong("download_id",-1);
        if(id<=0)return;
        int status;
        try(Cursor c=downloads.query(new DownloadManager.Query().setFilterById(id))) {
            if(c==null || !c.moveToFirst())return;
            status=c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
        } catch(Exception e) {return;}
        if(status==DownloadManager.STATUS_FAILED) {
            clearPending();updateDownloadProgress();
            notice("APK download failed; please try again");return;
        }
        if(status!=DownloadManager.STATUS_SUCCESSFUL)return;
        checkingDownload=true;
        updateDownloadProgress();
        String filename=settings.getString("download_file","");
        String sha=settings.getString("download_sha","");
        String pkg=settings.getString("download_package","");
        String version=settings.getString("download_version","");
        clearPending();
        worker.execute(()->{
            try {
                File folder=getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                if(folder==null || !filename.matches("ArtCraft-[A-Za-z0-9.-]+\\.apk"))
                    throw new IllegalStateException("Invalid download location");
                File file=new File(folder,filename);
                if(!file.getCanonicalFile().getParentFile().equals(folder.getCanonicalFile()))
                    throw new IllegalStateException("APK path mismatch");
                if(!file.isFile() || file.length()<1024)
                    throw new IllegalStateException("Downloaded APK is empty");
                String calculated=sha256(file);
                if(!calculated.equalsIgnoreCase(sha)) throw new IllegalStateException("APK SHA-256 does not match release");
                checkApkIdentity(file,pkg,version);
                ui.post(()->{
                    checkingDownload=false;
                    readyInstall=file;readyPackage=pkg;
                    updateDownloadProgress();
                    notice("Download verified. Tap Install inside the launcher to continue.");
                });
            } catch(Exception e) {
                ui.post(()->{checkingDownload=false;updateDownloadProgress();notice("APK rejected: "+e.getMessage());});
            }
        });
    }

    private void setDownloadButton(String label,Runnable click) {
        if(downloadButton==null)return;
        downloadButton.setText(label);
        downloadButton.setOnClickListener(v->click.run());
    }

    private void updateDownloadProgress() {
        if(downloadPanel==null || settings==null || downloads==null)return;
        long id=settings.getLong("download_id",-1L);
        if(id<=0) {
            if(checkingDownload) {
                downloadPanel.setVisibility(View.VISIBLE);
                downloadTitle.setText("Verifying downloaded APK");
                downloadInfo.setText("Checking SHA-256, package, version and signing certificate…");
                downloadProgress.setIndeterminate(true);
                downloadButton.setVisibility(View.GONE);
            } else if(readyInstall!=null) {
                downloadPanel.setVisibility(View.VISIBLE);
                downloadTitle.setText("APK verified — ready to install");
                downloadInfo.setText(readyInstall.getName());
                downloadProgress.setIndeterminate(false);
                downloadProgress.setProgress(100);
                downloadButton.setVisibility(View.VISIBLE);
                setDownloadButton("Install",()->{
                    if(readyInstall!=null)offerInstaller(readyInstall,readyPackage);
                });
            } else downloadPanel.setVisibility(View.GONE);
            return;
        }
        downloadPanel.setVisibility(View.VISIBLE);
        downloadButton.setVisibility(View.VISIBLE);
        setDownloadButton("Cancel",this::cancelDownload);
        try(Cursor cursor=downloads.query(new DownloadManager.Query().setFilterById(id))) {
            if(cursor==null || !cursor.moveToFirst()) {
                downloadTitle.setText("Preparing download");
                downloadInfo.setText("Waiting for Android Download Manager…");
                downloadProgress.setIndeterminate(true);
                return;
            }
            int status=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
            long current=cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
            long total=cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
            String name=settings.getString("download_package","ArtCraft").replace("com.artcraft.","");
            if(status==DownloadManager.STATUS_SUCCESSFUL) {
                downloadTitle.setText("Download complete");
                downloadInfo.setText("Verifying downloaded APK…");
                downloadProgress.setIndeterminate(true);
                downloadButton.setVisibility(View.GONE);
                inspectDownload();
                return;
            }
            if(status==DownloadManager.STATUS_FAILED) {
                clearPending();downloadPanel.setVisibility(View.GONE);
                notice("Download failed. Please try again.");return;
            }
            downloadTitle.setText("Downloading "+name+"…");
            if(total>0) {
                int percent=(int)Math.min(100,100L*current/total);
                downloadProgress.setIndeterminate(false);
                downloadProgress.setProgress(percent);
                downloadInfo.setText(percent+"%  •  "+formatBytes(current)+" / "+formatBytes(total));
            } else {
                downloadProgress.setIndeterminate(true);
                downloadInfo.setText(formatBytes(current)+" received  •  "+(status==DownloadManager.STATUS_PAUSED?"Waiting for network":"Downloading"));
            }
        } catch(Exception e) {
            downloadInfo.setText("Download status temporarily unavailable");
            downloadProgress.setIndeterminate(true);
        }
    }

    private String formatBytes(long size) {
        if(size<1024)return size+" B";
        if(size<1024L*1024)return String.format(Locale.ROOT,"%.1f KB",size/1024.0);
        return String.format(Locale.ROOT,"%.1f MB",size/(1024.0*1024));
    }

    private void cancelDownload() {
        long id=settings.getLong("download_id",-1L);
        if(id<=0)return;
        try { downloads.remove(id); } catch(Exception ignored) {}
        clearPending();
        ui.removeCallbacks(progressPoll);
        updateDownloadProgress();
        notice("APK download cancelled. No installed apps were changed.");
    }

    private void clearPending() {
        settings.edit().remove("download_id").remove("download_file").remove("download_sha")
            .remove("download_package").remove("download_version").apply();
    }

    private String sha256(File file) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(FileInputStream stream=new FileInputStream(file)) {
            byte[] bytes=new byte[65536];int n;
            while((n=stream.read(bytes))!=-1)digest.update(bytes,0,n);
        }
        StringBuilder sb=new StringBuilder();
        for(byte b:digest.digest())sb.append(String.format(Locale.ROOT,"%02x",b&0xff));
        return sb.toString();
    }

    private void checkApkIdentity(File file,String expectedPackage,String expectedVersion) throws Exception {
        int flags=Build.VERSION.SDK_INT>=28?PackageManager.GET_SIGNING_CERTIFICATES:PackageManager.GET_SIGNATURES;
        PackageInfo apk=getPackageManager().getPackageArchiveInfo(file.getAbsolutePath(),flags);
        if(apk==null || !expectedPackage.equals(apk.packageName))
            throw new IllegalStateException("APK package identity mismatch");
        if(apk.versionName==null || !expectedVersion.equals(apk.versionName))
            throw new IllegalStateException("APK versionName does not match GitHub release tag");
        Set<String> apkCerts=signingDigests(apk);
        if(apkCerts.isEmpty()) throw new IllegalStateException("Cannot verify APK signer");
        PackageInfo prior=installed(expectedPackage);
        if(prior!=null) {
            long oldVersion=Build.VERSION.SDK_INT>=28?prior.getLongVersionCode():prior.versionCode;
            long newVersion=Build.VERSION.SDK_INT>=28?apk.getLongVersionCode():apk.versionCode;
            if(newVersion<=oldVersion)throw new IllegalStateException("APK versionCode must increase");
            if(!apkCerts.equals(signingDigests(prior)))
                throw new IllegalStateException("Signer differs from the installed application; update blocked");
        }
    }

    private Set<String> signingDigests(PackageInfo pkg) throws Exception {
        Signature[] signers;
        if(Build.VERSION.SDK_INT>=28) {
            if(pkg.signingInfo==null)return new HashSet<>();
            signers=pkg.signingInfo.getApkContentsSigners();
        } else signers=pkg.signatures;
        Set<String> values=new HashSet<>();
        if(signers!=null)for(Signature sig:signers) {
            byte[] hashed=MessageDigest.getInstance("SHA-256").digest(sig.toByteArray());
            values.add(Arrays.toString(hashed));
        }
        return values;
    }

    private void offerInstaller(File file,String pkg) {
        if(Build.VERSION.SDK_INT>=26 && !getPackageManager().canRequestPackageInstalls()) {
            new AlertDialog.Builder(this).setTitle("Allow APK installation")
                .setMessage("Android must allow ArtCraft Launcher to request app installations. The system will ask you to confirm the individual APK separately.")
                .setPositiveButton("Open Settings",(d,w)->{
                    Intent i=new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:"+getPackageName()));
                    startActivity(i);
                }).setNegativeButton("Not now",null).show();
        } else {
            new AlertDialog.Builder(this).setTitle("APK verified")
                .setMessage("SHA-256, application identity and update compatibility checks passed. Continue to Android's installer?")
.setNegativeButton("Not now",null)
                .setPositiveButton("Continue",(d,w)->{
                    readyInstall=null;readyPackage=null;
                    updateDownloadProgress();
                    openInstaller(file,pkg);
                }).show();
        }
    }

    private void openInstaller(File file,String pkg) {
        try {
            Uri uri=new Uri.Builder().scheme("content").authority(ApkProvider.AUTHORITY)
                .appendPath(file.getName()).build();
            Intent intent=new Intent(Intent.ACTION_VIEW);
            intent.setDataAndType(uri,"application/vnd.android.package-archive");
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        } catch(Exception e) {
            notice("Android installer unavailable: "+e.getMessage());
        }
    }

    private void notice(String message) {
        if(banner!=null)banner.setText(message);
    }
}
