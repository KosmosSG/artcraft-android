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
import android.graphics.drawable.ColorDrawable;
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
import android.widget.PopupWindow;
import android.widget.ProgressBar;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.text.Editable;
import android.text.TextWatcher;
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
    private LinearLayout root, list, filterRow;
    private EditText searchField;
    private TextView gridToggle, tableToggle;
    private String searchQuery = "";
    private int activeFilter = 0; // 0 all, 1 installed, 2 updates, 3 not installed
    private boolean tableView = false;
    private TextView banner, summary, downloadTitle, downloadInfo, downloadButton;
    private ProgressBar downloadProgress;
    private LinearLayout downloadPanel;
    private ScrollView scroller;
    private boolean dark,checking,checkingDownload,checkingLauncher,receiverRegistered,catalogLoaded;
    private final Set<String> activeAppLookups=new HashSet<>();
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

    private int bg,surface,border,foreground,muted,accent,buttonFill,buttonOutline;
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
        if(settings.getBoolean("launcher_startup_check",false)) checkLauncherUpdate(true);
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
        // Match the v0.7.0 launcher UI: warm paper / near-black surfaces, hairline rules,
        // restrained blue accent, and inverted monochrome primary controls.
        bg=Color.parseColor(dark?"#121316":"#F2F1EE");
        surface=bg;
        border=dark?Color.argb(38,242,241,238):Color.argb(41,16,16,20);
        foreground=Color.parseColor(dark?"#F2F1EE":"#101014");
        muted=dark?Color.argb(153,242,241,238):Color.argb(158,16,16,20);
        accent=Color.parseColor(dark?"#74AAFF":"#1659C4");
        buttonFill=Color.parseColor(dark?"#FFFFFF":"#101014");
        buttonOutline=dark?Color.argb(102,242,241,238):Color.argb(102,16,16,20);
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
        int ink=primary?Color.parseColor(dark?"#0B0B0C":"#F2F1EE"):foreground;
        TextView button=text(label,13,ink,true);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(13),dp(10),dp(13),dp(10));
        button.setBackground(shape(primary?buttonFill:Color.TRANSPARENT,
            primary?Color.TRANSPARENT:buttonOutline,0));
        button.setOnClickListener(v->click.run());
        return button;
    }

    private void buildLayout() {
        root=vertical();root.setBackgroundColor(bg);
        setContentView(root);
        LinearLayout head=horizontal();
        head.setPadding(dp(16),0,dp(16),0);
        root.addView(head,new LinearLayout.LayoutParams(-1,dp(52)));
        ImageView emblem=new ImageView(this);
        emblem.setImageResource(R.drawable.ac_brand_icon);
        emblem.setScaleType(ImageView.ScaleType.FIT_CENTER);
        emblem.setContentDescription("ArtCraft Ac logo");
        head.addView(emblem,new LinearLayout.LayoutParams(dp(30),dp(30)));
        LinearLayout heading=vertical();
        heading.setPadding(dp(12),0,0,0);
        head.addView(heading,new LinearLayout.LayoutParams(0,-2,1f));
        heading.addView(text("Craft App Suite",18,foreground,true));
        TextView refresh=text("↻",21,muted,false);
        refresh.setGravity(Gravity.CENTER);
        refresh.setContentDescription("Check for updates");
        head.addView(refresh,new LinearLayout.LayoutParams(dp(42),dp(46)));
        refresh.setOnClickListener(v->refreshCatalog());
        TextView menu=text("⚙",19,muted,false);
        menu.setGravity(Gravity.CENTER);
        menu.setPadding(dp(9),0,dp(1),0);
        head.addView(menu,new LinearLayout.LayoutParams(dp(43),dp(48)));
        menu.setOnClickListener(v->openMenu(menu));

        scroller=new ScrollView(this);
        scroller.setFillViewport(true);scroller.setClipToPadding(false);
        root.addView(scroller,new LinearLayout.LayoutParams(-1,0,1f));
        LinearLayout page=vertical();page.setPadding(dp(17),dp(7),dp(17),dp(20));
        scroller.addView(page);
        addCatalogToolbar(page);
        summary=text("",12,muted,false);
        summary.setPadding(dp(2),dp(10),dp(2),dp(8));
        page.addView(summary);
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
        banner=text("Updates are checked manually. You can enable startup checking in settings.",13,foreground,false);
        banner.setPadding(dp(18),dp(14),dp(18),dp(14));
        banner.setBackground(shape(dark?Color.BLACK:Color.parseColor("#E5E9EC"),border,0));
        root.addView(banner,new LinearLayout.LayoutParams(-1,-2));
        updateCards();
    }

    private boolean officialExpanded = true;
    private boolean communityExpanded = false;

    private void addCatalogToolbar(LinearLayout page) {
        LinearLayout controls=horizontal();
        controls.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams controlsLp=new LinearLayout.LayoutParams(-1,dp(42));
        controlsLp.setMargins(0,dp(12),0,dp(4));
        page.addView(controls,controlsLp);
        searchField=new EditText(this);
        searchField.setSingleLine(true); searchField.setTextSize(14);
        searchField.setTextColor(foreground); searchField.setHintTextColor(muted);
        searchField.setHint("Search apps"); searchField.setPadding(dp(13),0,dp(10),0);
        searchField.setBackground(shape(surface,border,0)); searchField.setText(searchQuery);
        controls.addView(searchField,new LinearLayout.LayoutParams(0,-1,1f));
        searchField.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence value,int start,int count,int after) {}
            @Override public void onTextChanged(CharSequence value,int start,int before,int count) {
                searchQuery=value==null?"":value.toString(); updateCards();
            }
            @Override public void afterTextChanged(Editable value) {}
        });
        gridToggle=text("▦",21,tableView?muted:Color.WHITE,true);
        gridToggle.setGravity(Gravity.CENTER); gridToggle.setContentDescription("Show apps as cards");
        gridToggle.setBackground(shape(tableView?Color.TRANSPARENT:buttonFill,border,0));
        LinearLayout.LayoutParams toggleLp=new LinearLayout.LayoutParams(dp(44),-1);
        toggleLp.setMargins(dp(7),0,0,0); controls.addView(gridToggle,toggleLp);
        gridToggle.setOnClickListener(v->{tableView=false;updateCards();});
        tableToggle=text("☷",21,tableView?Color.WHITE:muted,true);
        tableToggle.setGravity(Gravity.CENTER); tableToggle.setContentDescription("Show apps as a table");
        tableToggle.setBackground(shape(tableView?buttonFill:Color.TRANSPARENT,border,0));
        LinearLayout.LayoutParams tableLp=new LinearLayout.LayoutParams(dp(44),-1);
        tableLp.setMargins(dp(5),0,0,0); controls.addView(tableToggle,tableLp);
        tableToggle.setOnClickListener(v->{tableView=true;updateCards();});
        HorizontalScrollView filters=new HorizontalScrollView(this);
        filters.setHorizontalScrollBarEnabled(false);
        LinearLayout.LayoutParams filtersLp=new LinearLayout.LayoutParams(-1,dp(42));
        filtersLp.setMargins(0,dp(4),0,dp(7)); page.addView(filters,filtersLp);
        filterRow=horizontal(); filterRow.setGravity(Gravity.CENTER_VERTICAL);
        filters.addView(filterRow); updateFilterButtons();
    }

    private void updateFilterButtons() {
        if(filterRow==null)return;
        filterRow.removeAllViews();
        String[] labels={"All apps","Installed","Updates","Not installed"};
        for(int i=0;i<labels.length;i++) {
            final int selected=i;
            TextView chip=action(labels[i],activeFilter==i,accent,()->{
                activeFilter=selected; updateFilterButtons(); updateCards();
            });
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-2,dp(34));
            lp.setMargins(0,0,dp(7),0); filterRow.addView(chip,lp);
        }
    }

    private boolean matchesCatalog(CatalogClient.App app) {
        PackageInfo pkg=installed(app.packageName);
        CatalogClient.Release release=available.get(app.key);
        if(activeFilter==1 && pkg==null)return false;
        if(activeFilter==2 && (pkg==null || release==null ||
            ReleaseRules.compareVersions(release.version,pkg.versionName)<=0))return false;
        if(activeFilter==3 && pkg!=null)return false;
        String needle=searchQuery.trim().toLowerCase(Locale.ROOT);
        return needle.isEmpty() || app.name.toLowerCase(Locale.ROOT).contains(needle) ||
            app.key.toLowerCase(Locale.ROOT).contains(needle) ||
            (app.repo!=null && app.repo.toLowerCase(Locale.ROOT).contains(needle));
    }

    private void updateCards() {
        if(list==null)return;
        int position=scroller==null?0:scroller.getScrollY();
        list.removeAllViews();
        int width=getResources().getConfiguration().screenWidthDp;
        int columns=width<680?1:(width<1050?2:3);
        int installedCount=0,updates=0,officialCount=0;
        java.util.ArrayList<CatalogClient.App> official=new java.util.ArrayList<>();
        java.util.ArrayList<CatalogClient.App> community=new java.util.ArrayList<>();
        for(CatalogClient.App app:CatalogClient.APPS) {
            PackageInfo pkg=installed(app.packageName);
            if(pkg!=null)installedCount++;
            CatalogClient.Release remote=available.get(app.key);
            if(pkg!=null && remote!=null && ReleaseRules.compareVersions(remote.version,pkg.versionName)>0)updates++;
            if(matchesCatalog(app)) { if(app.community)community.add(app); else official.add(app); }
            if(!app.community)officialCount++;
        }
        int communityCount=CatalogClient.APPS.length-officialCount;
        summary.setText(installedCount+" of "+CatalogClient.APPS.length+" apps installed  ·  "+
            officialCount+" official  ·  "+communityCount+" community  ·  "+
            (checking?"Checking releases…":updates+" updates"));
        if(gridToggle!=null) {
            gridToggle.setTextColor(tableView?muted:Color.WHITE);
            gridToggle.setBackground(shape(tableView?Color.TRANSPARENT:buttonFill,border,0));
            tableToggle.setTextColor(tableView?Color.parseColor(dark?"#0B0B0C":"#F2F1EE"):muted);
            tableToggle.setBackground(shape(tableView?buttonFill:Color.TRANSPARENT,border,0));
        }
        addSectionHeader("OFFICIAL ARTCRAFT APPS",official.size(),countInstalled(official),officialExpanded,
            ()->{officialExpanded=!officialExpanded;updateCards();});
        if(officialExpanded) { if(tableView)addAppTable(official); else addAppGrid(official,columns); }
        addSectionHeader("COMMUNITY APPS",community.size(),countInstalled(community),communityExpanded,
            ()->{communityExpanded=!communityExpanded;updateCards();});
        if(communityExpanded) { if(tableView)addAppTable(community); else addAppGrid(community,columns); }
        if(official.isEmpty() && community.isEmpty())
            list.addView(text("No apps match this search or filter.",13,muted,false));
        if(scroller!=null)scroller.post(()->scroller.scrollTo(0,position));
    }

    private int countInstalled(java.util.List<CatalogClient.App> apps) {
        int count=0;
        for(CatalogClient.App app:apps)if(installed(app.packageName)!=null)count++;
        return count;
    }

    private void addAppGrid(java.util.List<CatalogClient.App> group,int columns) {
        for(int i=0;i<group.size();i+=columns) {
            LinearLayout row=horizontal(); row.setGravity(Gravity.TOP);
            list.addView(row,new LinearLayout.LayoutParams(-1,-2));
            for(int j=0;j<columns;j++) {
                int idx=i+j;
                if(idx>=group.size()) {
                    View blank=new View(this);
                    row.addView(blank,new LinearLayout.LayoutParams(0,dp(1),1f)); continue;
                }
                LinearLayout.LayoutParams cardLp=new LinearLayout.LayoutParams(0,-2,1f);
                cardLp.setMargins(dp(4),dp(4),dp(4),dp(8));
                row.addView(appCard(group.get(idx)),cardLp);
            }
        }
    }

    private void addAppTable(java.util.List<CatalogClient.App> group) {
        for(CatalogClient.App app:group) {
            PackageInfo pkg=installed(app.packageName);
            CatalogClient.Release remote=available.get(app.key);
            LinearLayout row=horizontal(); row.setPadding(dp(10),dp(9),dp(8),dp(9));
            row.setBackground(shape(surface,border,0));
            LinearLayout.LayoutParams rowLp=new LinearLayout.LayoutParams(-1,-2);
            rowLp.setMargins(dp(2),dp(3),dp(2),dp(3)); list.addView(row,rowLp);
            row.addView(appIcon(app),new LinearLayout.LayoutParams(dp(38),dp(38)));
            LinearLayout labels=vertical(); labels.setPadding(dp(10),0,dp(6),0);
            row.addView(labels,new LinearLayout.LayoutParams(0,-2,1f));
            labels.addView(text(app.name,14,foreground,true));
            String status=pkg==null?"Not installed":"Installed · v"+safe(pkg.versionName);
            if(remote!=null)status+=" · latest v"+remote.version;
            labels.addView(text(status,10,muted,false));
            boolean update=pkg!=null && remote!=null &&
                ReleaseRules.compareVersions(remote.version,pkg.versionName)>0;
            String label=update?"Update":(pkg!=null?"Open":(app.community && remote==null?"Explore":"Download"));
            Runnable click=update || (pkg==null && remote!=null)?()->confirmDownload(app,remote):
                pkg!=null?()->openApp(app):app.community?()->openCommunityRepo(app):()->lookupAppRelease(app,true);
            row.addView(action(label,true,accent,click),new LinearLayout.LayoutParams(-2,dp(36)));
        }
    }

    private void addSectionHeader(String heading,int total,int installed,boolean expanded,Runnable toggle) {
        LinearLayout header=horizontal();
        header.setPadding(dp(16),dp(12),dp(16),dp(12));
        header.setBackground(shape(Color.TRANSPARENT,border,0));
        LinearLayout labels=vertical();
        header.addView(labels,new LinearLayout.LayoutParams(0,-2,1f));
        labels.addView(text(heading,13,foreground,true));
        labels.addView(text(installed+" of "+total+" installed",11,muted,false));
        TextView arrow=text(expanded?"−":"+",20,muted,false);
        arrow.setGravity(Gravity.CENTER);
        header.addView(arrow,new LinearLayout.LayoutParams(dp(32),dp(38)));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);
        lp.setMargins(dp(3),dp(12),dp(3),dp(5));
        list.addView(header,lp);
        header.setOnClickListener(v->toggle.run());
    }

    private void addAppGrid(boolean community,int columns) {
        java.util.ArrayList<CatalogClient.App> group=new java.util.ArrayList<>();
        for(CatalogClient.App app:CatalogClient.APPS)if(app.community==community)group.add(app);
        for(int i=0;i<group.size();i+=columns) {
            LinearLayout row=horizontal();
            row.setGravity(Gravity.TOP);
            list.addView(row,new LinearLayout.LayoutParams(-1,-2));
            for(int j=0;j<columns;j++) {
                int idx=i+j;
                if(idx>=group.size()) {
                    View blank=new View(this);
                    row.addView(blank,new LinearLayout.LayoutParams(0,dp(1),1f));
                    continue;
                }
                LinearLayout.LayoutParams cardLp=new LinearLayout.LayoutParams(0,-2,1f);
                cardLp.setMargins(dp(4),dp(4),dp(4),dp(8));
                row.addView(appCard(group.get(idx)),cardLp);
            }
        }
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
        card.setPadding(dp(20),dp(18),dp(20),dp(18));
        card.setBackground(shape(surface,border,0));
        card.setElevation(0f);
        LinearLayout row=horizontal();card.addView(row);
        View icon=appIcon(app);
        row.addView(icon,new LinearLayout.LayoutParams(dp(46),dp(46)));
        LinearLayout title=vertical();title.setPadding(dp(10),0,0,0);
        row.addView(title,new LinearLayout.LayoutParams(0,-2,1f));
        title.addView(text(app.name,16,foreground,true));
        title.addView(text(installed!=null?"Installed":"Not installed",11,muted,false));
        String note;
        if(remote==null) {
            if(app.community)note="Community project  ·  "+app.repo;
            else note=catalogLoaded?"No verified APK in selected channel":
                installed==null?"Tap Download to check latest APK":"Tap Info to check releases";
        } else note=(remote.preview?"Preview ":"Release ")+"v"+remote.version;
        TextView detail=text(note,12,muted,false);
        detail.setMaxLines(2);
        detail.setPadding(0,dp(11),0,dp(9));
        card.addView(detail);
        if(installed!=null) {
            TextView current=text("On device: v"+safe(installed.versionName),12,muted,false);
            current.setMaxLines(1);current.setEllipsize(android.text.TextUtils.TruncateAt.END);
            card.addView(current);
        }
        boolean needsUpdate=installed!=null && remote!=null &&
            ReleaseRules.compareVersions(remote.version,installed.versionName)>0;
        LinearLayout buttons=horizontal();
        buttons.setPadding(0,dp(12),0,0);
        card.addView(buttons);
        String label=needsUpdate?"Update":(installed!=null?"Open":
            (app.community && remote==null?"Explore":"Download"));
        Runnable onPrimary;
        if(needsUpdate || (installed==null && remote!=null))
            onPrimary=()->confirmDownload(app,remote);
        else if(installed!=null)onPrimary=()->openApp(app);
        else if(app.community)onPrimary=()->openCommunityRepo(app);
        else onPrimary=()->lookupAppRelease(app,true);
        TextView primary=action(label,true,accent,onPrimary);
        buttons.addView(primary,new LinearLayout.LayoutParams(0,dp(40),1f));
        String secondaryLabel=app.community?"Repository":(installed!=null?"Info":"Details");
        Runnable secondaryAction=app.community?()->openCommunityRepo(app):
            ()->{ if(remote==null) lookupAppRelease(app,false); else openUrl(remote.notesUrl); };
        TextView secondary=action(secondaryLabel,false,accent,secondaryAction);
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
    /** Open the community project's canonical source repository. */
    private void openCommunityRepo(CatalogClient.App app) {
        if(app.repo==null || !app.repo.matches("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")) {
            notice("Community project link is unavailable");
            return;
        }
        startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://github.com/"+app.repo)));
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

    /** App-specific website section, never the unrelated repository-wide releases page. */
    private void openAppDownloads(CatalogClient.App app) {
        Uri uri=Uri.parse("https://kosmossg.github.io/artcraft-android/#"+app.key);
        startActivity(new Intent(Intent.ACTION_VIEW,uri));
    }

    /**
     * When an app is missing, load its published release on demand.
     * The default startup setting is manual, so a missing cached catalog
     * must not disable Download or route to the unrelated all-app page.
     */
    private void lookupAppRelease(CatalogClient.App app,boolean download) {
        if(!activeAppLookups.add(app.key)) {
            notice("Already checking "+app.name+" releases…");return;
        }
        notice("Finding official "+app.name+" APK…");
        final boolean includePreviews=settings.getBoolean("preview",true);
        worker.execute(()->{
            try {
                Map<String,CatalogClient.Release> found=CatalogClient.fetch(includePreviews);
                ui.post(()->{
                    activeAppLookups.remove(app.key);
                    available.clear();available.putAll(found);
                    catalogLoaded=true;
                    updateCards();
                    CatalogClient.Release release=found.get(app.key);
                    if(release!=null) {
                        if(download)confirmDownload(app,release);
                        else openUrl(release.notesUrl);
                    } else showAppDownloadFallback(app,false);
                });
            } catch(Exception e) {
                ui.post(()->{
                    activeAppLookups.remove(app.key);
                    notice(app.name+" release lookup unavailable: "+e.getMessage());
                    showAppDownloadFallback(app,true);
                });
            }
        });
    }

    private void showAppDownloadFallback(CatalogClient.App app,boolean offline) {
        String message=offline
            ?"The release check could not finish. Open the "+app.name+
              " section on the ArtCraft downloads website instead?"
            :"No APK passed the release filename and SHA-256 checks for "+
              app.name+" on the selected channel. You can still browse "+
              app.name+"'s published downloads.";
        new AlertDialog.Builder(this).setTitle(app.name+" downloads")
            .setMessage(message).setNegativeButton("Cancel",null)
            .setPositiveButton("Browse "+app.name,(d,w)->openAppDownloads(app)).show();
    }

    /**
     * Native overflow rendered on its own solid-black surface.
     * PopupMenu inherits a platform-specific theme, so it could not reliably
     * honor the requested black menu on HONOR/MagicOS.
     */
    private void openMenu(View anchor) {
        LinearLayout content=vertical();
        content.setPadding(dp(7),dp(7),dp(7),dp(7));
        content.setBackground(shape(bg,border,0));

        ScrollView scroll=new ScrollView(this);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.setFillViewport(true);
        scroll.addView(content);

        int maxWidth=(int)(getResources().getDisplayMetrics().widthPixels/dp(1));
        int menuWidth=Math.min(308,Math.max(210,maxWidth-32));
        int menuHeight=Math.min(dp(500),
            getResources().getDisplayMetrics().heightPixels-dp(120));
        PopupWindow popup=new PopupWindow(scroll,dp(menuWidth),menuHeight,true);
        popup.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        popup.setOutsideTouchable(true);
        popup.setElevation(dp(16));

        menuGroup(content,"UPDATES");
        menuItem(content,popup,"Check App Updates",true,this::refreshCatalog);
        menuItem(content,popup,"Check Launcher Update",true,()->checkLauncherUpdate(false));
        menuItem(content,popup,"Downloads",false,()->{
            updateDownloadProgress();
            if(downloadPanel.getVisibility()==View.GONE)
                notice("No active downloads. Select Install or Update on an app card.");
        });
        menuDivider(content);

        menuGroup(content,"PREFERENCES");
        menuItem(content,popup,"Suite startup checks: "+
            (settings.getBoolean("startup_check",false)?"ON":"OFF"),false,()->{
            boolean next=!settings.getBoolean("startup_check",false);
            settings.edit().putBoolean("startup_check",next).apply();
            notice("Suite startup update checks "+(next?"enabled":"disabled"));
        });
        menuItem(content,popup,"Launcher startup checks: "+
            (settings.getBoolean("launcher_startup_check",false)?"ON":"OFF"),false,()->{
            boolean next=!settings.getBoolean("launcher_startup_check",false);
            settings.edit().putBoolean("launcher_startup_check",next).apply();
            notice("Launcher startup update checks "+(next?"enabled":"disabled"));
        });
        menuItem(content,popup,"Channel: "+
            (settings.getBoolean("preview",true)?"Stable + Preview":"Stable only"),
            false,()->{
            settings.edit().putBoolean("preview",!settings.getBoolean("preview",true)).apply();
            refreshCatalog();
        });
        menuItem(content,popup,"Theme: "+(dark?"Dark":"Light"),false,()->{
            settings.edit().putBoolean("dark_theme",!dark).apply();recreate();
        });
        menuDivider(content);

        menuGroup(content,"MORE");
        menuItem(content,popup,"GitHub Releases",false,this::openReleases);
        menuItem(content,popup,"About ArtCraft Launcher",false,()->{
            new AlertDialog.Builder(this)
                .setTitle("ArtCraft Android Launcher")
                .setMessage("v0.1.0-android.10  •  ARM64 TEST ONLY\\n\\n"+
                    "Standalone hub for 13 ArtCraft apps. APK installs require your approval. "+
                    "Published launcher updates must use a compatible signing certificate.")
                .setPositiveButton("OK",null).show();
        });
        popup.showAsDropDown(anchor,0,dp(5),Gravity.RIGHT);
    }

    private void menuGroup(LinearLayout content,String label) {
        TextView heading=text(label,10,muted,true);
        heading.setPadding(dp(15),dp(9),dp(12),dp(4));
        content.addView(heading,new LinearLayout.LayoutParams(-1,dp(33)));
    }

    private void menuDivider(LinearLayout content) {
        View line=new View(this);
        line.setBackgroundColor(border);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(1));
        lp.setMargins(dp(11),dp(7),dp(11),dp(7));
        content.addView(line,lp);
    }

    private void menuItem(LinearLayout content,PopupWindow popup,String title,
                          boolean highlighted,Runnable onSelect) {
        TextView item=text(title,14,foreground,false);
        item.setMinHeight(dp(46));
        item.setPadding(dp(15),dp(10),dp(10),dp(10));
        item.setGravity(Gravity.CENTER_VERTICAL);
        item.setBackground(shape(highlighted? (dark?Color.argb(20,242,241,238):Color.argb(18,16,16,20)):
            Color.TRANSPARENT,Color.TRANSPARENT,0));
        item.setOnClickListener(view->{popup.dismiss();onSelect.run();});
        item.setOnTouchListener((view,event)->{
            if(event.getAction()==android.view.MotionEvent.ACTION_DOWN)
                view.setBackground(shape(dark?Color.argb(28,242,241,238):Color.argb(24,16,16,20),Color.TRANSPARENT,0));
            else if(event.getAction()==android.view.MotionEvent.ACTION_UP || event.getAction()==android.view.MotionEvent.ACTION_CANCEL)
                view.setBackground(shape(highlighted?(dark?Color.argb(20,242,241,238):Color.argb(18,16,16,20)):Color.TRANSPARENT,Color.TRANSPARENT,0));
            return false;
        });
        content.addView(item,new LinearLayout.LayoutParams(-1,-2));
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
                    checking=false;catalogLoaded=true;
                    available.clear();available.putAll(result);
                    updateCards();notice("Found matching releases for "+result.size()+" apps");
                });
            } catch(Exception e) {
                ui.post(()->{checking=false;updateCards();notice("Update check unavailable: "+e.getMessage());});
            }
        });
    }

    private void checkLauncherUpdate(boolean startup) {
        // The side-by-side TEST package cannot receive production launcher updates.
        if(getPackageName().endsWith(".test")) {
            if(!startup)notice("Launcher self-update is disabled in the parallel TEST app");
            return;
        }
        if(checkingLauncher)return;
        checkingLauncher=true;
        if(!startup)notice("Checking published launcher updates…");
        final boolean preview=settings.getBoolean("preview",true);
        worker.execute(()->{
            try {
                CatalogClient.Release latest=CatalogClient.fetchLauncher(preview);
                ui.post(()->{
                    checkingLauncher=false;
                    PackageInfo installed=installed(getPackageName());
                    String current=installed==null?null:installed.versionName;
                    if(latest==null) {
                        if(!startup)notice("No eligible signed launcher release found on GitHub.");
                    } else if(current==null ||
                        ReleaseRules.compareVersions(latest.version,current)<=0) {
                        if(!startup)notice("ArtCraft Launcher is up to date.");
                    } else {
                        showLauncherUpdate(latest,current);
                    }
                });
            } catch(Exception e) {
                ui.post(()->{
                    checkingLauncher=false;
                    if(!startup)notice("Launcher update check unavailable: "+e.getMessage());
                });
            }
        });
    }

    private void showLauncherUpdate(CatalogClient.Release release,String installedVersion) {
        String summary="Installed: v"+installedVersion+
            "\\nAvailable: v"+release.version+
            (release.preview?" (Preview)":" (Stable)")+
            "\\n\\nDownload only from official KosmosSG GitHub Releases. The update must have the same signing certificate and an increasing Android versionCode. Disposable test APKs cannot update each other unless signing identities match.";
        new AlertDialog.Builder(this).setTitle("ArtCraft Launcher Update")
            .setMessage(summary).setNegativeButton("Not now",null)
            .setNeutralButton("Release details",(d,w)->openUrl(release.notesUrl))
            .setPositiveButton("Download",(d,w)->startLauncherDownload(release)).show();
    }

    private void startLauncherDownload(CatalogClient.Release release) {
        if(settings.getLong("download_id",-1L)>0) {
            notice("Finish the current app download first.");return;
        }
        notice("Verifying launcher release checksum…");
        worker.execute(()->{
            try {
                String hash=CatalogClient.expectedSha256(release);
                ui.post(()->enqueueDownload("ArtCraft Launcher",getPackageName(),
                    "launcher",release,hash));
            } catch(Exception e) {
                ui.post(()->notice("Launcher release rejected: "+e.getMessage()));
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
        enqueueDownload(app.name,app.packageName,app.key,release,sha);
    }

    private void enqueueDownload(String appName,String packageName,String appKey,
                                 CatalogClient.Release release,String sha) {
        if(settings.getLong("download_id",-1)>0) {notice("Another download is in progress");return;}
        try {
            if(!release.apkUrl.startsWith(CatalogClient.DOWNLOAD_PREFIX+release.tag+"/"))
                throw new IllegalStateException("Unexpected GitHub asset URL");
            File directory=getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            if(directory==null) throw new IllegalStateException("Storage unavailable");
            String filename="ArtCraft-"+appKey+"-"+release.version+".apk";
            File local=new File(directory,filename);
            if(local.exists() && !local.delete()) throw new IllegalStateException("Old APK could not be replaced");
            DownloadManager.Request request=new DownloadManager.Request(Uri.parse(release.apkUrl));
            request.setTitle(appName+" v"+release.version);
            request.setDescription("ArtCraft Launcher – verified GitHub release");
            request.setAllowedOverMetered(true);
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalFilesDir(this,Environment.DIRECTORY_DOWNLOADS,filename);
            long id=downloads.enqueue(request);
            settings.edit().putLong("download_id",id).putString("download_file",filename)
                .putString("download_sha",sha).putString("download_package",packageName)
                .putString("download_version",release.version).apply();
            notice("Downloading "+appName+" inside ArtCraft Launcher…");
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
            Uri uri=new Uri.Builder().scheme("content").authority(getPackageName()+".apks")
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
