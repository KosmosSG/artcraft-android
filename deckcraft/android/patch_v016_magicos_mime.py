#!/usr/bin/env python3
"""DeckCraft Android.3: isolated HONOR MagicOS PowerPoint default-app MIME probe.

The public builder declares modern OOXML presentation MIME types, whereas WordCraft
also declares the legacy Word type. HONOR may query the old PowerPoint type when
building its system-wide 'PowerPoint document' default-app list.

Add a separate, VIEW-only legacy-MIME intent filter to the disposable DeckCraft
builder checkout. Do not advertise .ppt by extension, change the document importer,
alter SHARE/EDIT actions, or modify any other ArtCraft application.

This is a hypothesis for owner device testing, NOT a promise of binary .ppt support.
Never merge or publish based only on this manifest probe.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: patch_v016_magicos_mime.py <disposable-builder-dir>")
root = Path(sys.argv[1])
path = root / "lib" / "file_associations.py"
src = path.read_text(encoding="utf-8")
old = """        # Let a browser hand a remote document straight to the app too (content:// links already
        # match above through their MIME type)."""
new = """        # HONOR MagicOS compatibility probe, DeckCraft only: some OEM default-app
        # registries may query the legacy PowerPoint MIME type rather than the
        # OOXML PPTX type. Keep this as a separate VIEW-only filter so the modern
        # PPTX/POTX/PPSX associations, ACTION_EDIT, and SEND filters stay identical.
        # Do not add a .ppt extension or claim unsupported binary PPT import.
        if app == "deckcraft":
            filters.append(
                '{ actions = ["android.intent.action.VIEW"], categories = ["android.intent.category.DEFAULT"], data = [{ mime_type = "application/vnd.ms-powerpoint" }] }'
            )
        # Let a browser hand a remote document straight to the app too (content:// links already
        # match above through their MIME type)."""
assert src.count(old) == 1, "Pinned builder association insertion point changed; abort"
assert 'application/vnd.ms-powerpoint' not in src, "Legacy PowerPoint alias already exists; abort"
path.write_text(src.replace(old, new, 1), encoding="utf-8")
print("PASS: isolated DeckCraft VIEW-only legacy PowerPoint MIME probe installed in builder")
