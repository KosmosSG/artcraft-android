    private final java.util.concurrent.atomic.AtomicInteger dkDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean dkDialogActive;
    private final java.util.HashSet<Integer> dkDialogKeys = new java.util.HashSet<>();
    public int dkUnsavedDialog(boolean active) {
        // A dialog can close before Android delivers its matching KEY_UP.
        // Reset held-key tracking on either modal boundary so D/C/S work
        // again on the next opening. Coordinate with dispatchKeyEvent.
        synchronized (dkDialogKeys) {
            if (dkDialogActive != active) {
                dkDialogKeys.clear();
                // Clear obsolete actions only when dismissing. An opening
                // may already have received a hardware key before the first frame.
                if (!active) dkDialogAction.set(0);
            }
            if (dkDialogActive != active) android.util.Log.i("DeckCraftDCS", "modal_active=" + active);\n            dkDialogActive = active;
            int action = dkDialogAction.getAndSet(0);
            return active ? action : 0;
        }
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {
            int code = event.getKeyCode();\n            if (code == android.view.KeyEvent.KEYCODE_D || code == android.view.KeyEvent.KEYCODE_C || code == android.view.KeyEvent.KEYCODE_S) {\n                android.util.Log.i("DeckCraftDCS", "key=" + code + " event=" + event.getAction() + " active=" + dkDialogActive + " focus=" + (getCurrentFocus() == null ? "none" : getCurrentFocus().getClass().getSimpleName()));\n            }
            synchronized (dkDialogKeys) {
                if (dkDialogKeys.contains(code)) {
                    if (event.getAction() == android.view.KeyEvent.ACTION_UP) dkDialogKeys.remove(code);
                    return true;
                }
                int action = code == android.view.KeyEvent.KEYCODE_D ? 1 : code == android.view.KeyEvent.KEYCODE_C ? 2 : code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;
                if (dkDialogActive && action != 0 && event.hasNoModifiers()
                        && event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                    dkDialogKeys.add(code);
                    if (event.getRepeatCount() == 0) dkDialogAction.compareAndSet(0, action);
                    return true;
                }
            }
        }

        return super.dispatchKeyEvent(event);
    }
