"""Add only the FilmCraft overlay hook to the pinned disposable builder."""
from pathlib import Path
import sys

ANCHOR = '[[ -f "$ANDROID_DIR/Cargo.toml" && -f "$ANDROID_DIR/src/lib.rs" ]] || fail "Android wrapper is incomplete at $ANDROID_DIR. See the build log and adapters/README.md."'
HOOK = '''

# FilmCraft-only features, applied after the pinned GameActivity launcher generation.
if [[ "$APP" == "filmcraft" ]]; then
    python3 "$ROOT/tools/filmcraft/runtime_patch.py" "$ANDROID_DIR" || fail "FilmCraft feature overlay rejected the generated launcher"
fi
'''

def patch(path):
    path = Path(path).resolve()
    if path.name != 'build-common.sh' or path.parent.name != 'lib' or 'filmcraft-builder' not in path.parts:
        raise ValueError('Only the disposable FilmCraft builder may be staged')
    source = path.read_text()
    if source.count(ANCHOR) != 1 or 'tools/filmcraft/runtime_patch.py' in source:
        raise ValueError('Pinned builder hook changed or already staged; inspect before retrying')
    path.write_text(source.replace(ANCHOR, ANCHOR + HOOK, 1))

if __name__ == '__main__':
    patch(sys.argv[1])
