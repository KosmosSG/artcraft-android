import java.util.HashMap;

/** De-duplicate routes without assuming the first observed DOWN has repeat=0. */
final class PcHardwareKeyGate {
    private final HashMap<Long, Long> pressed = new HashMap<>();
    private long lastTime = -1;
    private long lastKey = -1;
    private int lastAction = -1;

    synchronized boolean accept(int code, int action, int repeat, long time, long downTime, int device) {
        if (action != 0 && action != 1) return false;
        long key = ((long) device << 32) | (code & 0xffffffffL);
        if (time == lastTime && key == lastKey && action == lastAction) return false;
        lastTime = time;
        lastKey = key;
        lastAction = action;
        Long prior = pressed.get(key);
        if (action == 0) {
            if (prior != null && prior.longValue() == downTime) return false;
            pressed.put(key, downTime);
            return true;
        }
        if (prior != null && prior.longValue() > downTime) return false;
        pressed.remove(key);
        return true; // An orphan release still repairs downstream held-key state.
    }

    synchronized void clear() {
        pressed.clear();
        lastTime = -1;
        lastKey = -1;
        lastAction = -1;
    }
}
