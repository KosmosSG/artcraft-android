"""Offline update-filter regression tests. No release is represented as signed."""

import unittest
from update_policy import preliminary_candidates, parse_tag, parse_version


def release(tag, apk=None, *, draft=False, prerelease=False, assets=None):
    if assets is None:
        if apk is None:
            parts = tag.removeprefix("effectcraft-v")
            apk = f"EffectCraft-v{parts.split('-android.', 1)[0]}-arm64-release.apk"
        assets = [{"name": apk,
                   "browser_download_url": f"https://github.com/KosmosSG/artcraft-android/releases/download/{tag}/{apk}"}]
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease, "assets": assets}


class UpdatePolicyTest(unittest.TestCase):
    def test_parse_android_versions_only(self):
        self.assertEqual(parse_version("0.13.0-android.1"), (0,13,0,1))
        self.assertEqual(parse_tag("effectcraft-v0.13.0-android.2"), (0,13,0,2))
        for bad in ("0.13.0", "0.13.0-android.0", "photocraft-v0.13.0-android.1",
                    "effectcraft-v0.13.0", "0.13.0-android.1.apk", "0.13.0-android.-1"):
            self.assertIsNone(parse_version(bad))
        self.assertIsNone(parse_tag("effectcraft-v0.13.0"))

    def test_newer_official_app_releases_only(self):
        releases = [
            release("effectcraft-v0.13.0-android.2"),
            release("effectcraft-v0.13.0-android.1"),
            release("effectcraft-v0.14.0-android.1"),
            release("photocraft-v0.20.0-android.1"),
            release("effectcraft-v0.999.0-android.1", draft=True),
            release("effectcraft-v0.888.0-android.1", prerelease=True),
            release("effectcraft-v0.555.0-android.1", apk="not-effectcraft.apk"),
            release("v0.15.0", apk="effectcraft-0.15.0.apk"),
        ]
        result = preliminary_candidates(releases, "0.13.0-android.1")
        self.assertEqual([x.version_name for x in result],
                         ["0.14.0-android.1", "0.13.0-android.2"])
        self.assertTrue(all(x.verification_required for x in result))

    def test_bad_asset_and_duplicate_release_rejected(self):
        tag = "effectcraft-v0.13.0-android.3"
        name = "EffectCraft-v0.13.0-arm64-release.apk"
        bad = release(tag, assets=[
            {"name": name, "browser_download_url": f"https://attacker.example/{name}"}
        ])
        self.assertEqual(preliminary_candidates([bad], "0.13.0-android.1"), [])
        correct = release(tag)
        self.assertEqual(len(preliminary_candidates([correct, correct], "0.13.0-android.1")), 1)
        self.assertEqual(preliminary_candidates([release(tag, assets=correct["assets"]*2)],
                                                "0.13.0-android.1"), [])

    def test_installed_identity_unknown_fails_closed(self):
        self.assertEqual(preliminary_candidates([release("effectcraft-v0.13.0-android.2")], "0.13.0"), [])


if __name__ == "__main__":
    unittest.main()
