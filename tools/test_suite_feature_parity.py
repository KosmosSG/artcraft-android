#!/usr/bin/env python3
"""Contract tests cover all Craft IDs without asserting features are already shipped."""
import copy
import unittest

from suite_feature_parity import APP_IDS, FEATURE_IDS, read_contract, require_release_parity


class SuiteFeatureParityTest(unittest.TestCase):
    def setUp(self):
        self.contract=read_contract()

    def test_every_app_and_requirement_registered(self):
        self.assertEqual(set(self.contract["app_status"]),set(APP_IDS))
        self.assertEqual(set(self.contract["expected_feature_ids"]),set(FEATURE_IDS))
        for app,entry in self.contract["app_status"].items():
            with self.subTest(app=app):
                self.assertEqual(set(entry["features"]),set(FEATURE_IDS))
                self.assertTrue(all(status=="not_verified" for status in entry["features"].values()))
                self.assertIsNone(entry["verified_apk_sha256"])

    def test_native_fonts_persist_and_are_imported_via_scoped_storage(self):
        self.assertEqual(self.contract["font_extensions"],[".ttf",".otf"])
        self.assertIn("app-private persistent storage",self.contract["font_import_method"])
        self.assertIn("read-only",self.contract["shared_font_folder"])
        self.assertIn("nested folders",self.contract["shared_font_folder"])
        self.assertIn("no all-files-access",self.contract["shared_font_folder"])
        self.assertIn("bottom of Type",self.contract["font_menu_location"])

    def test_update_policy_is_app_scoped_and_opt_in(self):
        self.assertIn("OFF",self.contract["update_startup"])
        self.assertIn("published GitHub Releases",self.contract["update_manual"])
        self.assertIn("Help menu",self.contract["update_location"])
        self.assertIn("immediately below About",self.contract["update_location"])
        self.assertIn("no silent install",self.contract["update_integrity"])
        self.assertIn("non-fatal",self.contract["update_unavailable"])
        self.assertIn("android.N",self.contract["name_contract"])

    def test_cannot_claim_release_parity_without_exact_apk_and_device_evidence(self):
        for app in APP_IDS:
            with self.subTest(app=app), self.assertRaises(ValueError):
                require_release_parity(app,"0"*64,contract=self.contract)
        with self.assertRaises(ValueError):
            require_release_parity("wordcraft","not-a-sha",contract=self.contract)
        with self.assertRaises(ValueError):
            require_release_parity("unknown","0"*64,contract=self.contract)

    def test_checked_exact_sha_can_pass_only_when_all_features_are_device_verified(self):
        clone=copy.deepcopy(self.contract)
        verified="1"*64
        clone["app_status"]["wordcraft"]["verified_apk_sha256"]=verified
        for feature in FEATURE_IDS[:-1]:
            clone["app_status"]["wordcraft"]["features"][feature]="device_verified"
        with self.assertRaises(ValueError):
            require_release_parity("wordcraft",verified,contract=clone)
        clone["app_status"]["wordcraft"]["features"][FEATURE_IDS[-1]]="device_verified"
        require_release_parity("wordcraft",verified,contract=clone)
        with self.assertRaises(ValueError):
            require_release_parity("wordcraft","2"*64,contract=clone)


if __name__=="__main__":
    unittest.main()
