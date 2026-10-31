import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import android_integration as integration


class IntegrationTests(unittest.TestCase):
    def test_recorded_pins(self):
        integration.validate()
        for app, row in integration.config()['apps'].items():
            integration.check_pin(app, row['upstream_tag'])
            with self.assertRaises(ValueError):
                integration.check_pin(app, 'main')

    def test_wrong_checkout_is_rejected(self):
        with patch.object(subprocess, 'check_output', return_value='0' * 40):
            with self.assertRaises(ValueError):
                integration.verify_checkout('photocraft', Path('/unused'))

    def test_no_promotion_without_preservation_and_device_evidence(self):
        with self.assertRaises(ValueError):
            integration.promotion_check()

    def test_production_package_fails_before_build(self):
        result = subprocess.run(['bash', 'build.sh', '-photocraft'],
                                cwd=integration.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('release-baseline preservation is pending', result.stderr)


if __name__ == '__main__':
    unittest.main()
