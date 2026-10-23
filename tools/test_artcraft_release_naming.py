#!/usr/bin/env python3
"""No APK is published by these tests; all 13 ArtCraft app IDs are covered."""
import unittest

from artcraft_release_naming import apps, release_identity, verify_release

APP_IDS = {
    "photocraft", "vectorcraft", "designcraft", "filmcraft", "pdfcraft",
    "wordcraft", "deckcraft", "effectcraft", "lightcraft", "soundcraft",
    "cadcraft", "figcraft", "gridcraft",
}


class ReleaseNamingTest(unittest.TestCase):
    def test_all_suite_apps_registered(self):
        self.assertEqual(set(apps()), APP_IDS)

    def test_each_resolved_app_uses_upstream_and_android_revision(self):
        for app, metadata in apps().items():
            if "/" in metadata["display_name"]:
                with self.assertRaises(ValueError):
                    release_identity(app, "v1.2.3", 1)
                continue
            with self.subTest(app=app):
                identity = release_identity(app, "v1.2.3", 2)
                self.assertEqual(identity["versionName"], "1.2.3-android.2")
                self.assertEqual(identity["tag"], f"{app}-v1.2.3-android.2")
                self.assertEqual(identity["apk"],
                                 f'{metadata["display_name"]}-v1.2.3-android.2-arm64-v8a.apk')
                self.assertEqual(identity["title"],
                                 f'{metadata["display_name"]} v1.2.3-android.2')
                self.assertEqual(verify_release(
                    app, "1.2.3", 2, version_name=identity["versionName"],
                    tag=identity["tag"], apk=identity["apk"], title=identity["title"],
                    previous_code=100, new_code=101), identity)

    def test_android_only_change_increments_revision_not_upstream_patch(self):
        i = release_identity("pdfcraft", "v0.12.0", 2)
        self.assertEqual(i["tag"], "pdfcraft-v0.12.0-android.2")
        self.assertEqual(i["apk"], "PDFCraft-v0.12.0-android.2-arm64-v8a.apk")

    def test_existing_photo_and_vector_naming(self):
        self.assertEqual(release_identity("photocraft", "v0.12.0", 1)["tag"],
                         "photocraft-v0.12.0-android.1")
        self.assertEqual(release_identity("vectorcraft", "v0.14.0", 2)["tag"],
                         "vectorcraft-v0.14.0-android.2")

    def test_upstream_bump_resets_android_revision(self):
        self.assertEqual(release_identity("lightcraft", "0.11.1", 1)["versionName"],
                         "0.11.1-android.1")

    def test_invalid_upstream_or_revision(self):
        for upstream in ("0.12.0-android.1", "v0.12", "v0.12.0-beta", "v0.012.0", "../0.12.0"):
            with self.subTest(upstream=upstream), self.assertRaises(ValueError):
                release_identity("pdfcraft", upstream, 1)
        for revision in (0, -1, 1.2, True):
            with self.assertRaises(ValueError):
                release_identity("pdfcraft", "0.12.0", revision)

    def test_reject_wrong_apk_tag_and_downgrade(self):
        i = release_identity("deckcraft", "0.9.0", 1)
        for wrong in (
            {"tag": "deckcraft-v0.9.1-android.1"},
            {"apk": "DeckCraft-v0.9.0-arm64-release.apk"},
            {"version_name": "0.9.1-android.1"},
        ):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                verify_release("deckcraft", "0.9.0", 1,
                               version_name=wrong.get("version_name", i["versionName"]),
                               tag=wrong.get("tag", i["tag"]),
                               apk=wrong.get("apk", i["apk"]))
        with self.assertRaises(ValueError):
            verify_release("deckcraft", "0.9.0", 1,
                           version_name=i["versionName"], tag=i["tag"], apk=i["apk"],
                           previous_code=100, new_code=100)


if __name__ == "__main__":
    unittest.main()
