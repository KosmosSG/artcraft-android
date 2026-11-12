"""Android.11 investigation overlay. No speculative typing or hit-test changes.

Apply after Android.10. Counters describe routes, never payloads. This is a
source investigation checkpoint, not a verified typing correction.
"""
from pathlib import Path
import sys


def replace(path, old, new, count=1):
    source = path.read_text()
    if source.count(old) != count:
        raise ValueError(f'{path.name}: expected {count} reviewed anchors, got {source.count(old)}')
    path.write_text(source.replace(old, new))


def patch(root):
    adapter = root / 'adapters/vectorcraft'
    java = adapter / 'java/com/artcraft/vectorcraft/VectorCraftActivity.java'
    host = adapter / 'src/lib.rs'
    ui = root / 'source/vectorcraft/crates/ui-egui/src'
    engine = root / 'source/vectorcraft/crates/engine/src'
    counters = ['raw_text', 'raw_ime', 'type_route', 'stale_ime_rejected',
                'deferred_text_rejected', 'tool_text_calls', 'edit_generated',
                'edit_accepted', 'edit_rejected', 'edit_deferred', 'document_changes',
                'target_changes', 'reset_requested', 'reset_matched', 'reset_unmatched']
    module = '''//! Temporary aggregate Android typing diagnostics. No payloads or identifiers.
use std::sync::atomic::{AtomicU64, Ordering};
'''
    for name in counters:
        module += f'pub static {name.upper()}: AtomicU64 = AtomicU64::new(0);\n'
    module += '''pub fn bump(counter: &AtomicU64) {
    if cfg!(target_os = "android") { counter.fetch_add(1, Ordering::Relaxed); }
}
pub fn snapshot() -> String {
    let mut out = String::new();
'''
    for name in counters:
        module += f'    out.push_str(&format!("{name}={{}}\\n", {name.upper()}.load(Ordering::Relaxed)));\n'
    module += '    out\n}\n'
    (engine / 'android_typing_trace.rs').write_text(module)
    with (engine / 'lib.rs').open('a') as f:
        f.write('\n/// Aggregate Android test diagnostics; no user data.\npub mod android_typing_trace;\n')
    # Count the engine entry and generated previews separately. A successful
    # tool_text return does not imply preview acceptance: upstream logs errors.
    tooling = engine / 'tooling.rs'
    replace(tooling, '        let acts = self.with_tool_cx(view, |t, cx| t.text_input(cx, text));',
            '''        let acts = self.with_tool_cx(view, |t, cx| {
            crate::android_typing_trace::bump(&crate::android_typing_trace::TOOL_TEXT_CALLS);
            t.text_input(cx, text)
        });''')
    replace(tooling, '                Action::Preview(cmd, p) => {', '''                Action::Preview(cmd, p) => {
                    if cmd == "text.editRange" { crate::android_typing_trace::bump(&crate::android_typing_trace::EDIT_GENERATED); }''')
    replace(tooling, '                            it.preview = Some((cmd, p));', '''                            if cmd == "text.editRange" { crate::android_typing_trace::bump(&crate::android_typing_trace::EDIT_DEFERRED); }
                            it.preview = Some((cmd, p));''')
    # Scope instrumentation to Action::Preview; don't accidentally rewrite
    # other command/error branches with similar syntax.
    source = tooling.read_text()
    start = source.index('                Action::Preview(cmd, p) => {')
    end = source.index('                Action::Commit => {', start)
    part = source[start:end]
    assert part.count('                        Ok(v) => {') == 1
    part = part.replace('                        Ok(v) => {', '''                        Ok(v) => {
                            if cmd == "text.editRange" { crate::android_typing_trace::bump(&crate::android_typing_trace::EDIT_ACCEPTED); }''')
    old = '                        Err(e) => log::warn!("preview {cmd}: {e}"),'
    assert part.count(old) == 1
    part = part.replace(old, '''                        Err(e) => {
                            if cmd == "text.editRange" {
                                crate::android_typing_trace::bump(&crate::android_typing_trace::EDIT_REJECTED);
                                ui.push(UiRequest::Status("Text edit rejected; copy Keyboard Diagnostics.".into()));
                            }
                            log::warn!("preview {cmd}: {e}");
                        },''')
    tooling.write_text(source[:start] + part + source[end:])
    typing = ui / 'shortcuts/typing.rs'
    replace(typing, '    for e in seq {', '''    for e in seq {
        vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::TYPE_ROUTE);''')
    replace(typing, 'Seq::Commit(_) | Seq::DeleteSurrounding(..) | Seq::Preedit(..) => continue,', '''Seq::Commit(_) | Seq::DeleteSurrounding(..) | Seq::Preedit(..) => {
                    vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::STALE_IME_REJECTED);
                    continue;
                },''')
    replace(typing, 'Seq::Text(_) | Seq::Erase(..) | Seq::Edit(TextInput::Cut | TextInput::Paste(_)) => continue,', '''Seq::Text(_) | Seq::Erase(..) | Seq::Edit(TextInput::Cut | TextInput::Paste(_)) => {
                    vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::DEFERRED_TEXT_REJECTED);
                    continue;
                },''')
    replace(ui / 'ime.rs', '    let request = ctx.request_ime_reset(viewport);', '''    vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::RESET_REQUESTED);
    let request = ctx.request_ime_reset(viewport);''')
    replace(host, '    vc_last_doc_uid: Option<u64>,', '''    vc_last_doc_uid: Option<u64>,
    vc_trace_target: Option<(u64, u64)>,''')
    replace(host, '                vc_last_doc_uid: None,', '''                vc_last_doc_uid: None,
                vc_trace_target: None,''')
    replace(host, '            self.vc_last_doc_uid = current_uid;', '''            vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::DOCUMENT_CHANGES);
            self.vc_last_doc_uid = current_uid;''')
    replace(host, '        self.inner.raw_input_hook(ctx, raw);', '''        self.inner.raw_input_hook(ctx, raw);
        let view = self.inner.view_info();
        let target = self.inner.session.tool_ime_target(view).map(|(doc, node, _)| (doc, node));
        if target != self.vc_trace_target {
            self.vc_trace_target = target;
            vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::TARGET_CHANGES);
        }
        for event in &raw.events {
            match event {
                egui::Event::Text(_) => vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::RAW_TEXT),
                egui::Event::Ime(_) => vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::RAW_IME),
                _ => (),
            }
        }''')
    replace(host, 'VectorCraft v0.23.0-android.4 Diagnostic Session', 'VectorCraft {runtime_version} Diagnostic Session')
    replace(host, '                let elapsed=self.vc_diag_started.map_or(0,|t|t.elapsed().as_millis());', '''                let runtime_version = &self.installed_version;
                let elapsed=self.vc_diag_started.map_or(0,|t|t.elapsed().as_millis());''')
    replace(host, '                match self.bridge.copy_diagnostic_report(&report) {', '''                let report = format!("{report}\\naggregate_counters_since_launch:\\n{}capture_started={}\\n",
                    vectorcraft_engine::android_typing_trace::snapshot(), self.vc_diag_started.is_some());
                match self.bridge.copy_diagnostic_report(&report) {''')
    # Runtime version remains truthful even when the overlay is reused later.
    replace(java, '        return "java_stage=" + vcDiagStartupStage', '''        return "runtime_version=" + vcInstalledVersionName()
            + "\\nime_commit_callbacks=" + vcTraceCommits.get()
            + "; ime_callback_rejected=" + vcTraceRejected.get()
            + "; ime_rejection_reason=" + vcTraceRejectionReason
            + "; ime_resets=" + vcTraceResets.get()
            + "; pen_hover_events=" + vcTraceHover.get()
            + "\\njava_stage=" + vcDiagStartupStage''')
    replace(java, '    private long vcImeGeneration = 0L;', '''    private final java.util.concurrent.atomic.AtomicLong vcTraceCommits = new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcTraceRejected = new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcTraceResets = new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcTraceHover = new java.util.concurrent.atomic.AtomicLong();
    private volatile String vcTraceRejectionReason = "none";
    private long vcImeGeneration = 0L;''')
    replace(java, 'public boolean commitText(CharSequence text, int newCursorPosition) {', '''public boolean commitText(CharSequence text, int newCursorPosition) {
                            vcTraceCommits.incrementAndGet();''')
    replace(java, 'if (vcImeResetting || connectionGeneration != vcImeGeneration) return false;', '''if (vcImeResetting || connectionGeneration != vcImeGeneration) {
                                vcTraceRejected.incrementAndGet();
                                vcTraceRejectionReason = vcImeResetting ? "reset_in_progress" : "stale_connection_generation";
                                return false;
                            }''', count=6)
    replace(java, '    public void vcResetIme(long requestId) {', '''    public void vcResetIme(long requestId) {
        vcTraceResets.incrementAndGet();''')
    replace(java, '                int action = motion.getActionMasked();', '''                vcTraceHover.incrementAndGet();
                int action = motion.getActionMasked();''')
    bridge = adapter / 'src/ime_bridge.rs'
    replace(bridge, '                            if let Some(request_id) = matching {', '''                            if matching.is_some() {
                                vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::RESET_MATCHED);
                            } else {
                                vectorcraft_engine::android_typing_trace::bump(&vectorcraft_engine::android_typing_trace::RESET_UNMATCHED);
                            }
                            if let Some(request_id) = matching {''')
    print('PASS: Android.11 aggregate typing trace and runtime diagnostic title staged; typing cause remains unconfirmed')

if __name__ == '__main__':
    patch(Path(sys.argv[1]))
