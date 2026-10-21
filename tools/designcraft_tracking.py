"""Read-only official release tracking. Never edits a branch, key or release."""
import json
import re
from urllib.request import Request, urlopen

OFFICIAL = 'https://api.github.com/repos/storytold/designcraft'
PIN = '15a2f3c8c88ae2e011e5912149ac67460ea6d949'


def read(url):
    with urlopen(Request(url, headers={'User-Agent': 'DesignCraft-Android-Upstream-Report', 'Accept': 'application/vnd.github+json'}), timeout=20) as response:
        body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise ValueError('Official response exceeds size limit')
        return json.loads(body)


def report():
    release = read(OFFICIAL + '/releases/latest')
    tag = release['tag_name']
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('Stable official semver release required')
    obj = read(OFFICIAL + '/git/ref/tags/' + tag)['object']
    for _ in range(8):
        if obj['type'] == 'commit':
            break
        if obj['type'] != 'tag' or not re.fullmatch(r'[0-9a-f]{40}', obj['sha']):
            raise ValueError('Unexpected official tag object')
        obj = read(OFFICIAL + '/git/tags/' + obj['sha'])['object']
    if obj['type'] != 'commit' or not re.fullmatch(r'[0-9a-f]{40}', obj['sha']):
        raise ValueError('Cannot resolve an official commit')
    return {'official_repository': 'storytold/designcraft', 'tag': tag, 'commit': obj['sha'],
            'android_source_pin': PIN, 'review_required': obj['sha'] != PIN,
            'automatic_build_or_publish': False,
            'release_url': 'https://github.com/storytold/designcraft/releases/tag/' + tag}


if __name__ == '__main__':
    print(json.dumps(report(), indent=2))
