    private final java.util.concurrent.atomic.AtomicInteger dcDialogAction = new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean dcDialogActive;
    private final java.util.HashSet<Integer> dcDialogKeys = new java.util.HashSet<>();
    public int dcUnsavedDialog(boolean active) {
        dcDialogActive = active;
        int action = dcDialogAction.getAndSet(0);
        return active ? action : 0;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {
            int code = event.getKeyCode();
            if (dcDialogKeys.contains(code)) {
                if (event.getAction() == android.view.KeyEvent.ACTION_UP) dcDialogKeys.remove(code);
                return true;
            }
            int action = code == android.view.KeyEvent.KEYCODE_D ? 1 : code == android.view.KeyEvent.KEYCODE_C ? 2 : code == android.view.KeyEvent.KEYCODE_S ? 3 : 0;
            if (dcDialogActive && action != 0 && event.hasNoModifiers()
                    && event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                dcDialogKeys.add(code);
                if (event.getRepeatCount() == 0) dcDialogAction.compareAndSet(0, action);
                return true;
            }
        }

        return super.dispatchKeyEvent(event);
    }
