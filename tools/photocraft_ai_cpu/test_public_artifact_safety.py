#!/usr/bin/env python3
"""Guard PR93 public ARM proof artifacts against accidental disposable APK upload.

Static regression only: no Android build, network, secrets or signing.
The verified branding checker writes an EPHEMERAL APK into icon-verification/.
An old failed proof run mistakenly uploaded that folder as diagnostics.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2] / ".github" / "workflows"
EXPECTED = {
    "photocraft-ai-production-dryrun.yml": (
        "candidate-proof/production-identity-build-proof.json",
    ),
    "photocraft-ai-unsigned-linux-lab.yml": (
        "candidate-proof/production-identity-build-proof.json",
        "candidate-proof/PhotoCraft-v0.14.0-android.2-arm64-v8a-UNSIGNED.apk",
        "candidate-proof/SHA256SUMS.txt",
        "candidate-proof/UNSIGNED-VERIFICATION.json",
    ),
}


def upload_paths(source: str) -> list[tuple[str, ...]]:
    """Parse the small fixed subset of YAML used for upload-artifact steps."""
    steps = re.split(r"(?m)^      - ", source)
    uploads = []
    for step in steps:
        if not re.search(r"(?m)^\s+uses: actions/upload-artifact@v\d+\s*$", step):
            continue
        match = re.search(r"(?m)^          path: (.+)$", step)
        if match is None:
            raise AssertionError("Upload-artifact step has no explicit path")
        value = match.group(1).strip()
        if value == "|":
            paths = []
            for line in step[match.end():].splitlines()[1:]:
                if line.startswith("            "):
                    paths.append(line.strip())
                elif line.strip():
                    break
            uploads.append(tuple(paths))
        else:
            uploads.append((value,))
    return uploads


class PublicArtifactSafetyTests(unittest.TestCase):
    def test_allowlisted_uploads_only(self):
        for filename, expected in EXPECTED.items():
            with self.subTest(workflow=filename):
                source = (ROOT / filename).read_text()
                self.assertEqual(upload_paths(source), [expected])
                self.assertNotIn("PhotoCraft-AI-PR93-Keyboard-Icon-Failure", source)
                self.assertNotIn("Upload build failure diagnostics", source)
                self.assertIn("verify_apk.py . icon-verification", source)
                self.assertIn("rm -rf icon-verification/", source)
                self.assertRegex(
                    source,
                    r"(?s)- name: Always remove disposable key, output APK and verification APK copy"
                    r".*?if: always\(\).*?rm -rf icon-verification/",
                )
                self.assertIn("rm -f output/*.apk", source)
                for path in expected:
                    self.assertTrue(path.startswith("candidate-proof/"))
                    self.assertNotIn("*", path)
                    if path.lower().endswith(".apk"):
                        self.assertTrue(path.endswith("-UNSIGNED.apk"))

    def test_no_failure_diagnostic_uploads(self):
        for filename in EXPECTED:
            with self.subTest(workflow=filename):
                source = (ROOT / filename).read_text()
                self.assertNotRegex(
                    source,
                    r"(?s)uses: actions/upload-artifact@v\d+.*?"
                    r"(?:icon-verification/|logs/|output/)",
                )


if __name__ == "__main__":
    unittest.main()
