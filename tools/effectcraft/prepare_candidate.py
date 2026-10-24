#!/usr/bin/env python3
"""Patch only a temporary EffectCraft CI checkout; fail on unexpected builder drift."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: prepare_candidate.py <builder-root>")
path = Path(sys.argv[1]).resolve() / "lib/build-common.sh"
source = path.read_text()

def change_once(before, after):
    global source
    if source.count(before) != 1:
        raise SystemExit(f"STOP: inspected EffectCraft builder recipe changed: {before[:65]}")
    source = source.replace(before, after, 1)

change_once(
    '"effectcraft": {"app_type": "EffectcraftApp", "construct": "{app}::new(Session::new())"},',
    '"effectcraft": {"app_type": "EffectcraftApp", "construct": "{app}::new(effectcraft_host::session())"},',
)
change_once(
    '"construct_expr": "EffectcraftApp::new(Session::new())",',
    '"construct_expr": "EffectcraftApp::new(effectcraft_host::session())",',
)
change_once(
    "    java_sources = 'java_sources = \"java\"\\n' if saf else ''",
    """    host_deps = 'effectcraft-host = { path = "../../crates/host" }\\n' if app == "effectcraft" else ""
    java_sources = 'java_sources = "java"\\n' if saf else ''""",
)
change_once("{serde_dep}{rfd_dep}{cpal_dep}", "{serde_dep}{rfd_dep}{cpal_dep}{host_deps}")
change_once(
    '    apk_basename = f"{app}-{app_version}"',
    '''    version_line = f'version = "{app_version}-android.3"' if app == "effectcraft" else "version.workspace = true"
    apk_basename = f"{app}-{app_version}"''',
)
change_once(
    'version.workspace = true\nedition.workspace = true',
    '{version_line}\nedition.workspace = true',
)
change_once("{serde_dep}{rfd_dep}{cpal_dep}{host_deps}", '{serde_dep}{rfd_dep}{cpal_dep}{host_deps}effectcraft-text = {{ path = "../../crates/text" }}\\n')
change_once('[package.metadata.android]\n', '[package.metadata.android]\nversion_code = 16781315\n')
path.write_text(source)
print("PASS: EffectCraft host-wired session and Android revision applied only in temporary CI checkout.")

