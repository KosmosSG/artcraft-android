class FontScanBudgetTest {
    public static void main(String[] args) {
        FontScanBudget budget = new FontScanBudget();
        if (FontScanBudget.LIMIT != 4294967296L) throw new AssertionError("32-bit overflow");
        for (int i = 0; i < 65535; i++) {
            int n = budget.nextRead(65536);
            if (n != 65536) throw new AssertionError("Premature limit");
            budget.record(n);
        }
        budget.record(65530);
        if (budget.nextRead(65536) != 6) throw new AssertionError("Read exceeds remaining budget");
        budget.record(6);
        if (budget.used() != FontScanBudget.LIMIT || budget.nextRead(65536) != 0) throw new AssertionError("Wrong exact limit");
        try { budget.record(1); throw new AssertionError("Overrun allowed"); }
        catch (IllegalArgumentException expected) { }
        try { new FontScanBudget().record(-1); throw new AssertionError("Negative count allowed"); }
        catch (IllegalArgumentException expected) { }
        System.out.println("PASS: 4 GiB arithmetic, bounded reads, exact exhaustion, overrun and negative counts");
    }
}
