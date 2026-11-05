package com.artcraft.photocraft;

import android.app.Activity;
import android.view.PointerIcon;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;

/** PhotoCraft-only pointer bridge. All view access runs on the Android UI thread. */
final class PcAdaptiveCursor {
    private final Activity activity;
    private String wanted = "TYPE_ARROW";
    private int applied = -1;
    private View surface;
    private boolean queued;
    PcAdaptiveCursor(Activity activity) { this.activity = activity; }
    synchronized void request(String name) {
        if (wanted.equals(name) && applied >= 0) return;
        wanted = name;
        if (queued) return;
        queued = true;
        activity.runOnUiThread(() -> apply());
    }
    synchronized void reset() { surface = null; applied = -1; request(wanted); }
    private View findSurface(View view) {
        if (view instanceof SurfaceView
                || view.getClass().getSimpleName().equals("NativeContentView")) return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = findSurface(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }
    private synchronized void apply() {
        queued = false;
        if (activity.isFinishing() || activity.isDestroyed()) return;
        if (surface == null || !surface.isAttachedToWindow()) {
            surface = findSurface(activity.getWindow().getDecorView());
            applied = -1;
        }
        if (surface == null) return;
        int type;
        try { type = PointerIcon.class.getField(wanted).getInt(null); }
        catch (ReflectiveOperationException error) { type = PointerIcon.TYPE_ARROW; }
        if (applied == type) return;
        surface.setPointerIcon(PointerIcon.getSystemIcon(activity, type));
        applied = type;
    }
}
