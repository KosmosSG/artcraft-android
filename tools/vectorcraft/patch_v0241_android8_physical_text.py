"""VectorCraft v0.24.1 Android.8 — physical-key text is application text, NOT an IME terminal.

The successful Android.7 build encoded a physical printable KEY_DOWN as a
'c' (ImeEvent::Commit). The pinned VectorCraft Type-tool intentionally rejects
IME commits while IncomingComposition::Stale, so a plain key could disappear
despite reaching JNI. This patch changes ONLY the hardware-key transport to 't'
(egui::Event::Text); genuine InputConnection commits remain 'c'.

An unmodified Android KeyEvent also carries authoritative modifier state.
Queue a ModifiersChanged(NONE) before this tagged text and teach Android's
side-specific modifier tracker to honor that release. This prevents a missed
Ctrl key-up after Ctrl+Q from discarding subsequent plain characters.

Preserves stylus-button interception, Ctrl shortcuts, Android IME composition,
reset fences, doc isolation, and all non-Android upstream code. Test candidate;
not a device-verified fix.
"""
from pathlib import Path
import sys


def once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Android.8 {label}: expected exactly one reviewed anchor, found {count}")
    return source.replace(old, new, 1)


def patch(root: Path) -> None:
    adapter = Path(root) / "adapters/vectorcraft"
    java_path = adapter / "java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    bridge_path = adapter / "src/ime_bridge.rs"
    modifiers_path = adapter / "src/android_modifiers.rs"

    java = java_path.read_text()
    bridge = bridge_path.read_text()
    modifiers = modifiers_path.read_text()

    # Existing Android.7 patch has already run; keep all its key guards intact.
    old_physical = 'imeEvents.offer("c" + new String(Character.toChars(unicode)));'
    new_physical = 'imeEvents.offer("t" + new String(Character.toChars(unicode)));'
    java = once(java, old_physical, new_physical, "hardware key enqueue")
    # Counting at Activity dispatch distinguishes hardware keys arriving at
    # Android from characters reaching the focused IME-host EditText.
    java = once(java,
        '    private final java.util.concurrent.atomic.AtomicLong vcTraceCommits = new java.util.concurrent.atomic.AtomicLong();',
        '''    private final java.util.concurrent.atomic.AtomicLong vcTraceActivityKeys = new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcTracePhysicalText = new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcTraceCommits = new java.util.concurrent.atomic.AtomicLong();''',
        "privacy-safe physical keyboard counters")
    java = once(java,
        '    public boolean dispatchKeyEvent(KeyEvent event) {',
        '''    public boolean dispatchKeyEvent(KeyEvent event) {
        if (event != null && event.getAction() == KeyEvent.ACTION_DOWN
                && event.getDeviceId() >= 0 && !event.isSystem()) {
            vcTraceActivityKeys.incrementAndGet();
        }''',
        "Activity dispatch counter")
    java = once(java,
        '            + "; ime_callback_rejected=" + vcTraceRejected.get()',
        '''            + "; activity_physical_down=" + vcTraceActivityKeys.get()
            + "; physical_text_queued=" + vcTracePhysicalText.get()
            + "; ime_callback_rejected=" + vcTraceRejected.get()''',
        "copyable diagnostics counters")
    java = once(java, new_physical,
        'vcTracePhysicalText.incrementAndGet();' + chr(10) + '                            ' + new_physical,
        "physical text enqueue counter")
    java = once(java, '"VC_IME7 physical_text_commit key="',
                '"VC_IME8 physical_text_application key="', "privacy-safe hardware marker")

    # This specific tagged transport is not IME composition. The 'c' tag,
    # InputConnection generation filters and reset/ack queue remain unchanged.
    bridge = once(bridge,
        "        match tag {\n            'c' if !payload.is_empty() => {",
        """        match tag {
            // Plain physical keyboard characters are application edits, not
            // IME composition terminal commits guarded by reset fences.
            't' if !payload.is_empty() => Some(egui::Event::Text(payload.to_owned())),
            'c' if !payload.is_empty() => {""",
        "Java-to-egui event decoding")

    # Android.8 IME-reset patch has already installed the reset-id matching
    # branch here. Do not touch that branch or manufacture acknowledgements.
    bridge = once(bridge,
        """                        } else if let Some(event) = translate(&event) {
                            raw.events.push(event);
                        }""",
        """                        } else if let Some(event) = translate(&event) {
                            if event.starts_with_dummy_never() {
                                unreachable!()
                            }
                            raw.events.push(event);
                        }""".replace(
                            """                            if event.starts_with_dummy_never() {
                                unreachable!()
                            }
""",
                            """                            if matches!(&event, egui::Event::Text(_)) {
                                // Java issued this 't' only for a physical,
                                // unmodified key-down. Clear any missed Ctrl
                                // release BEFORE applying the character.
                                raw.events.push(egui::Event::ModifiersChanged(
                                    egui::Modifiers::NONE,
                                ));
                            }
"""
        ),
        "ordered raw-event enqueue")

    # The last statement makes only the physical 't' path return Event::Text,
    # so IME commits 'c' never reset the side-specific modifier tracker.
    modifiers = once(modifiers,
        """            egui::Event::Text(_) if state.modifiers().command => {}""",
        """            egui::Event::ModifiersChanged(modifiers)
                if !modifiers.ctrl && !modifiers.alt && !modifiers.command
                    && !modifiers.mac_cmd =>
            {
                // A trustworthy key-up/modifier snapshot from egui-winit,
                // or an explicitly unmodified physical Android 't' event.
                // Without this, a lost Ctrl-up can discard plain Text events.
                *state = AndroidModifiers::default();
                kept.push(event);
            }
            egui::Event::Text(_) if state.modifiers().command => {}""",
        "modifier-release authority")

    assert 'imeEvents.offer("c" + text);' in java
    assert new_physical in java
    assert 'vcImeFocusEpoch' in java
    assert 'if (vcStylusIntercept(event)) return true;' in java
    assert "get_temp::<Option<egui::ImeResetId>>(key).flatten()" in bridge
    assert "'c' if !payload.is_empty()" in bridge
    assert "'t' if !payload.is_empty()" in bridge
    assert "raw.events.push(egui::Event::ImeResetCompleted { request_id })" in bridge
    assert "egui::Event::ModifiersChanged(modifiers)" in modifiers

    # Build every transformation before mutating any file.
    java_path.write_text(java)
    bridge_path.write_text(bridge)
    modifiers_path.write_text(modifiers)
    print("PASS: Android.8 native hardware text route; IME reset and stylus shortcuts isolated")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
