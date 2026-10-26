package com.artcraft.photocraft;

import android.app.NativeActivity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.provider.DocumentsContract;
import android.text.InputType;
import android.util.Log;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.InputConnectionWrapper;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** NativeActivity subclass that supplies Android SAF open/save results to the Rust UI shell. */
public final class PhotoCraftActivity extends NativeActivity {
    private static final String TAG = "PhotoCraftSAF";
    private static final int REQ_OPEN = 0x5043;
    private static final int REQ_SAVE = 0x5044;
    private static final int REQ_FONT_FOLDER = 0x5045;
    private static final String FONT_FOLDER_PREF = "shared_font_tree_uri";
    private static final String PREFS = "photocraft_saf_uri_map";
    private final ConcurrentLinkedQueue<String> results = new ConcurrentLinkedQueue<>();
    private final Map<Integer, Long> requestIds = new HashMap<>();
    private final Map<Long, String> suggestedNames = new HashMap<>();
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    // Separate queue/executor: update checks must not block SAF or shared-font scanning.
    private final ConcurrentLinkedQueue<String> updateResults = new ConcurrentLinkedQueue<>();
    private final ExecutorService updateIo = Executors.newSingleThreadExecutor();
    private static final String RELEASES_API =
            "https://api.github.com/repos/KosmosSG/artcraft-android/releases?per_page=100";
    private static final String RELEASES_PAGE =
            "https://github.com/KosmosSG/artcraft-android/releases";

    // Soft-keyboard host. A bare NativeActivity has no editable view, so the system IME opens
    // unreliably and delivers no text. This tiny, invisible but focusable EditText has a real
    // InputConnection, so the keyboard shows/dismisses on request and every commit/composition
    // arrives here where imePoll() hands it to the Rust shell as egui IME events.
    private final ConcurrentLinkedQueue<String> imeEvents = new ConcurrentLinkedQueue<>();
    private EditText imeView;
    // True between imeShow() and imeHide(); suppresses a deferred show that a quick hide overtook.
    private volatile boolean imeWanted = false;
    private volatile boolean pcDiscardPrompt = false;

    // A button-only modal owns hardware keys, even while an inline Type edit
    // remains parked underneath. Do not finish that edit on Cancel.
    public void pcSetDiscardPrompt(boolean active) {
        pcDiscardPrompt = active;
        if (active) imeHide();
    }
    private boolean pcEscapeCaptured = false;
    private volatile int pcEscapeSeen = 0;
    private volatile int pcEscapeQueued = 0;
    private volatile int pcEscapePolled = 0;
    private volatile int pcTypeEnded = 0;
    private volatile int pcLastKey = -1;
    private volatile int pcLastScan = -1;
    private volatile int pcBackCalls = 0;

    @Override
    public void onBackPressed() {
        pcBackCalls++;
        super.onBackPressed();
    }

    public String pcKeyboardStatus() {
        return "Java Esc seen=" + pcEscapeSeen + " queued=" + pcEscapeQueued
                + " polled=" + pcEscapePolled + " ended=" + pcTypeEnded
                + " imeWanted=" + imeWanted
                + " lastCode=" + pcLastKey + " scan=" + pcLastScan + " backCalls=" + pcBackCalls;
    }

    // Documents the system asked this app to open (an ACTION_VIEW/ACTION_SEND it is registered for):
    // the private path of each staged copy, drained one per call by the Rust shell through
    // intentPoll() and opened exactly like a file chosen in the picker.
    private final ConcurrentLinkedQueue<String> intentPaths = new ConcurrentLinkedQueue<>();

    public String pcFilesDir() { return appStorageDir().getAbsolutePath(); }

    /**
     * The app's private storage root: the app-specific external directory
     * {@code /storage/emulated/0/Android/data/<pkg>/files} whenever the device has it, so the
     * preferences, exports and the working copies of SAF documents stay reachable over USB/MTP, and
     * the internal directory otherwise.
     */
    private File appStorageDir() {
        File external = getExternalFilesDir(null);
        return external != null ? external : getFilesDir();
    }

    private void applyImmersiveFullscreen() {
        Window window = getWindow();
        if (window == null) {
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController controller = window.getInsetsController();
            if (controller != null) {
                controller.hide(WindowInsets.Type.systemBars());
                controller.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            window.getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_FULLSCREEN);
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        applyImmersiveFullscreen();
        Window window = getWindow();
        if (window != null) {
            window.getDecorView().post(this::applyImmersiveFullscreen);
        }
        imeSetup();
        handleIncomingFiles(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        // singleTask launch mode: opening a registered file type while the app runs lands here
        // instead of onCreate, so stage it for the shell the same way.
        setIntent(intent);
        applyImmersiveFullscreen();
        handleIncomingFiles(intent);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            applyImmersiveFullscreen();
        }
    }

    /**
     * Install the invisible, focusable {@link EditText} that makes Android's soft keyboard usable.
     * Called from {@link #onCreate}; failures are logged and leave the app on the old (unreliable)
     * decor-view path, so a device that rejects the extra view still runs.
     */
    private void imeSetup() {
        try {
            // The IME height must not resize or pan the fullscreen native surface; the keyboard
            // simply overlays it. STATE_UNCHANGED keeps the initial hidden state under our control.
            Window window = getWindow();
            if (window != null) {
                window.setSoftInputMode(
                        WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING
                                | WindowManager.LayoutParams.SOFT_INPUT_STATE_UNCHANGED);
            }
            imeView = new EditText(this) {
                @Override
                public InputConnection onCreateInputConnection(EditorInfo outAttrs) {
                    InputConnection base = super.onCreateInputConnection(outAttrs);
                    if (base == null) {
                        return null;
                    }
                    return new InputConnectionWrapper(base, true) {
                        @Override
                        public boolean commitText(CharSequence text, int newCursorPosition) {
                            if (text != null && text.length() > 0) {
                                imeEvents.offer("c" + text);
                            }
                            return super.commitText(text, newCursorPosition);
                        }

                        @Override
                        public boolean setComposingText(CharSequence text, int newCursorPosition) {
                            imeEvents.offer("p" + (text == null ? "" : text.toString()));
                            return super.setComposingText(text, newCursorPosition);
                        }

                        @Override
                        public boolean finishComposingText() {
                            imeEvents.offer("f");
                            return super.finishComposingText();
                        }

                        @Override
                        public boolean deleteSurroundingText(int beforeLength, int afterLength) {
                            if (beforeLength > 0 || afterLength > 0) {
                                imeEvents.offer("d" + beforeLength + "," + afterLength);
                            }
                            return super.deleteSurroundingText(beforeLength, afterLength);
                        }

                        @Override
                        public boolean performEditorAction(int actionCode) {
                            imeEvents.offer("a" + actionCode);
                            return super.performEditorAction(actionCode);
                        }

                        @Override
                        public boolean sendKeyEvent(KeyEvent event) {
                            if (relayTypeEscape(event)) return true;
                            if (event.getAction() == KeyEvent.ACTION_DOWN) {
                                int code = event.getKeyCode();
                                if (code == KeyEvent.KEYCODE_DEL) {
                                    imeEvents.offer("d1,0");
                                } else if (code == KeyEvent.KEYCODE_FORWARD_DEL) {
                                    imeEvents.offer("d0,1");
                                } else if (code == KeyEvent.KEYCODE_ENTER) {
                                    imeEvents.offer("a6");
                                }
                            }
                            return super.sendKeyEvent(event);
                        }
                    };
                }

                @Override
                public boolean onKeyPreIme(int keyCode, KeyEvent event) {
                    // Physical Esc can otherwise be eaten by the active IME.
                    return relayTypeEscape(event) || super.onKeyPreIme(keyCode, event);
                }

                @Override
                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    if (relayTypeEscape(event)) return true;
                    // Let hardware key events fall through to the native input queue (winit), exactly
                    // as they did before this view existed; the soft keyboard talks to us through the
                    // InputConnection instead. This keeps physical keyboards working.
                    return false;
                }

                @Override
                public boolean onKeyUp(int keyCode, KeyEvent event) {
                    return relayTypeEscape(event);
                }

                @Override
                public boolean onTouchEvent(android.view.MotionEvent event) {
                    // Purely a keyboard target: never intercept touch, which belongs to the native
                    // surface underneath.
                    return false;
                }
            };
            imeView.setBackground(null);
            imeView.setCursorVisible(false);
            imeView.setTextColor(0);
            imeView.setAlpha(0.01f);
            imeView.setSoundEffectsEnabled(false);
            imeView.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
            imeView.setImeOptions(EditorInfo.IME_FLAG_NO_FULLSCREEN);
            imeView.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
            FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(1, 1);
            params.gravity = Gravity.TOP | Gravity.START;
            addContentView(imeView, params);
        } catch (Throwable error) {
            Log.w(TAG, "Could not install the soft-keyboard host view", error);
        }
    }

    /** Show the soft keyboard by focusing the IME host view. Called by the Rust shell via JNI. */
    public void imeShow() {
        if (pcDiscardPrompt) return;
        final EditText view = imeView;
        if (view == null) {
            return;
        }
        imeWanted = true;
        runOnUiThread(() -> {
            if (!imeWanted || pcDiscardPrompt) {
                return;
            }
            try {
                view.setFocusable(true);
                view.setFocusableInTouchMode(true);
                view.requestFocus();
                InputMethodManager imm =
                        (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
                if (imm != null && imm.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT)) {
                    return;
                }
                // Some devices ignore the request until focus and layout have settled; retry once on
                // the next message-loop turn (guarded so a following hide wins).
                view.post(() -> {
                    if (!imeWanted || pcDiscardPrompt) {
                        return;
                    }
                    try {
                        InputMethodManager retry =
                                (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
                        if (retry != null) {
                            retry.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT);
                        }
                    } catch (Throwable error) {
                        Log.w(TAG, "Could not show the soft keyboard", error);
                    }
                });
            } catch (Throwable error) {
                Log.w(TAG, "Could not show the soft keyboard", error);
            }
        });
    }

    /** Deliver a complete Escape pair once, before the IME can swallow it.
     * Do not hide/reset the IME here: only the native editor knows whether
     * Escape ended Type editing or was owned by a field/modal/composition.
     */
    private boolean relayTypeEscape(KeyEvent event) {
        if (event != null && event.getAction() == KeyEvent.ACTION_DOWN) {
            pcLastKey = event.getKeyCode();
            pcLastScan = event.getScanCode();
        }
        if (event == null || event.getKeyCode() != KeyEvent.KEYCODE_ESCAPE) return false;
        if (event.getAction() == KeyEvent.ACTION_DOWN) pcEscapeSeen++;
        if (pcEscapeCaptured) {
            if (event.getAction() == KeyEvent.ACTION_UP) {
                imeEvents.offer("E");
                pcEscapeCaptured = false;
            }
            return true;
        }
        if (event.getAction() == KeyEvent.ACTION_DOWN && imeWanted
                && event.getRepeatCount() == 0 && event.hasNoModifiers()) {
            pcEscapeCaptured = true;
            pcEscapeQueued++;
            imeEvents.offer("e");
            return true;
        }
        return false;
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (relayTypeEscape(event)) return true;
        return super.dispatchKeyEvent(event);
    }

    /** Called only after PhotoCraft has actually finished inline Type editing. */
    public void pcEndTypeEditing() {
        pcTypeEnded++;
        runOnUiThread(() -> {
            imeHide();
            // Reset can emit a final composition callback: discard it after the
            // editor ended, never during ordinary Chinese/IME text entry.
            imeEvents.clear();
        });
    }

    /** Hide the soft keyboard and release the IME host view. Called by the Rust shell via JNI. */
    public void imeHide() {
        imeWanted = false;
        final EditText view = imeView;
        if (view == null) {
            return;
        }
        runOnUiThread(() -> {
            try {
                InputMethodManager imm =
                        (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
                if (imm != null) {
                    imm.hideSoftInputFromWindow(view.getWindowToken(), 0);
                }
                view.clearFocus();
                // Restore focus to NativeActivity's visible surface; a hidden
                // EditText must not intercept the next V/T/P tool shortcut.
                final Window activeWindow = getWindow();
                final View content = activeWindow == null ? null
                        : activeWindow.getDecorView().findViewById(android.R.id.content);
                if (content instanceof android.view.ViewGroup) {
                    android.view.ViewGroup group = (android.view.ViewGroup) content;
                    for (int i = 0; i < group.getChildCount(); i++) {
                        View child = group.getChildAt(i);
                        if (child != view && child.isShown()) {
                            child.setFocusable(true);
                            child.setFocusableInTouchMode(true);
                            if (child.requestFocus()) break;
                        }
                    }
                }
                // Drop the scratch buffer between sessions so it cannot grow without bound.
                if (!pcDiscardPrompt) view.setText("");
            } catch (Throwable error) {
                Log.w(TAG, "Could not hide the soft keyboard", error);
            }
        });
    }

    /**
     * Hand the Rust shell at most one queued keyboard event per call. The first character tags the
     * event ("c" commit, "p" pre-edit, "f" finish, "d" delete-with-counts, "a" editor action) and
     * the remainder is the payload; returns {@code null} when the queue is empty.
     */
    public String imePoll() {
        String event = imeEvents.poll();
        if ("e".equals(event)) pcEscapePolled++;
        return event;
    }

    /**
     * Hand the Rust shell the private path of one file the system asked us to open (or that another
     * app shared with us), or {@code null} when nothing is queued. Each staged copy is delivered
     * once and then opened exactly like a file chosen in the open picker.
     */
    public String intentPoll() {
        return intentPaths.poll();
    }

    // Keep the existing versionCode-based updater. Native Android handles preferences only.
    public boolean pcStartupUpdatesEnabled() {
        return getSharedPreferences(PREFS, MODE_PRIVATE)
                .getBoolean("check_updates_at_startup", true);
    }
    private android.app.AlertDialog pcUpdatesDialog;
    private android.widget.TextView pcUpdateStatus;
    private android.widget.Button pcUpdateCheckButton, pcUpdateReleaseButton;
    private String pcUpdateReleaseUrl;
    private volatile boolean pcChecking;

    /** Same information architecture as LightCraft's About > Updates tab. */
    public void pcUpdateSettings() {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            if (pcUpdatesDialog != null && pcUpdatesDialog.isShowing()) return;
            final int spacing = Math.round(16 * getResources().getDisplayMetrics().density);
            android.widget.LinearLayout content = new android.widget.LinearLayout(this);
            content.setOrientation(android.widget.LinearLayout.VERTICAL);
            content.setPadding(spacing, spacing, spacing, spacing);
            android.widget.TextView section = new android.widget.TextView(this);
            section.setText("PhotoCraft Updates");
            section.setTextSize(18);
            section.setTypeface(null, android.graphics.Typeface.BOLD);
            content.addView(section);
            android.widget.TextView installed = new android.widget.TextView(this);
            try {
                installed.setText("Installed Version: " + getPackageManager()
                        .getPackageInfo(getPackageName(), 0).versionName);
            } catch (Exception error) { installed.setText("Installed Version: unavailable"); }
            installed.setPadding(0, spacing / 2, 0, spacing / 2);
            content.addView(installed);
            pcUpdateStatus = new android.widget.TextView(this);
            pcUpdateStatus.setText(pcChecking ? "Checking for updates…" :
                    "Tap Check for Updates to check published PhotoCraft releases.");
            content.addView(pcUpdateStatus);
            pcUpdateCheckButton = new android.widget.Button(this);
            pcUpdateCheckButton.setText("Check for Updates");
            pcUpdateCheckButton.setEnabled(!pcChecking);
            pcUpdateCheckButton.setOnClickListener(view -> pcCheckForUpdates());
            content.addView(pcUpdateCheckButton);
            android.widget.TextView channelTitle = new android.widget.TextView(this);
            channelTitle.setText("Update Channel");
            channelTitle.setPadding(0, spacing, 0, 0);
            content.addView(channelTitle);
            android.widget.RadioGroup channels = new android.widget.RadioGroup(this);
            android.widget.RadioButton stable = new android.widget.RadioButton(this);
            stable.setId(android.view.View.generateViewId());
            stable.setText("Stable Releases Only");
            channels.addView(stable);
            android.widget.RadioButton preview = new android.widget.RadioButton(this);
            preview.setId(android.view.View.generateViewId());
            preview.setText("Stable + Preview Releases");
            channels.addView(preview);
            channels.check(getSharedPreferences(PREFS, MODE_PRIVATE)
                    .getBoolean("include_preview_releases", false) ? preview.getId() : stable.getId());
            channels.setOnCheckedChangeListener((group, id) ->
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                            .putBoolean("include_preview_releases", id == preview.getId()).apply());
            content.addView(channels);
            android.widget.TextView caution = new android.widget.TextView(this);
            caution.setText("Preview releases may be untested; installing remains your choice.");
            caution.setTextSize(12);
            content.addView(caution);
            android.widget.CheckBox atStartup = new android.widget.CheckBox(this);
            atStartup.setText("Check for updates at startup");
            atStartup.setChecked(pcStartupUpdatesEnabled());
            atStartup.setOnCheckedChangeListener((button, checked) ->
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                            .putBoolean("check_updates_at_startup", checked).apply());
            atStartup.setPadding(0, spacing / 2, 0, 0);
            content.addView(atStartup);
            pcUpdateReleaseButton = new android.widget.Button(this);
            pcUpdateReleaseButton.setText("Open Official GitHub Release");
            pcUpdateReleaseButton.setVisibility(android.view.View.GONE);
            pcUpdateReleaseButton.setOnClickListener(view -> {
                if (pcUpdateReleaseUrl != null) pcOpenUpdatePage(pcUpdateReleaseUrl);
            });
            content.addView(pcUpdateReleaseButton);
            android.widget.TextView note = new android.widget.TextView(this);
            note.setText("PhotoCraft-only GitHub Releases; Android updates require the original signing key.");
            note.setTextSize(12);
            content.addView(note);
            android.widget.ScrollView scroll = new android.widget.ScrollView(this);
            scroll.addView(content);
            pcUpdatesDialog = new android.app.AlertDialog.Builder(this)
                    .setTitle("About PhotoCraft — Updates")
                    .setView(scroll)
                    .setPositiveButton("Close", (dialog, which) -> { })
                    .create();
            pcUpdatesDialog.setOnDismissListener(dialog -> {
                pcUpdatesDialog = null;
                pcUpdateStatus = null;
                pcUpdateCheckButton = null;
                pcUpdateReleaseButton = null;
                pcUpdateReleaseUrl = null;
            });
            pcUpdatesDialog.show();
        });
    }

    private void pcRenderUpdateResult(JSONObject result) {
        runOnUiThread(() -> {
            pcChecking = false;
            if (pcUpdateCheckButton != null) pcUpdateCheckButton.setEnabled(true);
            if (pcUpdateStatus == null) return; // Silent startup checks stay silent.
            String state = result.optString("state", "error");
            String installed = result.optString("installed_version", "unknown");
            String latest = result.optString("latest_version", "unknown");
            String message = "update_available".equals(state)
                    ? "Update available: " + latest + " (installed: " + installed + ")"
                    : "up_to_date".equals(state)
                    ? "PhotoCraft is up to date (" + installed + ")."
                    : result.optString("message", "Update check failed.");
            pcUpdateStatus.setText(message);
            String url = result.optString("url", "");
            boolean trusted = "update_available".equals(state)
                    && url.matches("https://github\\.com/KosmosSG/artcraft-android/releases/tag/photocraft-v[0-9]+\\.[0-9]+\\.[0-9]+(?:-android\\.[1-9][0-9]*)?");
            pcUpdateReleaseUrl = trusted ? url : null;
            if (pcUpdateReleaseButton != null)
                pcUpdateReleaseButton.setVisibility(trusted ? android.view.View.VISIBLE : android.view.View.GONE);
        });
    }

    /** Report the real PhotoCraft shared text-engine families for font-import diagnosis. */
    public void pcShowFontCatalog(String report) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            new android.app.AlertDialog.Builder(this)
                    .setTitle("PhotoCraft — Detected Fonts")
                    .setMessage(report == null ? "No font information available" : report)
                    .setPositiveButton("Close", (dialog, which) -> { })
                    .show();
        });
    }

    public void pcShowMessage(String message) {
        runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed())
                android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show();
        });
    }

    /** JNI: begin a manual, read-only check of published PhotoCraft GitHub releases. */
    public void pcCheckForUpdates() {
        pcChecking = true;
        runOnUiThread(() -> {
            if (pcUpdateStatus != null) pcUpdateStatus.setText("Checking official GitHub releases…");
            if (pcUpdateCheckButton != null) pcUpdateCheckButton.setEnabled(false);
            if (pcUpdateReleaseButton != null) pcUpdateReleaseButton.setVisibility(android.view.View.GONE);
        });
        updateIo.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(RELEASES_API).openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(8000);
                connection.setRequestProperty("Accept", "application/vnd.github+json");
                connection.setRequestProperty("User-Agent", "PhotoCraft-Android-Updater");
                int httpStatus = connection.getResponseCode();
                if (httpStatus != 200) {
                    throw new java.io.IOException("GitHub returned HTTP " + httpStatus);
                }
                byte[] bytes;
                try (InputStream input = connection.getInputStream();
                     ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                    byte[] chunk = new byte[8192];
                    int n;
                    while ((n = input.read(chunk)) != -1) {
                        if (buffer.size() + n > 1024 * 1024) {
                            throw new java.io.IOException("GitHub response is too large");
                        }
                        buffer.write(chunk, 0, n);
                    }
                    bytes = buffer.toByteArray();
                }
                JSONArray releases = new JSONArray(new String(bytes, StandardCharsets.UTF_8));
                android.content.pm.PackageInfo installed = getPackageManager()
                        .getPackageInfo(getPackageName(), 0);
                String installedVersion = installed.versionName;
                if (installedVersion == null) installedVersion = "unknown";
                long installedCode = installed.getLongVersionCode();

                // GitHub release ordering and upstream semver are NOT Android upgrade ordering.
                // Only offer a public PhotoCraft APK whose release notes declare an Android
                // versionCode greater than the one actually installed. Missing metadata fails
                // closed; do not suggest an APK that Android would reject as a downgrade.
                String latestVersion = null;
                String latestUrl = null;
                long latestCode = -1;
                for (int i = 0; i < releases.length(); i++) {
                    JSONObject release = releases.optJSONObject(i);
                    if (release == null || release.optBoolean("draft")
                            || (!getSharedPreferences(PREFS, MODE_PRIVATE)
                                    .getBoolean("include_preview_releases", false) && release.optBoolean("prerelease"))) continue;
                    String releaseTag = release.optString("tag_name", "");
                    String version = PhotoCraftUpdatePolicy.versionFromTag(releaseTag);
                    if (version == null) continue;
                    long candidateCode = PhotoCraftUpdatePolicy.declaredVersionCode(
                            release.optString("body", ""));
                    if (candidateCode <= 0 || candidateCode <= latestCode) continue;

                    JSONArray assets = release.optJSONArray("assets");
                    boolean hasApk = false;
                    if (assets != null) {
                        for (int a = 0; a < assets.length(); a++) {
                            JSONObject asset = assets.optJSONObject(a);
                            if (asset != null && PhotoCraftUpdatePolicy.isPhotoCraftApkAsset(
                                    releaseTag, asset.optString("name", ""))) {
                                hasApk = true;
                                break;
                            }
                        }
                    }
                    if (!hasApk) continue;
                    String releaseUrl = release.optString("html_url", "");
                    if (!releaseUrl.startsWith(
                            "https://github.com/KosmosSG/artcraft-android/releases/tag/photocraft-v"))
                        continue;
                    latestCode = candidateCode;
                    latestVersion = version;
                    latestUrl = releaseUrl;
                }
                JSONObject result = new JSONObject();
                result.put("status", "ok");
                result.put("installed_version", installedVersion);
                result.put("installed_version_code", installedCode);
                if (installedCode <= 0) {
                    result.put("state", "error");
                    result.put("message", "Cannot determine installed Android versionCode");
                } else if (latestVersion == null) {
                    result.put("state", "no_release");
                    result.put("message",
                            "No published PhotoCraft APK with declared versionCode was found");
                } else {
                    result.put("latest_version", latestVersion);
                    result.put("latest_version_code", latestCode);
                    result.put("url", latestUrl);
                    result.put("state", PhotoCraftUpdatePolicy.isNewer(latestCode, installedCode)
                            && PhotoCraftUpdatePolicy.compareVersions(latestVersion, installedVersion) > 0
                            ? "update_available" : "up_to_date");
                }
                updateResults.offer(result.toString());
                pcRenderUpdateResult(result);
            } catch (Exception error) {
                Log.w(TAG, "PhotoCraft update check failed", error);
                try {
                    JSONObject result = new JSONObject();
                    result.put("status", "error");
                    result.put("message", error.getMessage() == null
                            ? "Could not check GitHub releases" : error.getMessage());
                    updateResults.offer(result.toString());
                pcRenderUpdateResult(result);
                } catch (Exception ignored) { }
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    /** JNI: returns one completed update-check result as JSON, or null while waiting. */
    public String pcPollUpdateResult() { return updateResults.poll(); }

    /** JNI: open only the official PhotoCraft release URL in a browser. */
    public void pcOpenUpdatePage(String url) {
        if (url == null || !url.startsWith(
                "https://github.com/KosmosSG/artcraft-android/releases/")) return;
        runOnUiThread(() -> {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            } catch (Exception error) {
                Log.w(TAG, "Could not open PhotoCraft release page", error);
            }
        });
    }

    private static int compareVersions(String a, String b) {
        String[] aa = a.split("\\.");
        String[] bb = b.split("\\.");
        for (int i = 0; i < 3; i++) {
            int av = i < aa.length ? parseVersionPart(aa[i]) : 0;
            int bv = i < bb.length ? parseVersionPart(bb[i]) : 0;
            if (av != bv) return Integer.compare(av, bv);
        }
        return 0;
    }

    private static int parseVersionPart(String value) {
        try { return Integer.parseInt(value); }
        catch (NumberFormatException ignored) { return 0; }
    }

    public String pcPollPickerResult() { return results.poll(); }

    public void pcRequestOpen(long id, boolean multiple) {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                requestIds.put(REQ_OPEN, id);
                startActivityForResult(intent, REQ_OPEN);
            } catch (Exception e) {
                enqueueError(id, "open", e.toString());
            }
        });
    }

    public void pcRequestSave(long id, String suggestedName) {
        runOnUiThread(() -> {
            try {
                String name = safeName(suggestedName == null ? "Untitled.pcraft" : suggestedName);
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType(mimeFor(name));
                intent.putExtra(Intent.EXTRA_TITLE, name);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                requestIds.put(REQ_SAVE, id);
                suggestedNames.put(id, name);
                startActivityForResult(intent, REQ_SAVE);
            } catch (Exception e) {
                enqueueError(id, "save", e.toString());
            }
        });
    }

    /** Ask Android for read-only access to a user-selected shared font directory. */
    public void pcRequestFontFolder(long id) {
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                requestIds.put(REQ_FONT_FOLDER, id);
                startActivityForResult(intent, REQ_FONT_FOLDER);
            } catch (Exception error) {
                requestIds.remove(REQ_FONT_FOLDER);
                enqueueError(id, "font_folder", error.toString());
            }
        });
    }

    /** Refresh the previously selected folder, without prompting again. */
    public void pcRefreshFontFolder(long id) {
        String stored = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(FONT_FOLDER_PREF, null);
        if (stored == null) {
            enqueueError(id, "font_folder", "Select Shared Font Folder first");
            return;
        }
        scanFontFolder(id, Uri.parse(stored));
    }

    private void scanFontFolder(long id, Uri treeUri) {
        io.execute(() -> {
            try {
                boolean granted = false;
                for (android.content.UriPermission permission :
                        getContentResolver().getPersistedUriPermissions()) {
                    if (treeUri.equals(permission.getUri()) && permission.isReadPermission()) {
                        granted = true;
                        break;
                    }
                }
                if (!granted) throw new SecurityException("Folder access expired; select the folder again");

                File cache = new File(appStorageDir(), "shared-font-cache");
                if (!cache.isDirectory() && !cache.mkdirs())
                    throw new Exception("Could not create shared font cache");

                JSONArray paths = new JSONArray();
                int count = 0;
                int visitedFolders = 0;
                // Breadth-first scan. Bounded to avoid loops, huge providers and slow scans.
                java.util.ArrayDeque<String> pending = new java.util.ArrayDeque<>();
                java.util.HashSet<String> seen = new java.util.HashSet<>();
                pending.add(DocumentsContract.getTreeDocumentId(treeUri));
                while (!pending.isEmpty() && count < 200 && visitedFolders < 1000) {
                    String parentId = pending.removeFirst();
                    if (!seen.add(parentId)) continue;
                    visitedFolders++;
                    Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentId);
                    try (Cursor cursor = getContentResolver().query(children,
                            new String[] {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                                    DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                                    DocumentsContract.Document.COLUMN_MIME_TYPE,
                                    DocumentsContract.Document.COLUMN_SIZE}, null, null, null)) {
                        if (cursor == null) {
                            Log.w(TAG, "Cannot list font subfolder: " + parentId);
                            continue;
                        }
                        while (cursor.moveToNext() && count < 200) {
                            String documentId = cursor.getString(0);
                            String name = cursor.getString(1);
                            String mime = cursor.getString(2);
                            if (documentId == null || name == null) continue;
                            if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                                if (seen.size() + pending.size() < 1000) pending.addLast(documentId);
                                continue;
                            }
                            String lower = name.toLowerCase(java.util.Locale.ROOT);
                            if (!lower.endsWith(".ttf") && !lower.endsWith(".otf")) continue;
                            if (!cursor.isNull(3)) {
                                long size = cursor.getLong(3);
                                if (size <= 0 || size > 32L * 1024 * 1024) continue;
                            }
                            Uri fontUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, documentId);
                            String extension = lower.endsWith(".ttf") ? ".ttf" : ".otf";
                            // Use the full document ID for cache naming, including subfolder path.
                            String hash = java.util.UUID.nameUUIDFromBytes(
                                    documentId.getBytes(java.nio.charset.StandardCharsets.UTF_8))
                                    .toString();
                            File target = new File(cache, "font-" + hash + extension);
                            try (InputStream input = getContentResolver().openInputStream(fontUri);
                                 OutputStream output = new FileOutputStream(target)) {
                                if (input == null) throw new Exception("Cannot read font " + name);
                                byte[] buffer = new byte[64 * 1024];
                                int n;
                                long total = 0;
                                while ((n = input.read(buffer)) != -1) {
                                    total += n;
                                    if (total > 32L * 1024 * 1024)
                                        throw new Exception("Font too large: " + name);
                                    output.write(buffer, 0, n);
                                }
                                if (total == 0) throw new Exception("Empty font: " + name);
                            } catch (Exception fontError) {
                                target.delete();
                                Log.w(TAG, "Skipping shared font " + name, fontError);
                                continue;
                            }
                            paths.put(target.getAbsolutePath());
                            count++;
                        }
                    } catch (SecurityException securityError) {
                        throw securityError;
                    } catch (Exception folderError) {
                        Log.w(TAG, "Skipping unreadable font subfolder: " + parentId, folderError);
                    }
                }
                JSONObject result = base(id, "font_folder", "ok");
                result.put("paths", paths);
                result.put("count", count);
                results.offer(result.toString());
            } catch (Exception error) {
                enqueueError(id, "font_folder", error.toString());
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_OPEN && requestCode != REQ_SAVE && requestCode != REQ_FONT_FOLDER) return;
        Long boxedId = requestIds.remove(requestCode);
        if (boxedId == null) return;
        final long id = boxedId;
        final String kind = requestCode == REQ_OPEN ? "open" : (requestCode == REQ_SAVE ? "save" : "font_folder");
        if (resultCode != RESULT_OK || data == null) {
            suggestedNames.remove(id);
            enqueueCancel(id, kind);
            return;
        }
        if (requestCode == REQ_FONT_FOLDER) {
            Uri treeUri = data.getData();
            if (treeUri == null) { enqueueCancel(id, kind); return; }
            try {
                int readFlag = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
                if (readFlag == 0) throw new SecurityException("Folder read permission not granted");
                getContentResolver().takePersistableUriPermission(treeUri, readFlag);
                getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                        .putString(FONT_FOLDER_PREF, treeUri.toString()).apply();
                scanFontFolder(id, treeUri);
            } catch (Exception error) {
                enqueueError(id, kind, error.toString());
            }
            return;
        }
        if (requestCode == REQ_SAVE) {
            Uri uri = data.getData();
            if (uri == null) { enqueueCancel(id, kind); return; }
            persistPermission(uri, data);
            try {
                String name = displayName(uri);
                if (name == null || name.trim().isEmpty()) name = suggestedNames.getOrDefault(id, "Untitled.pcraft");
                File stage = newStageFile(name, uri);
                rememberUri(stage, uri);
                enqueueSave(id, stage.getAbsolutePath());
            } catch (Exception e) {
                enqueueError(id, kind, e.toString());
            } finally {
                suggestedNames.remove(id);
            }
            return;
        }

        List<Uri> uris = new ArrayList<>();
        ClipData clip = data.getClipData();
        if (clip != null) {
            for (int i = 0; i < clip.getItemCount(); i++) {
                Uri uri = clip.getItemAt(i).getUri();
                if (uri != null) uris.add(uri);
            }
        } else if (data.getData() != null) {
            uris.add(data.getData());
        }
        if (uris.isEmpty()) { enqueueCancel(id, kind); return; }
        for (Uri uri : uris) persistPermission(uri, data);
        io.execute(() -> {
            try {
                JSONArray paths = new JSONArray();
                for (Uri uri : uris) {
                    File stage = newStageFile(displayName(uri), uri);
                    copyUriToFile(uri, stage);
                    rememberUri(stage, uri);
                    paths.put(stage.getAbsolutePath());
                }
                JSONObject result = base(id, "open", "ok");
                result.put("paths", paths);
                results.offer(result.toString());
            } catch (Exception e) {
                enqueueError(id, "open", e.toString());
            }
        });
    }

    /** Commit an app-private staged file to its remembered SAF URI; used by Rust after every save. */
    public String pcCommitIfMapped(String path) {
        try {
            String uriText = getSharedPreferences(PREFS, MODE_PRIVATE).getString("uri:" + path, null);
            if (uriText == null) return "NONE";
            Uri uri = Uri.parse(uriText);
            OutputStream out = getContentResolver().openOutputStream(uri, "wt");
            if (out == null) out = getContentResolver().openOutputStream(uri, "w");
            if (out == null) return "ERROR: Android document provider did not open an output stream";
            try (InputStream in = new FileInputStream(new File(path)); OutputStream target = out) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = in.read(buffer)) != -1) target.write(buffer, 0, count);
                target.flush();
            }
            return "OK";
        } catch (Exception e) {
            Log.e(TAG, "Could not write a selected document", e);
            return "ERROR: Could not write the selected document: " + e.getMessage();
        }
    }

    /**
     * The working copy of a document the user chose through SAF. It lives under {@link #appStorageDir()}
     * so a file manager or a computer finds the file the app is editing, and inside a plain
     * {@code media} directory named after the document rather than a random per-open directory, so the
     * same document always lands on the same path.
     *
     * <p>A document that is opened again reuses its staged file; a different document whose name is
     * already taken gets a {@code " (2)"}-style suffix, because the staged path is the key that maps
     * back to the picked document and two documents sharing one path would overwrite each other.
     * A name whose staged copy has since been deleted (the app prunes working copies the recent list
     * let go of) is free again: the stale {@code uri:} mapping is harmless.
     */
    private File newStageFile(String name, Uri uri) throws Exception {
        File dir = new File(appStorageDir(), "media");
        if (!dir.mkdirs() && !dir.isDirectory()) throw new Exception("Could not create the media directory");
        String safe = safeName(name == null ? "imported-file" : name);
        String stem = safe, extension = "";
        int dot = safe.lastIndexOf('.');
        if (dot > 0) { stem = safe.substring(0, dot); extension = safe.substring(dot); }
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String owner = uri == null ? null : uri.toString();
        for (int attempt = 1; attempt <= 10000; attempt++) {
            String candidate = attempt == 1 ? safe : stem + " (" + attempt + ")" + extension;
            File file = new File(dir, candidate);
            String mapped = prefs.getString("uri:" + file.getAbsolutePath(), null);
            if (mapped == null || mapped.equals(owner) || !file.exists()) return file;
        }
        throw new Exception("Could not find a free name for the selected document in " + dir);
    }

    private static String safeName(String name) {
        String clean = name.replace('\\', '/');
        int slash = clean.lastIndexOf('/');
        if (slash >= 0) clean = clean.substring(slash + 1);
        clean = clean.replaceAll("[^A-Za-z0-9._() -]", "_").trim();
        if (clean.isEmpty() || clean.equals(".") || clean.equals("..")) return "untitled";
        return clean;
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) return safeName(cursor.getString(index));
            }
        } catch (Exception ignored) { }
        String segment = uri.getLastPathSegment();
        return segment == null ? "imported-file" : safeName(segment);
    }

    private void persistPermission(Uri uri, Intent data) {
        try {
            int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            if (flags != 0) getContentResolver().takePersistableUriPermission(uri, flags);
        } catch (Exception e) {
            Log.i(TAG, "Provider did not offer a persistable grant for " + uri, e);
        }
    }

    private void rememberUri(File path, Uri uri) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("uri:" + path.getAbsolutePath(), uri.toString()).apply();
    }

    private void copyUriToFile(Uri uri, File destination) throws Exception {
        InputStream input = getContentResolver().openInputStream(uri);
        if (input == null) throw new Exception("Android document provider did not open the selected file");
        try (InputStream in = input; FileOutputStream out = new FileOutputStream(destination)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
            out.flush();
        }
    }

    /**
     * Collect the file(s) an {@code ACTION_VIEW} / {@code ACTION_SEND} intent carries: the data URI
     * (opening a registered type), the intent's {@link ClipData} (modern shares) and the legacy
     * {@code EXTRA_STREAM} extra, de-duplicated. Anything else (in particular the launcher's MAIN
     * intent) is ignored so normal launches are untouched.
     */
    private static List<Uri> collectIncomingUris(Intent intent) {
        LinkedHashSet<Uri> uris = new LinkedHashSet<>();
        String action = intent.getAction();
        if (Intent.ACTION_VIEW.equals(action)) {
            if (intent.getData() != null) uris.add(intent.getData());
        } else if (Intent.ACTION_SEND.equals(action)) {
            Uri stream = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (stream != null) uris.add(stream);
        } else if (Intent.ACTION_SEND_MULTIPLE.equals(action)) {
            ArrayList<Uri> streams = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (streams != null) uris.addAll(streams);
        } else {
            return new ArrayList<>();
        }
        ClipData clip = intent.getClipData();
        if (clip != null) {
            for (int i = 0; i < clip.getItemCount(); i++) {
                Uri uri = clip.getItemAt(i).getUri();
                if (uri != null) uris.add(uri);
            }
        }
        return new ArrayList<>(uris);
    }

    /**
     * Copy every file the given intent carries into app-private staging and queue its path for the
     * Rust shell. Runs off the UI thread because the copy can be large; the shell polls
     * {@link #intentPoll()} until the path appears, so a slow copy never blocks startup.
     */
    private void handleIncomingFiles(Intent intent) {
        if (intent == null) return;
        List<Uri> uris = collectIncomingUris(intent);
        if (uris.isEmpty()) return;
        for (Uri uri : uris) persistPermission(uri, intent);
        io.execute(() -> {
            for (Uri uri : uris) {
                try {
                    File stage = newStageFile(displayName(uri), uri);
                    copyUriToFile(uri, stage);
                    rememberUri(stage, uri);
                    intentPaths.offer(stage.getAbsolutePath());
                } catch (Exception e) {
                    Log.e(TAG, "Could not open the file the system handed the app: " + uri, e);
                }
            }
        });
    }

    private JSONObject base(long id, String kind, String status) throws Exception {
        JSONObject value = new JSONObject();
        value.put("id", id);
        value.put("kind", kind);
        value.put("status", status);
        return value;
    }

    private void enqueueCancel(long id, String kind) {
        try { results.offer(base(id, kind, "cancel").toString()); }
        catch (Exception e) { Log.e(TAG, "Could not encode cancellation", e); }
    }

    private void enqueueError(long id, String kind, String message) {
        try {
            JSONObject value = base(id, kind, "error");
            value.put("message", message == null ? "Unknown Android file picker error" : message);
            results.offer(value.toString());
        } catch (Exception e) { Log.e(TAG, "Could not encode picker error", e); }
    }

    private void enqueueSave(long id, String path) {
        try {
            JSONObject value = base(id, "save", "ok");
            value.put("path", path);
            results.offer(value.toString());
        } catch (Exception e) { enqueueError(id, "save", e.toString()); }
    }

    private static String mimeFor(String fileName) {
        String lower = fileName.toLowerCase(java.util.Locale.ROOT);
        if (lower.endsWith(".png")) return "image/png";
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".webp")) return "image/webp";
        if (lower.endsWith(".gif")) return "image/gif";
        if (lower.endsWith(".tif") || lower.endsWith(".tiff")) return "image/tiff";
        if (lower.endsWith(".bmp")) return "image/bmp";
        if (lower.endsWith(".svg")) return "image/svg+xml";
        return "application/octet-stream";
    }
}
