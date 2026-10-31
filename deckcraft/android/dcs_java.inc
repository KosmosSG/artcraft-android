    private final java.util.concurrent.atomic.AtomicInteger dkDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean dkDialogActive;
    private final java.util.HashSet<Integer> dkDialogKeys = new java.util.HashSet<>();
    public int dkUnsavedDialog(boolean active) {
        dkDialogActive = active;
        int action = dkDialogAction.getAndSet(0);
        return active ? action : 0;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {
            int code = event.getKeyCode();
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

        return super.dispatchKeyEvent(event);
    }
