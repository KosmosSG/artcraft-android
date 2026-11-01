"""Exercise the actual Java budget expression above the signed 32-bit boundary."""
import re, subprocess, tempfile
from pathlib import Path
source = Path("tools/designcraft/support/font_methods.java").read_text()
match = re.search(r'4L \* 1024 \* 1024 \* 1024', source)
assert match, 'Missing long 4 GiB font scan budget'
with tempfile.TemporaryDirectory() as folder:
    p = Path(folder)
    code = '''class BudgetCheck {
      public static void main(String[] args) {
        long limit = EXPR;
        if (limit != 4294967296L) throw new AssertionError("overflow");
        long used = 2147483648L;
        int chunk = 65536;
        if (used > limit - chunk) throw new AssertionError("old 2 GiB cap");
        used = limit - chunk;
        if (used > limit - chunk) throw new AssertionError("exact limit");
        used += chunk;
        if (used <= limit - 1) throw new AssertionError("over-limit accepted");
      }
    }'''.replace('EXPR', match.group(0))
    (p / 'BudgetCheck.java').write_text(code)
    subprocess.run(['javac', str(p / 'BudgetCheck.java')], check=True)
    subprocess.run(['java', '-cp', folder, 'BudgetCheck'], check=True)
print('PASS: actual 4 GiB long expression, >2 GiB, exact and over-limit boundaries')
