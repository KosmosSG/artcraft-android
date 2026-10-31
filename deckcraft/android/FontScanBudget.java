final class FontScanBudget {
    static final long LIMIT = 4L * 1024 * 1024 * 1024;
    private long used;
    long used() { return used; }
    int nextRead(int bufferSize) {
        if (bufferSize <= 0) throw new IllegalArgumentException("Invalid buffer size");
        return (int)Math.min((long)bufferSize, LIMIT - used);
    }
    void record(int count) {
        if (count < 0 || (long)count > LIMIT - used) throw new IllegalArgumentException("Scan budget exceeded");
        used += count;
    }
}
