#!/usr/bin/env python3
"""Read-only validation of a PR93 UNSIGNED Linux Lab GitHub Actions artifact ZIP.

No APK is installed, signed, extracted, modified or uploaded. This verifies
artifact member allowlisting, hashes, and build metadata. It does NOT prove
that the APK is unsigned or safe to install; Android SDK checks and the
original-key compatibility gate remain mandatory after owner signing.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

APK_NAME = "PhotoCraft-v0.14.0-android.2-arm64-v8a-UNSIGNED.apk"
FILES = frozenset({
    APK_NAME, "SHA256SUMS.txt", "UNSIGNED-VERIFICATION.json",
    "production-identity-build-proof.json",
})
PUBLIC_CERT = "45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef"
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
MAX_APK_BYTES = 200 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest_stream(stream) -> str:
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()


def unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject ambiguous duplicate JSON keys, including nested metadata objects.

    Python's default json.loads uses last-key-wins; another verifier may
    interpret a conflicting first value (e.g. production_signed=true).
    """
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON metadata key: " + key)
        result[key] = value
    return result


def check(path: Path, expected_source_sha: str, expected_zip_sha256: str | None = None) -> dict:
    require(bool(COMMIT.fullmatch(expected_source_sha)), "Expected source must be a full lowercase Git SHA")
    if expected_zip_sha256 is not None:
        require(bool(SHA.fullmatch(expected_zip_sha256)), "Expected ZIP SHA256 is malformed")
    require(path.is_file() and not path.is_symlink(), "Artifact ZIP must be a regular file")
    if expected_zip_sha256 is not None:
        with path.open("rb") as stream:
            require(digest_stream(stream) == expected_zip_sha256, "GitHub artifact ZIP SHA256 mismatch")
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            require(len(names) == len(FILES) and set(names) == FILES,
                    "Artifact ZIP must contain exactly four allowlisted files, without duplicates")
            for entry in entries:
                require(not entry.is_dir() and not entry.flag_bits & 1,
                        "Directory or encrypted artifact member rejected")
                require(stat.S_IFMT(entry.external_attr >> 16) != stat.S_IFLNK,
                        "Symlink artifact member rejected")
                limit = MAX_APK_BYTES if entry.filename == APK_NAME else MAX_METADATA_BYTES
                require(entry.file_size <= limit, "Artifact member exceeds safe size limit")
                require(entry.compress_size > 0 or entry.file_size == 0,
                        "Invalid compressed artifact member")
            def read_small(name: str) -> bytes:
                with archive.open(name) as member:
                    return member.read(MAX_METADATA_BYTES + 1)
            checksums = read_small("SHA256SUMS.txt").decode("utf-8")
            match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(APK_NAME) + r"\n?", checksums)
            require(match is not None, "SHA256SUMS must identify exactly the unsigned APK")
            with archive.open(APK_NAME) as apk_stream:
                apk_sha = digest_stream(apk_stream)
            require(apk_sha == match.group(1), "Unsigned APK bytes do not match SHA256SUMS")
            verification = json.loads(read_small("UNSIGNED-VERIFICATION.json"),
                                      object_pairs_hook=unique_json_object)
            proof = json.loads(read_small("production-identity-build-proof.json"),
                               object_pairs_hook=unique_json_object)
            require(isinstance(verification, dict) and isinstance(proof, dict),
                    "Artifact metadata must be JSON objects")
            expected = {
                "kind": "UNSIGNED_SIGNING_INPUT_ONLY",
                "installable": False,
                "production_signed": False,
                "source_checkout_verified": True,
                "zip_header_mismatch_absent": True,
                "disposable_signability_test_passed": True,
                "disposable_signed_apk_deleted": True,
                "package": "com.artcraft.photocraft",
                "version_code": 16790005,
                "version_name": "0.14.0-android.2",
                "pr93_ci_commit": expected_source_sha,
                "original_signer_certificate_required": PUBLIC_CERT,
                "apk_sha256": apk_sha,
            }
            for key, value in expected.items():
                require(type(verification.get(key)) is type(value) and verification[key] == value,
                        "Unsigned verification field mismatched: " + key)
            proof_expected = {
                "package": "com.artcraft.photocraft",
                "version_name": "0.14.0-android.2",
                "version_code": 16790005,
                "public_reference_certificate_sha256": PUBLIC_CERT,
                "proof_signer_matches_public": False,
                "non_installable_disposable_build": True,
                "android_arm64": True,
                "public_release_created": False,
            }
            for key, value in proof_expected.items():
                require(type(proof.get(key)) is type(value) and proof[key] == value,
                        "Build proof field mismatched: " + key)
            return {
                "status": "unsigned_artifact_integrity_only",
                "source_sha": expected_source_sha,
                "apk_sha256": apk_sha,
                "apk_name": APK_NAME,
                "warning": "NOT production signed or installation approved. Owner must verify original key and signed candidate separately.",
            }
    except (zipfile.BadZipFile, EOFError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
        raise ValueError("Artifact ZIP or metadata is malformed") from exc


def self_test() -> None:
    sha = "f" * 40
    apk = b"synthetic-unsigned-apk-test-bytes"
    digest = hashlib.sha256(apk).hexdigest()
    verify = {
        "kind": "UNSIGNED_SIGNING_INPUT_ONLY", "installable": False,
        "production_signed": False, "source_checkout_verified": True,
        "zip_header_mismatch_absent": True, "disposable_signability_test_passed": True,
        "disposable_signed_apk_deleted": True, "package": "com.artcraft.photocraft",
        "version_code": 16790005, "version_name": "0.14.0-android.2",
        "pr93_ci_commit": sha, "original_signer_certificate_required": PUBLIC_CERT,
        "apk_sha256": digest,
    }
    proof = {
        "package": "com.artcraft.photocraft", "version_name": "0.14.0-android.2",
        "version_code": 16790005, "public_reference_certificate_sha256": PUBLIC_CERT,
        "proof_signer_matches_public": False, "non_installable_disposable_build": True,
        "android_arm64": True, "public_release_created": False,
    }
    original = {
        APK_NAME: apk,
        "SHA256SUMS.txt": (digest + "  " + APK_NAME + "\n").encode(),
        "UNSIGNED-VERIFICATION.json": json.dumps(verify).encode(),
        "production-identity-build-proof.json": json.dumps(proof).encode(),
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "artifact.zip"
        def write(members):
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for name, content in members:
                    z.writestr(name, content)
        write(original.items())
        with path.open("rb") as stream:
            zip_sha = digest_stream(stream)
        assert check(path, sha, zip_sha)["apk_sha256"] == digest
        bad_cases = [
            list(original.items()) + [("unexpected.apk", b"x")],
            list(original.items()) + [(APK_NAME, apk)],
            [(n, b"tampered" if n == APK_NAME else v) for n, v in original.items()],
            [(n, b"0" * 64 + b"  " + APK_NAME.encode() + b"\n" if n == "SHA256SUMS.txt" else v)
             for n, v in original.items()],
            [(n, json.dumps({**verify, "pr93_ci_commit": "0" * 40}).encode()
              if n == "UNSIGNED-VERIFICATION.json" else v) for n, v in original.items()],
            [(n, json.dumps({**verify, "production_signed": True}).encode()
              if n == "UNSIGNED-VERIFICATION.json" else v) for n, v in original.items()],
            [(n, json.dumps({**proof, "proof_signer_matches_public": True}).encode()
              if n == "production-identity-build-proof.json" else v) for n, v in original.items()],
            [(n, json.dumps({**proof, "version_code": 16790004}).encode()
              if n == "production-identity-build-proof.json" else v) for n, v in original.items()],
            # Last-key-wins json.loads would accept these conflicting first
            # values. Both metadata documents must reject duplicate keys.
            [(n, b'{"production_signed": true, ' + json.dumps(verify)[1:].encode()
              if n == "UNSIGNED-VERIFICATION.json" else v) for n, v in original.items()],
            [(n, b'{"proof_signer_matches_public": true, ' + json.dumps(proof)[1:].encode()
              if n == "production-identity-build-proof.json" else v) for n, v in original.items()],
        ]
        for members in bad_cases:
            write(members)
            try:
                check(path, sha)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted malformed unsigned artifact ZIP")
        write(original.items())
        try:
            check(path, sha, "0" * 64)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted incorrect GitHub ZIP digest")
    print("PASS: unsigned artifact ZIP allowlist, hashes, source, signing metadata and 11 rejection cases")
    print("No APK built, signed, extracted, installed, uploaded or published")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--expected-source-sha")
    parser.add_argument("--expected-zip-sha256")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.zip or not args.expected_source_sha:
        parser.error("--zip and --expected-source-sha are required")
    print(json.dumps(check(args.zip, args.expected_source_sha, args.expected_zip_sha256),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print("STOP: unsigned artifact validation failed: " + str(exc), file=sys.stderr)
        sys.exit(1)
