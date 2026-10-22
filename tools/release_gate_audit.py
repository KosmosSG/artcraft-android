"""Read-only ArtCraft Android suite production-release readiness audit.

Fail closed: this workflow only reports readiness; it cannot publish or sign.
"""
import json
from pathlib import Path
import re
import sys
p=Path("configs/release-gates/suite.json")
d=json.loads(p.read_text())
assert d.get("schema_version")==1
assert d.get("public_release_repository")=="KosmosSG/artcraft-android"
assert d.get("enable_unattended_upstream_merges") is False
assert d.get("enable_any_public_release") is False, "Global release switch cannot be enabled without per-app reviewed workflows"
expected=["photocraft","vectorcraft","designcraft","filmcraft","pdfcraft","wordcraft","deckcraft","effectcraft","lightcraft","soundcraft","cadcraft","figcraft","gridcraft"]
apps=d.get("apps",{})
assert sorted(apps)==sorted(expected),"Missing suite app or unreviewed new app"
required=("production_baseline_confirmed","icon_device_verified",
"preserved_all_enhancements","updater_compatible","release_workflow_verified")
reasons=[]
for id in expected:
    item=apps[id]
    if not re.fullmatch("[a-z0-9]+",id):
        raise ValueError("Unsafe app ID")
    cert=item.get("verified_certificate_sha256")
    if cert is not None:
        assert re.fullmatch(r"[a-f0-9]{64}",cert),id+" signer fingerprint"
        assert item.get("private_signing_repository"),id+" private key repository absent"
    missing=[name for name in required if item.get(name) is not True]
    if not item.get("private_signing_repository"): missing.append("own permanent signing repo")
    if not cert:missing.append("verified permanent signing certificate")
    if not item.get("android_package"):missing.append("verified package identifier")
    for key in ("latest_public_approved_apk_sha256","device_tested_sha256"):
        value=item.get(key)
        if value is None:missing.append(key)
        elif not re.fullmatch(r"[a-f0-9]{64}",value):raise ValueError(id+": bad "+key)
    code=item.get("highest_verified_production_version_code")
    if type(code) is not int or code < 1:missing.append("highest verified production versionCode")
    if item.get("public_release_enabled") is True:
        raise SystemExit("STOP: No app may be activated by this read-only manifest; install a distinct, reviewed, signed production publisher: "+id)
    reasons.append((id,sorted(set(missing))))
print("PASS: Suite manifest is complete and fail-closed.")
for id,missing in reasons:
    print(f"{id:13} BLOCKED: {', '.join(missing) if missing else 'Await separate publisher gate and APK validation'}")
print("No app signed, built, published, merged or authorized by this audit.")
