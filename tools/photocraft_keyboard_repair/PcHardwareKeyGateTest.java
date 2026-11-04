public final class PcHardwareKeyGateTest {
    private static void check(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        PcHardwareKeyGate gate = new PcHardwareKeyGate();
        for (int cycle = 0; cycle < 20; cycle++) {
            long t = 1000 + cycle * 100;
            check(gate.accept(111, 0, 1, t, t - 5, 2), "first observed repeat DOWN must reach Esc handler");
            check(!gate.accept(111, 0, 1, t, t - 5, 2), "duplicate pre-IME/Activity route");
            check(!gate.accept(111, 0, 2, t + 1, t - 5, 2), "held repeat must not retrigger");
            check(gate.accept(111, 1, 0, t + 2, t - 5, 2), "release must arrive");
            check(!gate.accept(111, 1, 0, t + 2, t - 5, 2), "duplicate release");
            check(gate.accept(41, 0, 0, t + 3, t + 3, 2), "normal M press");
            check(gate.accept(41, 1, 0, t + 4, t + 3, 2), "normal M release");
        }
        check(gate.accept(111, 0, 0, 4000, 4000, 2), "press before focus loss");
        gate.clear();
        check(gate.accept(111, 0, 1, 4001, 4000, 2), "focus regain must not inherit held state");
        check(gate.accept(111, 0, 0, 5000, 5000, 2), "new press with missing old release");
        check(!gate.accept(111, 1, 0, 5001, 4000, 2), "late old release must not release new press");
        check(gate.accept(111, 1, 0, 5002, 5000, 2), "current release");
        check(gate.accept(50, 1, 0, 6000, 6000, 2), "orphan release repairs native state");
        System.out.println("PASS: 20 Escape/M cycles, first-observed repeats, duplicate routes, focus reset, stale releases");
    }
}
