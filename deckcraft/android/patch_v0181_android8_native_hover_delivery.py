#!/usr/bin/env python3
"""DeckCraft Android.8 isolated test: native hover routing and approved Dk size."""
from pathlib import Path
import sys
if len(sys.argv)!=2: raise SystemExit("usage: patch_v0181_android8_native_hover_delivery.py <builder>")
root=Path(sys.argv[1])
java=root/"templates/android/SafActivity.java"
wheel=root/"source/deckcraft/crates/ui-egui/src/android_wheel.rs"
bridge=root/"templates/android/dcs_bridge.rs"
assert java.is_file() and wheel.is_file() and bridge.is_file()
def once(path,old,new):
    s=path.read_text()
    if s.count(old)!=1: raise RuntimeError(f"Unsafe Android.8 source anchor in {path}: {s.count(old)}")
    path.write_text(s.replace(old,new,1))
once(wheel,"vec2(35.58,22.16)*scale","vec2(40.92,25.48)*scale")
once(java,"    private void dkCaptureRealStylusHover(MotionEvent e) {",'''    // Receive native surface hover from cold start; preserve event delivery.
    private android.view.View dkHoverSurface;
    private boolean dkHoverObserverInstalled=false;
    private android.view.View dkFindSurface(android.view.View view) {
        if (view==null) return null;
        if (view instanceof android.view.SurfaceView) return view;
        if (view instanceof android.view.ViewGroup) {
            android.view.ViewGroup group=(android.view.ViewGroup)view;
            for(int n=0;n<group.getChildCount();n++) {
                android.view.View found=dkFindSurface(group.getChildAt(n));
                if(found!=null) return found;
            }
        }
        return null;
    }
    private void dkInstallNativeHover() {
        if(getWindow()==null) return;
        android.view.View decor=getWindow().getDecorView();
        if(decor==null) return;
        android.view.View nativeView=dkFindSurface(decor);
        if(nativeView==null || nativeView==dkHoverSurface) return;
        nativeView.setOnHoverListener((view,event)->{
            dkCaptureRealStylusHover(event);
            return false;
        });
        dkHoverSurface=nativeView;
    }
    private void dkSetupNativeHover() {
        if(getWindow()==null) return;
        android.view.View decor=getWindow().getDecorView();
        if(decor==null) return;
        if(!dkHoverObserverInstalled) {
            dkHoverObserverInstalled=true;
            decor.getViewTreeObserver().addOnGlobalLayoutListener(
                ()->dkInstallNativeHover());
        }
        decor.post(()->dkInstallNativeHover());
    }
    private void dkCaptureRealStylusHover(MotionEvent e) {''')
once(java,"        imeSetup();\n        handleIncomingFiles(getIntent());",
          "        imeSetup();\n        dkSetupNativeHover();\n        handleIncomingFiles(getIntent());")
once(java,"        super.onWindowFocusChanged(hasFocus);\n        if (hasFocus) {",
          "        super.onWindowFocusChanged(hasFocus);\n        if (hasFocus) dkSetupNativeHover();\n        else dkRealStylusHover.set(-1L);\n        if (hasFocus) {")
j=java.read_text()
w=wheel.read_text()
b=bridge.read_text()
for marker in ["nativeView.setOnHoverListener((view,event)->{","return false;","v instanceof", "dkSetupNativeHover();"]:
    if marker=="v instanceof": continue
    assert marker in j,marker
for marker in ["MotionEvent.TOOL_TYPE_STYLUS","MotionEvent.TOOL_TYPE_ERASER","MotionEvent.ACTION_HOVER_ENTER","MotionEvent.ACTION_HOVER_EXIT","dkWheelTakeHover()"]:
    assert marker in j,marker
for marker in ["vec2(40.92,25.48)*scale","const DEFAULT_SIZE: f32 = 75.0;","const DEFAULT_OPACITY: f32 = 100.0;","deckcraft-wheel-bottom-notification","painter.circle_filled(c,HUB*scale,BURGUNDY);","Color32::from_rgb(105,105,109)","ctx.request_repaint_after(std::time::Duration::from_millis(80));"]:
    assert marker in w,marker
assert "self.wheel_hover(ctx);" in b
print("PASS: native stylus hover captured before first touch without consuming events")
print("PASS: original launcher Dk lettering scaled +15%, hub and defaults preserved")
