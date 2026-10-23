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
features=d.get("required_android_features", {})
assert features.get("policy_doc")=="docs/ARTCRAFT_ANDROID_SUITE_FEATURE_STANDARD.md"
assert Path(features["policy_doc"]).is_file(), "Suite feature standard missing"
for key in ("apply_to_all_apps", "photocraft_reference", "ttf_otf_import_via_saf",
            "optional_saf_shared_font_folder", "manual_android_github_update_check",
            "opt_in_startup_update_check", "visible_nonfloating_update_status",
            "verified_published_app_apk_only", "preserve_installed_package_signer_data",
            "feature_regression_tests_required",
            "device_test_before_claiming_compatibility",
            "automatically_consider_for_future_apps"):
    assert features.get(key) is True, "Required suite feature missing: "+key
naming=d.get("version_naming",{})
assert naming.get("scheme")=="upstream-semver-plus-android-revision-v1", "Unsupported suite naming scheme"
assert naming.get("version_name")=="MAJOR.MINOR.PATCH-android.REVISION"
assert naming.get("release_title")=="DisplayName vMAJOR.MINOR.PATCH-android.REVISION"
assert naming.get("tag")=="appname-vMAJOR.MINOR.PATCH-android.REVISION"
assert naming.get("apk_asset")=="DisplayName-vMAJOR.MINOR.PATCH-android.REVISION-arm64-v8a.apk"
assert naming.get("legacy_releases_immutable") is True, "Never rename old signed release artifacts"
assert naming.get("signing_and_version_codes_unchanged_by_naming") is True
# The PhotoCraft font/update experience is required in every app. This
# read-only suite audit validates the contract but cannot invent verification
# of real production APKs.
from suite_feature_parity import read_contract, APP_IDS, FEATURE_IDS
feature_contract=read_contract()
assert feature_contract['reference_app']=='photocraft'
assert len(feature_contract['app_status'])==len(APP_IDS)==13
assert len(FEATURE_IDS)==11
assert 'update_channel_selection' in FEATURE_IDS

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
