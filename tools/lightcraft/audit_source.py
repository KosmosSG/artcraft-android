"""Read-only LightCraft source/reference preflight. This does not compile an APK."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_checkout(root, expected):
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != expected:
        raise ValueError('Checkout is not the reviewed immutable commit')
    if subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--']).returncode:
        raise ValueError('Tracked source differs from the pinned checkout')


def check_files(root, files):
    for path, expected in files.items():
        if digest(root / path) != expected:
            raise ValueError(f'Reviewed API/license file differs: {path}')


def audit(source, builder, reference, suite, lock):
    for root, name in ((source, 'source'), (builder, 'builder'), (reference, 'android_reference')):
        check_checkout(root, lock[name]['commit'])
        check_files(root, lock[name]['files'])
    cargo = tomllib.loads((source / 'Cargo.toml').read_text())
    if cargo['workspace']['package']['version'] != lock['official_version']:
        raise ValueError('Official source version changed')
    if digest(suite / lock['icon']['path']) != lock['icon']['sha256']:
        raise ValueError('Approved original Lc artwork differs')
    # Guard the actual reference recipe, not a new generic Android shell.
    script = (builder / 'lib/build-common.sh').read_text()
    recipe = script.split('    "lightcraft": {', 2)[-1].split('    "cadcraft": {', 1)[0]
    required = ('LightCraftActivity', 'fn saf_write_and_commit(', 'std::thread::spawn',
                'PickKind::Files', 'PickKind::Save', 'picker: Some(', 'write: Some(')
    if not all(anchor in recipe for anchor in required):
        raise ValueError('Reviewed asynchronous SAF/export recipe needs review')
    ui = (source / 'crates/ui-egui/src/lib.rs').read_text()
    for anchor in ('pub fn new(mut session: Session, services: Services)',
                   'pub fn logic(&mut self, ctx: &egui::Context)',
                   'pub fn ui(&mut self, ui: &mut egui::Ui)', 'pub write_shared:'):
        if anchor not in ui:
            raise ValueError('LightCraft host API differs: ' + anchor)
    return {'status': 'read-only source preflight passed; not an Android compile',
            'source_commit': lock['source']['commit'],
            'builder_commit': lock['builder']['commit'],
            'android_reference_commit': lock['android_reference']['commit'],
            'official_version': lock['official_version'],
            'approved_icon_sha256': lock['icon']['sha256'],
            'production_signing': 'unproven; no key generated or reused',
            'apk_tested': False, 'device_tested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('source', 'builder', 'reference', 'suite'):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    lock = json.loads(Path(__file__).with_name('source-lock.json').read_text())
    print(json.dumps(audit(args.source, args.builder, args.reference, args.suite, lock), indent=2))
