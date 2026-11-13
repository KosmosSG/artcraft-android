"""Final staged contract checks; runtime wheel behavior is tested by Rust in CI."""
from pathlib import Path
import sys

def verify(root):
    a=root/'adapters/vectorcraft'
    host=(a/'src/lib.rs').read_text()
    wheel=(a/'src/stylus_wheel.rs').read_text()
    java=(a/'java/com/artcraft/vectorcraft/VectorCraftActivity.java').read_text()
    canvas=(root/'source/vectorcraft/crates/ui-egui/src/canvas/input.rs').read_text()
    assert 'version = "0.24.1"' in (root/'source/vectorcraft/Cargo.toml').read_text()
    assert wheel.count('fn paint_wheel(')==1
    assert wheel.count('self.paint_wheel(ui, rect, scale, highlighted);')==2
    assert 'num_columns(2)' in wheel and '.width(236.0)' in wheel
    assert 'format!("Slot {}", slot + 1)' in wheel
    assert 'fn external_preview(&self, ctx: &Context)' in wheel
    assert 'let width = screen.width().min(450.0).max(120.0)' in wheel
    assert 'if !isolated { retained.push(egui::Event::PointerMoved(pos)); }' in wheel
    assert 'vc-wheel-input-owned' in canvas and 'tool_frame_moves(ui, app, false)' in canvas
    assert canvas.index('vc-wheel-input-owned') < canvas.index('wheel_view(app, ui, resp, rect)')
    assert 'self.stylus_wheel.capture(ctx, raw, wheel_blocked);' in host
    assert 'wheel_consumed_events=' in host and 'canvas_input_frames=' in host
    assert 'self.persist_now();' in host[host.index('fn on_exit('):]
    assert host.index('if vc_quit_after_native.load(Ordering::Acquire)') > host.index('let result = eframe::run_native(')
    destroy=java[java.index('    protected void onDestroy() {'):java.index('    protected void onNewIntent(')]
    assert destroy.index('super.onDestroy();') < destroy.index('android.os.Process.killProcess(')
    assert 'if (vcConfirmedNativeQuit && !isChangingConfigurations())' in destroy
    assert java.count('vcConfirmedNativeQuit = true;')==1
    assert 'Thread.sleep(' not in destroy and '.join(' not in destroy
    assert 'vcImeFocusEpoch.incrementAndGet()' in destroy
    assert 'vcImeNeedsRebind = true;' in destroy
    assert 'vcImeFocusEpoch.get() != focusToken' in java
    assert 'vcObserveFirstBuffer' in java and 'postOnAnimation' in java
    assert 'postDelayed(this::dismissStartupCover, 120)' not in java
    assert 'com.artcraft.vectorcraft' in (a/'Cargo.toml').read_text()
    print('PASS: final wheel renderer, alignment, input isolation, fresh-process quit and preserved IME contracts')

if __name__=='__main__': verify(Path(sys.argv[1]))
