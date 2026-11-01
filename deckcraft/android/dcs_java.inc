    private final java.util.concurrent.atomic.AtomicInteger dkDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean dkDialogActive;
    public int dkUnsavedDialog(boolean active) {
        // Only one pending action is stored. No held-key set is retained
        // across dialog generations (Android may omit KEY_UP after dismissal).
        boolean justOpened = active && !dkDialogActive;
        dkDialogActive = active;
        if (justOpened) {
            // Match WordCraft: recover hardware-keyboard focus from the editor.
            runOnUiThread(() -> {
                android.view.Window window = getWindow();
                if (window != null && window.getDecorView() != null) {
                    window.getDecorView().setFocusableInTouchMode(true);
                    window.getDecorView().requestFocus();
                }
            });
            android.util.Log.i("DeckCraftDCS", "modal_focus_requested");
        }
        // Match WordCraft: do not drain a pending action when dismissing.
        if (!active) return 0;
        return dkDialogAction.getAndSet(0);
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && dkDialogActive
                && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {
            final int code = event.getKeyCode();
            final int shortcut = code == android.view.KeyEvent.KEYCODE_D ? 1
                    : code == android.view.KeyEvent.KEYCODE_C ? 2
                    : code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;
            if (shortcut != 0 && event.hasNoModifiers()) {
                // Consume both DOWN and UP while the dialog is active.
                // Only the first DOWN is an action, never a key repeat.
                if (event.getAction() == android.view.KeyEvent.ACTION_DOWN
                        && event.getRepeatCount() == 0) {
                    dkDialogAction.compareAndSet(0, shortcut);
                }
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }
