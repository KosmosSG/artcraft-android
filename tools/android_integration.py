#!/usr/bin/env python3
"""Pinned, isolated integration checks. Never authorizes a release."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def config():
    return json.loads((ROOT / 'configs/android-integration.json').read_text())


def check_pin(app, tag):
    expected = config()['apps'][app]['upstream_tag']
    if tag != expected:
        raise ValueError(f'{app}: expected reviewed upstream {expected}, got {tag}')


def verify_checkout(app, checkout):
    expected = config()['apps'][app]['upstream_commit']
    actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected:
        raise ValueError(f'{app}: source commit mismatch: {actual} != {expected}')


def promotion_check():
    pending = [app for app, row in config()['apps'].items()
               if not all(row.get(key) is True for key in
                          ('preservation_verified', 'artifact_verified', 'device_verified'))]
    if pending or config()['production_ready'] is not True:
        raise ValueError('Release blocked: baseline preservation / APK / device evidence pending: ' + ', '.join(pending))


def validate():
    import re
    from suite_feature_parity import APP_IDS
    data = config()
    assert set(data['apps']) == set(APP_IDS)
    assert re.fullmatch('[0-9a-f]{40}', data['android_reference']['commit'])
    for app, row in data['apps'].items():
        assert row['upstream_repository'] == 'storytold/' + app
        assert re.fullmatch(r'v\d+\.\d+\.\d+', row['upstream_tag'])
        assert re.fullmatch('[0-9a-f]{40}', row['upstream_commit'])
        if row['release_baseline_tag']:
            assert row['release_baseline_tag'].startswith(app + '-v')
            assert re.fullmatch('[0-9a-f]{40}', row['release_baseline_commit'])
    print('PASS: 13 official upstream pins and released source baselines recorded; no runtime verification claimed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['validate', 'check-pin', 'verify-checkout', 'promotion-check'])
    p.add_argument('app', nargs='?')
    p.add_argument('value', nargs='?')
    a = p.parse_args()
    if a.command == 'validate':
        validate()
    elif a.command == 'promotion-check':
        promotion_check()
    elif a.command == 'check-pin':
        check_pin(a.app, a.value)
    else:
        verify_checkout(a.app, a.value)
