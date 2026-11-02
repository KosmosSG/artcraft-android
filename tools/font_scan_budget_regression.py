"""FilmCraft 4 GiB font-scan boundary and source integration checks."""
import re
import subprocess
import tempfile
from pathlib import Path

source = Path("tools/filmcraft/FilmCraftActivity.features.java.inc").read_text()
match = re.search(r"4L\s*\*\s*1024\s*\*\s*1024\s*\*\s*1024", source)
assert match, "Missing 64-bit 4 GiB scan budget"
assert re.search(r"long\[\]\s+scanBytes\s*=\s*\{0\}", source), "Scan budget accumulator must be long"
assert "scanBytes[0] > 4L * 1024 * 1024 * 1024 - n" in source, "Missing overflow-safe pre-write budget check"
assert "scanBytes[0] += n;" in source, "Missing per-chunk accounting"
assert "scanBytes[0] < 4L * 1024 * 1024 * 1024" in source, "Traversal must stop at budget"
assert "FC_SCAN_MAX_FONT_FILES = 5000" in source, "5,000-file scan limit missing"
assert "FC_SCAN_MAX_FOLDERS = 2048" in source, "2,048-folder traversal limit missing"
assert source.count("accepted + skipped < FC_SCAN_MAX_FONT_FILES") == 2, "File-count guards differ"
assert "folders < FC_SCAN_MAX_FOLDERS" in source, "Folder-count guard removed"
rust = Path("tools/filmcraft/filmcraft_features.rs").read_text()
assert "if index >= 5000 { break; }" in rust, "Native cache cap is stale"
assert "paths.iter().take(5000)" in rust, "Native registration handoff is truncated"
assert "for _ in 0..24" in rust, "Bounded per-frame registration is missing"
assert "self.register_pending_fonts(ctx);" in rust, "Registration queue is not drained"
assert "5,000-file limit reached" in source, "No file-cap feedback"
assert "2,048-folder limit reached" in source, "No folder-cap feedback"
assert "getPersistedUriPermissions()" in source, "Persisted SAF grant check removed"

with tempfile.TemporaryDirectory() as folder:
    p = Path(folder)
    code = """class BudgetCheck {
      public static void main(String[] args) {
        long limit = EXPR;
        if (limit != 4294967296L) throw new AssertionError("overflow");
        long used = 2147483648L;
        int chunk = 65536;
        if (used > limit - chunk) throw new AssertionError("old 2 GiB cap");
        used = limit - chunk;
        if (used > limit - chunk) throw new AssertionError("exact limit");
        used += chunk;
        if (used != limit) throw new AssertionError("exact budget accounting");
        if (!(used > limit - chunk)) throw new AssertionError("over-limit accepted");
      }
    }""".replace("EXPR", match.group(0))
    (p / "BudgetCheck.java").write_text(code)
    subprocess.run(["javac", str(p / "BudgetCheck.java")], check=True)
    subprocess.run(["java", "-cp", folder, "BudgetCheck"], check=True)
print("PASS: FilmCraft 4 GiB budget, 5,000-file recursive SAF scans, and bounded native registration")
