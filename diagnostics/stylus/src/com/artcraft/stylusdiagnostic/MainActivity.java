package com.artcraft.stylusdiagnostic;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.HashSet;
import java.util.Set;
import java.util.Locale;
import java.util.Map;

/** Standalone diagnostic. No networking, input injection or dangerous permissions. */
public final class MainActivity extends Activity {
    private static final int EXPORT_REQUEST = 201;
    private static final int MAX_ROWS = 8000;
    private static final int CALIBRATION_REPEATS = 5;
    private static final int[] BUTTONS = {
        MotionEvent.BUTTON_STYLUS_PRIMARY,
        MotionEvent.BUTTON_STYLUS_SECONDARY,
        MotionEvent.BUTTON_SECONDARY
    };
    private final ArrayDeque<String> log = new ArrayDeque<>();
    private final Map<Integer, Press> press = new HashMap<>();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView counts, latest, recent, testStatus;
    private final ArrayList<Button> testButtons = new ArrayList<>();
    private final ArrayList<String> testSummaries = new ArrayList<>();
    private final Map<String, ArrayList<TestWindow>> calibration = new LinkedHashMap<>();
    private TestWindow activeTest;
    private Button nextTrialButton;
    private String selectedKind, selectedInstruction;
    private long selectedDurationMs;
    private int completedTests, nextTestId;
    private DrawingPad pad;
    private final Set<Integer> seenDevices = new HashSet<>();
    private int nonStylusTouches;
    private int lastButtonMask, hover, touch, pressureSamples, tiltSamples, edges;
    private int keys, singles, doubles, longs;
    private long lastSample, lastRender;
    private String latestLine = "Ready: hover your Magic-Pencil 4s over the dark test area.";

    private static final class Press {
        long downAt, lastRelease;
        Runnable pending;
    }

    private static final class TestWindow {
        int id, attempt;
        String kind;
        long startUptime, durationMs;
        final ArrayList<String> penKeySequence = new ArrayList<>();
        String signature, summary;
        int penKeyDown, penKeyUp, keyRepeats, orphanUp, matchedPairs;
        int heldAtLeast1400ms, otherKeyEvents, stylusContactEvents, standardButtonEdges;
        final Map<Integer, Long> pressedAt = new HashMap<>();
        Runnable timeout;
    }

    private int dp(float n) {
        return Math.round(n * getResources().getDisplayMetrics().density);
    }

    private TextView text(LinearLayout parent, String value, int size, int color) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(size);
        t.setTextColor(color);
        t.setPadding(0, dp(5), 0, dp(5));
        parent.addView(t);
        return t;
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.rgb(20, 28, 43));
        getWindow().setNavigationBarColor(Color.rgb(20, 28, 43));
        ScrollView scroll = new StylusSafeScrollView();
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(245, 247, 251));
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setPadding(dp(16), dp(14), dp(16), dp(24));
        scroll.addView(column);
        TextView heading = text(column, "ArtCraft Stylus Diagnostic", 22, Color.rgb(25, 38, 62));
        heading.setTypeface(null, 1);
        text(column, "Magic-Pencil 4s / MagicPad 4 - TEST ONLY\n"
            + "No network, storage or accessibility permissions. Logs stay local until exported.",
            13, Color.DKGRAY);
        counts = text(column, "", 14, Color.rgb(27, 48, 82));
        latest = text(column, "", 12, Color.rgb(33, 81, 139));
        text(column, "Hover or draw on the dark canvas. Finger swipes can scroll this screen, "
            + "but the pen must draw without scrolling. Test the pen button during hover and contact.",
            13, Color.DKGRAY);
        pad = new DrawingPad();
        column.addView(pad, new LinearLayout.LayoutParams(-1, dp(320)));
        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        Button export = new Button(this);
        export.setText("Export .txt");
        export.setOnClickListener(v -> exportLog());
        controls.addView(export, new LinearLayout.LayoutParams(0, dp(56), 1));
        Button clear = new Button(this);
        clear.setText("Clear log");
        clear.setOnClickListener(v -> clearLog());
        controls.addView(clear, new LinearLayout.LayoutParams(0, dp(56), 1));
        column.addView(controls);
        text(column, "BUTTON CALIBRATION — choose a gesture, then perform it ONCE "
            + "in each of FIVE individually timed trials. After each trial, tap "
            + "Record next trial. Repeat for the other gesture types.",
            13, Color.rgb(27, 48, 82));
        testStatus = text(column, "Choose a gesture below to record trial 1 of 5.",
            13, Color.rgb(33, 81, 139));
        LinearLayout testRow1 = new LinearLayout(this);
        testRow1.setOrientation(LinearLayout.HORIZONTAL);
        addTestButton(testRow1, "1. Single 5x", "SINGLE_HOVER", 8000,
            "Hover above the dark canvas and press the pen button ONCE.");
        addTestButton(testRow1, "2. Double 5x", "DOUBLE_HOVER", 8000,
            "Hover above the dark canvas and press TWICE quickly.");
        column.addView(testRow1);
        LinearLayout testRow2 = new LinearLayout(this);
        testRow2.setOrientation(LinearLayout.HORIZONTAL);
        addTestButton(testRow2, "3. Long 5x", "LONG_HOVER", 10000,
            "Hover and hold the pen button for TWO SECONDS, then release.");
        addTestButton(testRow2, "4. Drawing 5x", "PRESS_WHILE_DRAWING", 10000,
            "Draw on canvas while pressing and releasing the pen button.");
        column.addView(testRow2);
        nextTrialButton = new Button(this);
        nextTrialButton.setText("Record next trial");
        nextTrialButton.setEnabled(false);
        nextTrialButton.setOnClickListener(v -> beginNextTrial());
        column.addView(nextTrialButton, new LinearLayout.LayoutParams(-1, dp(55)));
        text(column, "Each trial includes its own exact key sequence (even orphan releases). "
            + "A consistent key sequence is NOT proof that the physical gesture is uniquely "
            + "recognized. No shortcuts execute.",
            12, Color.DKGRAY);
        text(column, "RECENT EVENTS. Raw KeyEvents are not automatically attributed to the stylus.",
            12, Color.DKGRAY);
        recent = text(column, "No events yet.", 11, Color.rgb(72, 79, 92));
        setContentView(scroll);
        add("SESSION_START", "model=" + Build.MANUFACTURER + " " + Build.MODEL
            + " api=" + Build.VERSION.SDK_INT + " package=com.artcraft.stylusdiagnostic");
        for (int id : InputDevice.getDeviceIds()) recordDevice(id);
        updateUi(true);
    }


    private void addTestButton(LinearLayout row, String label, String kind,
            long durationMs, String instruction) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(13);
        b.setAllCaps(false);
        b.setOnClickListener(v -> selectCalibration(kind, durationMs, instruction));
        row.addView(b, new LinearLayout.LayoutParams(0, dp(64), 1));
        testButtons.add(b);
    }

    private void selectCalibration(String kind, long durationMs, String instruction) {
        if (activeTest != null) {
            Toast.makeText(this, "Wait until the active trial finishes.", Toast.LENGTH_SHORT).show();
            return;
        }
        // Selecting the same category again intentionally starts a new five-trial set.
        selectedKind = kind;
        selectedInstruction = instruction;
        selectedDurationMs = durationMs;
        calibration.put(kind, new ArrayList<TestWindow>());
        add("CALIBRATION_BEGIN", "kind=" + kind + " repeats=" + CALIBRATION_REPEATS
            + " trial_ms=" + durationMs);
        beginNextTrial();
    }

    private void beginNextTrial() {
        if (activeTest != null || selectedKind == null) return;
        ArrayList<TestWindow> group = calibration.get(selectedKind);
        if (group == null || group.size() >= CALIBRATION_REPEATS) return;
        TestWindow t = new TestWindow();
        t.id = ++nextTestId;
        t.attempt = group.size() + 1;
        t.kind = selectedKind;
        t.durationMs = selectedDurationMs;
        t.startUptime = SystemClock.uptimeMillis();
        activeTest = t;
        nextTrialButton.setEnabled(false);
        for (Button b : testButtons) b.setEnabled(false);
        add("CALIBRATION_TRIAL_BEGIN", "id=" + t.id + " kind=" + t.kind
            + " attempt=" + t.attempt + "/" + CALIBRATION_REPEATS
            + " window_ms=" + t.durationMs + " instruction=" + selectedInstruction);
        testStatus.setText("RECORDING " + t.kind + " (trial " + t.attempt + "/"
            + CALIBRATION_REPEATS + ") for " + (t.durationMs / 1000)
            + " seconds. " + selectedInstruction);
        latestLine = "Trial " + t.attempt + "/5: " + selectedInstruction;
        updateUi(true);
        Toast.makeText(this, "Trial " + t.attempt + "/5: "
            + selectedInstruction, Toast.LENGTH_LONG).show();
        final int id = t.id;
        t.timeout = () -> endTest(id, false);
        handler.postDelayed(t.timeout, t.durationMs);
    }

    private void observeTestKey(KeyEvent e, InputDevice device) {
        TestWindow t = activeTest;
        if (t == null) return;
        if (device == null || device.getName() == null
                || !device.getName().contains("Magic-Pencil 4s")) {
            t.otherKeyEvents++;
            return;
        }
        int code = e.getKeyCode();
        long now = SystemClock.uptimeMillis();
        long delta = now - t.startUptime;
        String key = KeyEvent.keyCodeToString(code);
        String edge = e.getAction() == KeyEvent.ACTION_DOWN ? "DOWN" : "UP";
        t.penKeySequence.add(key + "(" + code + "):" + edge
            + (e.getRepeatCount() == 0 ? "" : ":repeat" + e.getRepeatCount()));
        if (e.getAction() == KeyEvent.ACTION_DOWN) {
            if (e.getRepeatCount() > 0 || t.pressedAt.containsKey(code)) {
                t.keyRepeats++;
            } else {
                t.penKeyDown++;
                t.pressedAt.put(code, now);
            }
        } else if (e.getAction() == KeyEvent.ACTION_UP) {
            t.penKeyUp++;
            Long started = t.pressedAt.remove(code);
            if (started == null) {
                t.orphanUp++;
            } else {
                t.matchedPairs++;
                if (now - started >= 1400) t.heldAtLeast1400ms++;
            }
        }
        add("CALIBRATION_PEN_KEY", "id=" + t.id + " kind=" + t.kind
            + " attempt=" + t.attempt
            + " elapsed_ms=" + delta + " key=" + key + " code=" + code
            + " action=" + edge
            + " repeat=" + e.getRepeatCount() + " scan=" + e.getScanCode()
            + " device=" + e.getDeviceId()
            + " matched_pairs=" + t.matchedPairs
            + " orphan_up=" + t.orphanUp);
        testStatus.setText("Recording " + t.kind + " trial " + t.attempt + "/5"
            + ": pen-key DOWN=" + t.penKeyDown
            + ", UP=" + t.penKeyUp + ", matched=" + t.matchedPairs
            + ", unmatched release=" + t.orphanUp
            + ". Continue the requested gesture until test ends.");
    }

    private void endTest(int id, boolean cancelled) {
        TestWindow t = activeTest;
        if (t == null || t.id != id) return;
        if (t.timeout != null) handler.removeCallbacks(t.timeout);
        activeTest = null;
        for (Button b : testButtons) b.setEnabled(true);
        int unmatchedDown = t.pressedAt.size();
        String observation = cancelled ? "CANCELLED"
            : t.penKeyDown == 0 && t.penKeyUp == 0 && t.standardButtonEdges == 0
                ? "NO_BUTTON_SIGNAL_OBSERVED"
            : t.orphanUp > 0 || unmatchedDown > 0
                ? "PARTIAL_KEY_PAIRS"
            : "KEY_PAIRS_CAPTURED_NOT_GESTURE_PROOF";
        t.signature = t.penKeySequence.isEmpty()
            ? (t.standardButtonEdges == 0 ? "NONE" : "STANDARD_BUTTON_EDGES")
            : String.join(",", t.penKeySequence);
        t.summary = "id=" + t.id + " kind=" + t.kind
            + " attempt=" + t.attempt + "/" + CALIBRATION_REPEATS
            + " result=" + observation
            + " signature=" + t.signature
            + " pen_down=" + t.penKeyDown + " pen_up=" + t.penKeyUp
            + " matched_pairs=" + t.matchedPairs + " orphan_up=" + t.orphanUp
            + " unmatched_down=" + unmatchedDown
            + " keypair_held_1400ms=" + t.heldAtLeast1400ms
            + " repeat_down=" + t.keyRepeats
            + " other_key_events=" + t.otherKeyEvents
            + " stylus_contact_events=" + t.stylusContactEvents
            + " standard_button_edges=" + t.standardButtonEdges;
        add(cancelled ? "CALIBRATION_TRIAL_CANCELLED" : "CALIBRATION_TRIAL_END", t.summary);
        if (!cancelled) {
            completedTests++;
            testSummaries.add(t.summary);
            ArrayList<TestWindow> group = calibration.get(t.kind);
            if (group != null) group.add(t);
            boolean done = group != null && group.size() == CALIBRATION_REPEATS;
            String summary = calibrationSummary(t.kind);
            if (done) {
                add("CALIBRATION_COMPLETE", summary);
                String contrast = compareHoverSignatures();
                if (!contrast.isEmpty()) add("CALIBRATION_CROSS_GESTURE", contrast);
            }
            testStatus.setText((done ? "5/5 COMPLETE: " : "TRIAL COMPLETE: ")
                + t.kind + " " + t.attempt + "/" + CALIBRATION_REPEATS
                + "\\n" + summary + "\\n"
                + (done ? "Select another category to calibrate."
                    : "Tap Record next trial for the next repetition."));
            nextTrialButton.setEnabled(!done && t.kind.equals(selectedKind));
        } else {
            nextTrialButton.setEnabled(false);
            testStatus.setText("Trial cancelled. Choose a gesture.");
        }
        latestLine = "Trial " + t.attempt + ": " + observation;
        updateUi(true);
    }

    private String calibrationSummary(String kind) {
        ArrayList<TestWindow> group = calibration.get(kind);
        if (group == null || group.isEmpty()) return "kind=" + kind + " trials=0/5";
        Map<String, Integer> patterns = new LinkedHashMap<>();
        for (TestWindow t : group) {
            Integer n = patterns.get(t.signature);
            patterns.put(t.signature, n == null ? 1 : n + 1);
        }
        String dominant = "", counts = "";
        int max = 0;
        for (Map.Entry<String, Integer> entry : patterns.entrySet()) {
            if (entry.getValue() > max) {
                max = entry.getValue();
                dominant = entry.getKey();
            }
            if (!counts.isEmpty()) counts += " | ";
            counts += entry.getValue() + "x{" + entry.getKey() + "}";
        }
        boolean complete = group.size() == CALIBRATION_REPEATS;
        String repeatability = !complete ? "INCOMPLETE"
            : max == CALIBRATION_REPEATS ? "SAME_EVENT_PATTERN_5_OF_5"
            : max >= 4 ? "SAME_EVENT_PATTERN_4_OF_5" : "VARIABLE_EVENT_PATTERNS";
        if ("NONE".equals(dominant) && max == CALIBRATION_REPEATS)
            repeatability = "NO_INPUT_REPORTED_5_OF_5";
        return "kind=" + kind + " completed=" + group.size() + "/"
            + CALIBRATION_REPEATS + " repeatability=" + repeatability
            + " dominant_count=" + max + " dominant_pattern=" + dominant
            + " observed_patterns=" + counts
            + " note=patterns_are_not_proof_of_distinct_physical_gestures";
    }

    private String compareHoverSignatures() {
        ArrayList<TestWindow> single = calibration.get("SINGLE_HOVER");
        ArrayList<TestWindow> dbl = calibration.get("DOUBLE_HOVER");
        if (single == null || dbl == null
                || single.size() != CALIBRATION_REPEATS
                || dbl.size() != CALIBRATION_REPEATS) return "";
        String a = dominantSignature(single), b = dominantSignature(dbl);
        if (a.equals(b)) return "SINGLE_AND_DOUBLE_SHARE_DOMINANT_PATTERN="
            + a + " automated_shortcut_mapping_is_not_safe";
        return "SINGLE_AND_DOUBLE_DIFFERENT_DOMINANT_PATTERNS single=" + a
            + " double=" + b + " requires_device_validation";
    }

    private String dominantSignature(ArrayList<TestWindow> items) {
        Map<String, Integer> freq = new HashMap<>();
        String best = "";
        int n = 0;
        for (TestWindow item : items) {
            int count = freq.containsKey(item.signature)
                ? freq.get(item.signature) + 1 : 1;
            freq.put(item.signature, count);
            if (count > n) { best = item.signature; n = count; }
        }
        return best;
    }

    private void add(String type, String details) {
        String date = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(new Date());
        log.addLast(date + "\t" + type + "\t" + details.replace('\n', ' '));
        while (log.size() > MAX_ROWS) log.removeFirst();
    }

    private void recordDevice(int id) {
        if (id < 0 || !seenDevices.add(id)) return;
        InputDevice d = InputDevice.getDevice(id);
        if (d == null) {
            add("INPUT_DEVICE", "id=" + id + " descriptor_unavailable");
            return;
        }
        add("INPUT_DEVICE", "id=" + id
            + " name=" + d.getName().replace('\n', ' ')
            + " vendorId=" + d.getVendorId()
            + " productId=" + d.getProductId()
            + " sources=0x" + Integer.toHexString(d.getSources())
            + " keyboardType=" + d.getKeyboardType()
            + " isExternal=" + d.isExternal());
    }

    @Override public boolean dispatchTouchEvent(MotionEvent e) {
        monitor(e);
        if (pad != null) pad.capture(e);
        return super.dispatchTouchEvent(e);
    }

    @Override public boolean dispatchGenericMotionEvent(MotionEvent e) {
        monitor(e);
        if (pad != null) pad.capture(e);
        return super.dispatchGenericMotionEvent(e);
    }

    @Override public boolean dispatchKeyEvent(KeyEvent e) {
        if (e.getAction() == KeyEvent.ACTION_DOWN || e.getAction() == KeyEvent.ACTION_UP) {
            keys++;
            recordDevice(e.getDeviceId());
            InputDevice origin = InputDevice.getDevice(e.getDeviceId());
            String deviceName = origin == null ? "UNKNOWN" : origin.getName().replace('\n', ' ');
            String s = KeyEvent.keyCodeToString(e.getKeyCode())
                + " action=" + (e.getAction() == KeyEvent.ACTION_DOWN ? "DOWN" : "UP")
                + " repeat=" + e.getRepeatCount() + " scan=" + e.getScanCode()
                + " device=" + e.getDeviceId() + " deviceName=" + deviceName
                + " source=0x" + Integer.toHexString(e.getSource());
            add("UNATTRIBUTED_KEY_EVENT", s);
            observeTestKey(e, origin);
            latestLine = s + "\n(Key could be from keyboard, system or pen.)";
            updateUi(true);
        }
        // MagicOS exposes some pen-button signals as keyboard-style DPAD_UP/DOWN
        // from its external "HONOR Magic-Pencil 4s Mouse" device.  We must
        // observe them but not let ScrollView interpret them as navigation.
        if (isMagicPencilNavigationKey(e)) {
            if (e.getAction() == KeyEvent.ACTION_DOWN && e.getRepeatCount() == 0) {
                add("PEN_NAVIGATION_SCROLL_BLOCKED",
                    KeyEvent.keyCodeToString(e.getKeyCode())
                    + " device=" + e.getDeviceId());
                updateUi(true);
            }
            return true;
        }
        return super.dispatchKeyEvent(e);
    }

    private boolean isMagicPencilNavigationKey(KeyEvent e) {
        int code = e.getKeyCode();
        if (code != KeyEvent.KEYCODE_DPAD_UP && code != KeyEvent.KEYCODE_DPAD_DOWN)
            return false;
        InputDevice origin = e.getDevice();
        return origin != null && origin.getName() != null
            && origin.getName().contains("Magic-Pencil 4s");
    }

    // Keep finger-driven scrolling, but never claim stylus swipes as scroll gestures.
    private final class StylusSafeScrollView extends ScrollView {
        StylusSafeScrollView() { super(MainActivity.this); }

        @Override public boolean onInterceptTouchEvent(MotionEvent e) {
            if (isStylus(e)) return false;
            return super.onInterceptTouchEvent(e);
        }

        @Override public boolean onTouchEvent(MotionEvent e) {
            if (isStylus(e)) return false;
            return super.onTouchEvent(e);
        }

        @Override public boolean onGenericMotionEvent(MotionEvent e) {
            if (isStylus(e) && e.getActionMasked() == MotionEvent.ACTION_SCROLL)
                return false;
            return super.onGenericMotionEvent(e);
        }
    }

    private boolean isStylus(MotionEvent e) {
        if ((e.getSource() & InputDevice.SOURCE_STYLUS) == InputDevice.SOURCE_STYLUS) return true;
        for (int i = 0; i < e.getPointerCount(); i++) {
            int t = e.getToolType(i);
            if (t == MotionEvent.TOOL_TYPE_STYLUS || t == MotionEvent.TOOL_TYPE_ERASER) return true;
        }
        return (e.getButtonState()
            & (MotionEvent.BUTTON_STYLUS_PRIMARY | MotionEvent.BUTTON_STYLUS_SECONDARY)) != 0;
    }

    private String action(int a) {
        switch (a) {
            case MotionEvent.ACTION_HOVER_ENTER: return "HOVER_ENTER";
            case MotionEvent.ACTION_HOVER_MOVE: return "HOVER_MOVE";
            case MotionEvent.ACTION_HOVER_EXIT: return "HOVER_EXIT";
            case MotionEvent.ACTION_DOWN: return "DOWN";
            case MotionEvent.ACTION_UP: return "UP";
            case MotionEvent.ACTION_MOVE: return "MOVE";
            case MotionEvent.ACTION_CANCEL: return "CANCEL";
            case MotionEvent.ACTION_BUTTON_PRESS: return "BUTTON_PRESS";
            case MotionEvent.ACTION_BUTTON_RELEASE: return "BUTTON_RELEASE";
            case MotionEvent.ACTION_POINTER_DOWN: return "POINTER_DOWN";
            case MotionEvent.ACTION_POINTER_UP: return "POINTER_UP";
            default: return "ACTION_" + a;
        }
    }

    private void monitor(MotionEvent e) {
        if (e.getPointerCount() == 0) return;
        recordDevice(e.getDeviceId());
        int a = e.getActionMasked();
        if (!isStylus(e)) {
            if (a == MotionEvent.ACTION_DOWN || a == MotionEvent.ACTION_UP) {
                nonStylusTouches++;
                add("NON_STYLUS_TOUCH", action(a) + " toolType=" + e.getToolType(0)
                    + " device=" + e.getDeviceId()
                    + " source=0x" + Integer.toHexString(e.getSource()));
                updateUi(true);
            }
            return;
        }
        long now = SystemClock.uptimeMillis();
        TestWindow t = activeTest;
        if (t != null && (a == MotionEvent.ACTION_DOWN
                || a == MotionEvent.ACTION_MOVE || a == MotionEvent.ACTION_UP))
            t.stylusContactEvents++;
        boolean buttonChanged = trackButtons(e, a, now);
        boolean move = a == MotionEvent.ACTION_MOVE || a == MotionEvent.ACTION_HOVER_MOVE;
        if (move && !buttonChanged && now - lastSample < 45) return;
        lastSample = now;
        if (a == MotionEvent.ACTION_HOVER_MOVE || a == MotionEvent.ACTION_HOVER_ENTER) hover++;
        if (a == MotionEvent.ACTION_DOWN || a == MotionEvent.ACTION_MOVE) touch++;
        float p = e.getPressure(0);
        float tilt = e.getAxisValue(MotionEvent.AXIS_TILT, 0);
        float distance = e.getAxisValue(MotionEvent.AXIS_DISTANCE, 0);
        if (p > 0f && (a == MotionEvent.ACTION_DOWN || a == MotionEvent.ACTION_MOVE))
            pressureSamples++;
        if (Math.abs(tilt) > 0.001f) tiltSamples++;
        String tool = e.getToolType(0) == MotionEvent.TOOL_TYPE_STYLUS ? "STYLUS"
            : e.getToolType(0) == MotionEvent.TOOL_TYPE_ERASER ? "ERASER" : "OTHER";
        latestLine = String.format(Locale.US,
            "%s tool=%s x=%.1f y=%.1f pressure=%.3f tilt=%.3f distance=%.3f "
            + "buttons=0x%x actionButton=0x%x pointers=%d device=%d source=0x%x",
            action(a), tool, e.getX(0), e.getY(0), p, tilt, distance,
            e.getButtonState(), e.getActionButton(), e.getPointerCount(),
            e.getDeviceId(), e.getSource());
        add("MOTION", latestLine);
        updateUi(buttonChanged || !move);
    }

    private boolean trackButtons(MotionEvent e, int a, long now) {
        int mask = e.getButtonState();
        if (a == MotionEvent.ACTION_BUTTON_PRESS) mask |= e.getActionButton();
        if (a == MotionEvent.ACTION_BUTTON_RELEASE) mask &= ~e.getActionButton();
        int changed = lastButtonMask ^ mask;
        for (int bit : BUTTONS) {
            if ((changed & bit) == 0) continue;
            boolean down = (mask & bit) != 0;
            edges++;
            if (activeTest != null) activeTest.standardButtonEdges++;
            add("BUTTON_EDGE", "button=0x" + Integer.toHexString(bit)
                + " state=" + (down ? "PRESSED" : "RELEASED")
                + " device=" + e.getDeviceId());
            classify(bit, down, now);
        }
        lastButtonMask = mask;
        return changed != 0;
    }

    private void classify(int bit, boolean down, long now) {
        Press p = press.get(bit);
        if (p == null) { p = new Press(); press.put(bit, p); }
        final Press state = p;
        if (down) { state.downAt = now; return; }
        if (state.downAt == 0) return;
        long duration = now - state.downAt;
        state.downAt = 0;
        if (duration >= 650) {
            if (state.pending != null) handler.removeCallbacks(state.pending);
            state.pending = null;
            longs++;
            add("GESTURE_LONG", "button=0x" + Integer.toHexString(bit)
                + " held_ms=" + duration);
        } else if (state.pending != null && now - state.lastRelease <= 380) {
            handler.removeCallbacks(state.pending);
            state.pending = null;
            doubles++;
            add("GESTURE_DOUBLE", "button=0x" + Integer.toHexString(bit));
        } else {
            Runnable onSingle = () -> {
                singles++;
                add("GESTURE_SINGLE", "button=0x" + Integer.toHexString(bit));
                state.pending = null;
                updateUi(true);
            };
            state.pending = onSingle;
            handler.postDelayed(onSingle, 390);
        }
        state.lastRelease = now;
    }

    private void updateUi(boolean forced) {
        long now = SystemClock.uptimeMillis();
        if (!forced && now - lastRender < 100) return;
        lastRender = now;
        counts.setText("Hover: " + hover + "  Contact: " + touch
            + "  Pressure: " + pressureSamples + "  Tilt: " + tiltSamples
            + "  Other touches: " + nonStylusTouches
            + "\nButton edges: " + edges + "  Single/Double/Long: "
            + singles + "/" + doubles + "/" + longs + "  KeyEvents: " + keys
            + "\nCompleted calibration trials: " + completedTests + "/20");
        latest.setText(latestLine);
        StringBuilder s = new StringBuilder();
        int skip = Math.max(0, log.size() - 8), i = 0;
        for (String line : log) if (i++ >= skip) s.append(line).append('\n');
        recent.setText(s.toString());
    }

    private void clearLog() {
        if (activeTest != null) endTest(activeTest.id, true);
        calibration.clear();
        selectedKind = selectedInstruction = null;
        selectedDurationMs = 0;
        if (nextTrialButton != null) nextTrialButton.setEnabled(false);
        testSummaries.clear();
        completedTests = nextTestId = 0;
        if (testStatus != null) testStatus.setText("Ready. Choose a 5x calibration test.");
        for (Press p : press.values()) if (p.pending != null) handler.removeCallbacks(p.pending);
        press.clear();
        log.clear();
        lastButtonMask = 0;
        hover = touch = pressureSamples = tiltSamples = edges = keys = singles = doubles = longs = 0;
        nonStylusTouches = 0;
        latestLine = "Cleared. Ready for next test.";
        pad.clear();
        add("SESSION_CLEARED", "user_action");
        updateUi(true);
    }

    private void exportLog() {
        if (activeTest != null) {
            Toast.makeText(this, "Finish the active test before exporting.", Toast.LENGTH_LONG).show();
            return;
        }
        Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        i.setType("text/plain");
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.putExtra(Intent.EXTRA_TITLE, "artcraft-stylus-4s-diagnostic.txt");
        startActivityForResult(i, EXPORT_REQUEST);
    }

    @Override protected void onActivityResult(int req, int result, Intent data) {
        super.onActivityResult(req, result, data);
        if (req != EXPORT_REQUEST || result != RESULT_OK
            || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        StringBuilder s = new StringBuilder("ARTCRAFT STYLUS DIAGNOSTIC TEST ONLY\n")
            .append("Device: ").append(Build.MANUFACTURER).append(' ').append(Build.MODEL)
            .append(" API: ").append(Build.VERSION.SDK_INT)
            .append("\nApp: com.artcraft.stylusdiagnostic\n")
            .append("Hover: ").append(hover)
            .append("\nContact: ").append(touch)
            .append("\nPressure samples: ").append(pressureSamples)
            .append("\nNonzero tilt samples: ").append(tiltSamples)
            .append("\nButton edges: ").append(edges)
            .append("\nSingle/Double/Long: ").append(singles).append('/')
            .append(doubles).append('/').append(longs)
            .append("\nOther touch samples: ").append(nonStylusTouches)
            .append("\nUnattributed KeyEvents: ").append(keys)
            .append("\nNote: KeyEvents cannot be attributed to the pen without verification.")
            .append("\nCompleted labeled calibration trials: ").append(completedTests)
            .append("\nEach gesture requires five separate timed trials. The reported signature is an app-visible event sequence, not proven gesture recognition.")
            .append("\nA 2ms Android key-pair interval cannot measure a physical long press.")
            .append("\nOrphan releases and missing key signals remain explicit.")
            .append("\nCALIBRATION_SUMMARY_BEGIN\n");
        for (String kind : new String[]{"SINGLE_HOVER", "DOUBLE_HOVER",
                "LONG_HOVER", "PRESS_WHILE_DRAWING"})
            s.append(calibrationSummary(kind)).append('\n');
        String comparison = compareHoverSignatures();
        if (!comparison.isEmpty()) s.append("CROSS_GESTURE ").append(comparison).append('\n');
        s.append("CALIBRATION_SUMMARY_END\n")
            .append("CALIBRATION_TRIALS_BEGIN\n")
            .append(String.join("\n", testSummaries))
            .append("\nCALIBRATION_TRIALS_END")
            .append("\nLog retains newest ").append(MAX_ROWS)
            .append(" rows. Coordinates and local timestamps are included.\n\n")
            .append("TIME\tTYPE\tDETAILS\n");
        for (String row : log) s.append(row).append('\n');
        try (OutputStream out = getContentResolver().openOutputStream(uri)) {
            if (out == null) throw new IllegalStateException("No output stream");
            out.write(s.toString().getBytes(StandardCharsets.UTF_8));
            Toast.makeText(this, "Export successful", Toast.LENGTH_LONG).show();
        } catch (Exception ex) {
            Toast.makeText(this, "Export failed: " + ex.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override protected void onDestroy() {
        if (activeTest != null && activeTest.timeout != null)
            handler.removeCallbacks(activeTest.timeout);
        for (Press p : press.values())
            if (p.pending != null) handler.removeCallbacks(p.pending);
        super.onDestroy();
    }

    private final class DrawingPad extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        // [x0, y0, x1, y1, pressure] for continuous connected strokes.
        private final ArrayList<float[]> segments = new ArrayList<>();
        private final int[] screenLocation = new int[2];
        private float x = -1, y = -1, p;
        private float prevX, prevY;
        private boolean active, hovering;
        private int strokeId;

        DrawingPad() {
            super(MainActivity.this);
            setBackgroundColor(Color.rgb(21, 31, 49));
            setClickable(true);
        }

        void clear() {
            segments.clear();
            active = false;
            strokeId = 0;
            x = -1;
            postInvalidateOnAnimation();
        }

        private boolean inside(float xx, float yy) {
            return xx >= 0 && yy >= 0 && xx <= getWidth() && yy <= getHeight();
        }

        private void segment(float nextX, float nextY, float pressure) {
            float level = Math.max(0f, Math.min(1f, pressure));
            segments.add(new float[]{prevX, prevY, nextX, nextY, level});
            if (segments.size() > 10000) segments.remove(0);
            prevX = nextX;
            prevY = nextY;
        }

        // Feed from Activity.dispatchTouchEvent before ScrollView can consume drag moves.
        void capture(MotionEvent e) {
            if (!isStylus(e) || e.getPointerCount() == 0 || getWidth() <= 0) return;
            getLocationOnScreen(screenLocation);
            float localX = e.getRawX() - screenLocation[0];
            float localY = e.getRawY() - screenLocation[1];
            int a = e.getActionMasked();

            if (a == MotionEvent.ACTION_HOVER_MOVE || a == MotionEvent.ACTION_HOVER_ENTER) {
                hovering = true;
                x = inside(localX, localY) ? localX : -1;
                y = localY;
                p = 0;
                postInvalidateOnAnimation();
                return;
            }
            if (a == MotionEvent.ACTION_HOVER_EXIT) {
                hovering = false;
                x = -1;
                postInvalidateOnAnimation();
                return;
            }
            if (a == MotionEvent.ACTION_DOWN) {
                if (!inside(localX, localY)) return;
                active = true;
                hovering = false;
                strokeId++;
                prevX = localX;
                prevY = localY;
                p = e.getPressure(0);
                x = localX;
                y = localY;
                segment(localX, localY, p);
                // A stylus stroke must not turn into scrolling of the parent view.
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(true);
                add("CANVAS_STROKE_START", "stroke=" + strokeId
                    + " x=" + localX + " y=" + localY);
                postInvalidateOnAnimation();
                return;
            }
            if (a == MotionEvent.ACTION_MOVE && active) {
                // Include points buffered by Android to keep curves continuous.
                float offsetX = e.getRawX() - e.getX(0);
                float offsetY = e.getRawY() - e.getY(0);
                for (int h = 0; h < e.getHistorySize(); h++) {
                    float hx = e.getHistoricalX(0, h) + offsetX - screenLocation[0];
                    float hy = e.getHistoricalY(0, h) + offsetY - screenLocation[1];
                    segment(hx, hy, e.getHistoricalPressure(0, h));
                }
                segment(localX, localY, e.getPressure(0));
                x = localX;
                y = localY;
                p = e.getPressure(0);
                postInvalidateOnAnimation();
                return;
            }
            if ((a == MotionEvent.ACTION_UP || a == MotionEvent.ACTION_CANCEL) && active) {
                if (a == MotionEvent.ACTION_UP) segment(localX, localY, e.getPressure(0));
                active = false;
                x = a == MotionEvent.ACTION_CANCEL ? -1 : localX;
                y = localY;
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(false);
                add("CANVAS_STROKE_END", "stroke=" + strokeId
                    + " action=" + action(a) + " segment_count=" + segments.size());
                postInvalidateOnAnimation();
            }
        }

        @Override public boolean onHoverEvent(MotionEvent e) {
            // Hover rendering already handled by Activity dispatch; no duplicate samples.
            return isStylus(e) || super.onHoverEvent(e);
        }

        @Override public boolean onTouchEvent(MotionEvent e) {
            if (!isStylus(e)) return super.onTouchEvent(e);
            // Activity captures all stylus samples even if the parent steals input.
            return true;
        }

        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            paint.setStyle(Paint.Style.STROKE);
            paint.setColor(Color.rgb(49, 65, 85));
            paint.setStrokeWidth(dp(1));
            for (int xx = 0; xx < getWidth(); xx += dp(32))
                canvas.drawLine(xx, 0, xx, getHeight(), paint);
            for (int yy = 0; yy < getHeight(); yy += dp(32))
                canvas.drawLine(0, yy, getWidth(), yy, paint);

            paint.setColor(Color.rgb(82, 184, 248));
            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeJoin(Paint.Join.ROUND);
            for (float[] seg : segments) {
                paint.setStrokeWidth(dp(2.4f + 9f * seg[4]));
                canvas.drawLine(seg[0], seg[1], seg[2], seg[3], paint);
            }
            if (x >= 0 && inside(x, y)) {
                paint.setStyle(Paint.Style.STROKE);
                paint.setColor(hovering ? Color.rgb(255, 210, 90) : Color.WHITE);
                paint.setStrokeWidth(dp(2));
                canvas.drawCircle(x, y, dp(10 + 12 * p), paint);
                canvas.drawLine(x - dp(18), y, x + dp(18), y, paint);
                canvas.drawLine(x, y - dp(18), x, y + dp(18), paint);
            }
        }
    }
}
