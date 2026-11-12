#!/usr/bin/env python3
"""Exercise the builder's actual diagnostic for custom icons outside app source."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys


def main():
    source = Path(sys.argv[1]).read_text()
    statements = [line for line in source.splitlines()
                  if line.startswith('print(f"  Icon: ')]
    if len(statements) != 1:
        raise SystemExit("Expected one generated-launcher icon diagnostic")
    statement = compile(statements[0], "<builder icon diagnostic>", "exec")
    cases = [
        (Path("source/filmcraft"), Path("source/filmcraft/icon.png"), "icon.png"),
        (Path("source/filmcraft"), Path("/ci/suite/assets/filmcraft/fc.png"),
         "/ci/suite/assets/filmcraft/fc.png"),
        (Path("/ci/source/filmcraft"), Path("/ci/suite/assets/fc.png"),
         "/ci/suite/assets/fc.png"),
        (Path("source/filmcraft"), Path("source/filmcraft-extra/icon.png"),
         "source/filmcraft-extra/icon.png"),
    ]
    for src, icon, expected in cases:
        output = StringIO()
        with redirect_stdout(output):
            exec(statement, {"src": src, "icon": icon})
        assert output.getvalue() == f"  Icon: {expected}\n", output.getvalue()
    print("Builder custom-icon diagnostic: 4 path regression cases passed")


if __name__ == "__main__":
    main()
