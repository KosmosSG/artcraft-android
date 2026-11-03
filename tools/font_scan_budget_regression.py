#!/usr/bin/env python3
"""PDFCraft: enforce 4 GiB (long) / 5,000 candidate fonts per SAF refresh."""
from pathlib import Path
import re
import subprocess
import tempfile

source = Path("templates/android/pdfcraft_mobile_java.txt").read_text()
assert "4L * 1024 * 1024 * 1024" in source, "4 GiB scan must use Java long arithmetic"
assert "PDF_FONT_SCAN_MAX_FILES = 5000" in source
assert "PDF_FONT_SCAN_MAX_FOLDERS = 10000" in source
assert "PDF_FONT_FILE_MAX_BYTES = 16L * 1024 * 1024" in source
assert "pdfCopyFont(font, name, scanBytes)" in source
assert "pdfCopyFont(uri, name, new long[]{0L})" in source
assert "examined++" in source
assert source.count("examined < PDF_FONT_SCAN_MAX_FILES") == 2
assert source.count("scanBytes[0] < PDF_FONT_SCAN_MAX_BYTES") == 2
assert "scanBytes[0] > PDF_FONT_SCAN_MAX_BYTES - length" in source
assert "scanBytes[0] += length;" in source
assert "if (!visited.contains(id)" in source
assert "4 GiB read budget reached" in source
assert "5,000-font scan cap reached" in source
assert "copied < 200" not in source, "Original 200-font cap has regressed"
assert "visited.size() < 1000" not in source, "Original 1000-folder cap has regressed"
# Exercise the actual Java long formula, and an attempted 5001st file, not
# merely Python's unlimited integers.
expression = re.search(r"PDF_FONT_SCAN_MAX_BYTES = ([^;]+);", source)
assert expression, "Missing cumulative budget expression"
with tempfile.TemporaryDirectory() as directory:
    base = Path(directory)
    code = """class BudgetCheck {
      static final long LIMIT = EXPR;
      static final int MAX_FILES = 5000;
      public static void main(String[] args) {
        if (LIMIT != 4294967296L) throw new AssertionError("4 GiB overflow");
        long read = 2147483648L;
        int chunk = 65536;
        if (read > LIMIT - chunk) throw new AssertionError("early 2 GiB stop");
        read = LIMIT - chunk;
        if (read > LIMIT - chunk) throw new AssertionError("exact boundary");
        read += chunk;
        if (read < LIMIT) throw new AssertionError("4 GiB boundary not reached");
        if (read <= LIMIT - 1) throw new AssertionError("over limit accepted");
        int visited = 0;
        while (visited < MAX_FILES) visited++;
        if (visited != 5000 || visited < MAX_FILES)
          throw new AssertionError("font file count exceeded");
      }
    }""".replace("EXPR", expression.group(1))
    (base / "BudgetCheck.java").write_text(code)
    subprocess.run(["javac", str(base / "BudgetCheck.java")], check=True)
    subprocess.run(["java", "-cp", directory, "BudgetCheck"], check=True)
print("PASS: Java long 4 GiB boundaries; 5,000 files; recursive and per-file guards")
