#!/usr/bin/env python3
"""Fail-closed, read-only compatibility gate for a FUTURE PhotoCraft AI APK.

The program reads two already-built Android APK files, uses SDK aapt and
apksigner to verify them, and compares release identity. It NEVER builds,
signs, installs, merges, uploads or publishes an app. The reference must be
the original publicly released PhotoCraft APK, not an arbitrary preview.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

from photocraft_ai_reference_signing import inspect as inspect_apk

PUBLIC_TAG = "photocraft-v0.14.0-android.1"
PUBLIC_VERSION_CODE = 16790004
PUBLIC_SIGNER_SHA256 = (
    "45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef"
)
PUBLIC_PACKAGE = "com.artcraft.photocraft"
MAX_APK_BYTES = 512 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
# Fail closed on common independently distributed model-weight formats.
MODEL_WEIGHT_SUFFIXES = (
    ".onnx", ".pth", ".pt", ".safetensors", ".tflite", ".ort",
    ".ckpt", ".gguf", ".h5", ".hdf5",
)
CANDIDATE_TAG_PATTERN = re.compile(
    r"^photocraft-v(\d+)\.(\d+)\.(\d+)-android\.(\d+)$"
)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_arm64_archive(
    apk: Path, *, max_uncompressed_bytes: int = MAX_UNCOMPRESSED_BYTES
) -> dict[str, object]:
    """Read-only fail-closed ZIP/ABI check on the ACTUAL signed candidate APK.

    APK package/signature identity is verified separately by inspect_apk().
    This catches a validly signed but non-ARM64, corrupt or unexpectedly
    model/key-containing archive before any tablet installation.
    """
    ensure(apk.is_file() and not apk.is_symlink(),
           "Candidate APK must be a regular, non-symlink file")
    ensure(0 < apk.stat().st_size <= MAX_APK_BYTES,
           "Candidate APK exceeds safe input size")
    ensure(max_uncompressed_bytes > 0, "Invalid archive size limit")
    try:
        with zipfile.ZipFile(apk) as archive:
            entries = archive.infolist()
            total_uncompressed = 0
            names = [entry.filename for entry in entries]
            ensure(len(names) == len(set(names)), "Candidate APK has duplicate ZIP entries")
            ensure("AndroidManifest.xml" in names, "Candidate APK is missing AndroidManifest.xml")
            ensure("classes.dex" in names, "Candidate APK is missing primary classes.dex")
            for entry in entries:
                name = entry.filename
                # PurePosixPath normalizes empty and "." segments, hiding
                # ambiguous ZIP names that Android and desktop extractors may
                # interpret differently. Validate raw segments instead.
                parts = name.split("/")
                if entry.is_dir():
                    parts = parts[:-1]
                ensure(bool(parts) and all(part not in ("", ".", "..") for part in parts)
                       and not name.startswith("/") and "\\" not in name,
                       "Candidate APK contains an unsafe or noncanonical ZIP path")
                ensure(not entry.flag_bits & 1, "Candidate APK has an encrypted ZIP entry")
                total_uncompressed += entry.file_size
                ensure(entry.file_size <= MAX_APK_BYTES
                       and total_uncompressed <= max_uncompressed_bytes,
                       "Candidate APK exceeds safe uncompressed ZIP size")
                # A ZIP entry without a trailing slash may still declare a
                # directory, FIFO or device through UNIX type bits. Never
                # accept a special file as AndroidManifest.xml or a native .so.
                mode = stat.S_IFMT(entry.external_attr >> 16)
                allowed_modes = (0, stat.S_IFDIR) if entry.is_dir() else (0, stat.S_IFREG)
                ensure(mode in allowed_modes, "Candidate APK has a non-regular ZIP file")
                ensure(not entry.is_dir() or entry.file_size == 0,
                       "Candidate APK has a nonempty ZIP directory")
                # Identity and a valid ZIP CRC alone do not establish a
                # launchable application. Refuse zero-byte critical payloads.
                if name in ("AndroidManifest.xml", "classes.dex") or (
                    name.startswith("lib/arm64-v8a/") and name.endswith(".so")
                ):
                    ensure(not entry.is_dir() and entry.file_size > 0,
                           "Candidate APK has an empty critical application payload")
                ensure(not name.lower().endswith(
                    (".jks", ".p12", ".keystore") + MODEL_WEIGHT_SUFFIXES),
                    "Candidate APK unexpectedly bundles a key or AI model weight")
            native_libs = [name for name in names if name.startswith("lib/")
                           and name.lower().endswith(".so")]
            ensure(bool(native_libs), "Candidate APK is missing ARM64 native libraries")
            ensure(all(name.startswith("lib/arm64-v8a/") for name in native_libs),
                   "Candidate APK includes a non-ARM64 native library")
            ensure(archive.testzip() is None, "Candidate APK has a corrupt ZIP member")
    except (zipfile.BadZipFile, EOFError, RuntimeError) as exc:
        raise ValueError("Candidate APK ZIP cannot be verified") from exc
    return {"arm64_only": True, "native_library_count": len(native_libs),
            "zip_crc_verified": True, "model_weights_embedded": False}


def release_key(tag: str) -> tuple[int, int, int, int]:
    match = CANDIDATE_TAG_PATTERN.fullmatch(tag)
    ensure(match is not None, "Candidate requires a PhotoCraft-specific Android release tag")
    return tuple(int(group) for group in match.groups())


def check_candidate(
    reference: dict[str, object], candidate: dict[str, object],
    candidate_badging: str,
) -> dict[str, object]:
    """Validate package, certificate, version ordering and launcher identity.

    Both dictionaries MUST come from inspect_apk(), which verifies actual APK
    signatures. Synthetic dictionaries are used by offline unit tests only.
    """
    ensure(reference.get("tag") == PUBLIC_TAG,
           "Reference must be the publicly released PhotoCraft 0.14.0-android.1")
    ensure(reference.get("package") == PUBLIC_PACKAGE,
           "Reference package does not match production PhotoCraft")
    ensure(reference.get("version_code") == PUBLIC_VERSION_CODE,
           "Reference versionCode differs from published PhotoCraft")
    ensure(reference.get("signer_certificate_sha256") == PUBLIC_SIGNER_SHA256,
           "Reference signer certificate differs from published PhotoCraft")
    ensure(candidate.get("package") == PUBLIC_PACKAGE,
           "Candidate package differs: a preview APK cannot update PhotoCraft")
    ensure(candidate.get("signer_certificate_sha256") == PUBLIC_SIGNER_SHA256,
           "Candidate must be signed with the original PhotoCraft production certificate")
    ensure(isinstance(candidate.get("version_code"), int)
           and not isinstance(candidate["version_code"], bool)
           and candidate["version_code"] > PUBLIC_VERSION_CODE,
           "Candidate versionCode must be strictly above the installed public version")
    candidate_tag = candidate.get("tag")
    ensure(isinstance(candidate_tag, str), "Missing candidate Android release tag")
    ensure(release_key(candidate_tag) > release_key(PUBLIC_TAG),
           "Candidate versionName must be newer than the current public release")
    ensure(candidate.get("version_name") == candidate_tag.removeprefix("photocraft-v"),
           "Candidate APK versionName must match the proposed PhotoCraft release tag")
    # Check the independent aapt output against the already signature-verified
    # inspect_apk() result. Previously a stale/contradictory badging string
    # could pass source-level tests despite mismatched version/package fields.
    # The CLI uses one actual APK for both reads, but this extra fail-closed
    # invariant catches tool output corruption and future integration mistakes.
    # A malformed second package record must fail even when the valid record
    # still matches. Counting only regex matches silently ignored such lines.
    raw_package_lines = re.findall(r"^package:", candidate_badging, re.M)
    badges = re.findall(
        r"^package:\s+name='([^']+)'\s+versionCode='([0-9]+)'\s+versionName='([^']+)'",
        candidate_badging, re.M,
    )
    ensure(len(raw_package_lines) == len(badges) == 1,
           "Candidate aapt must report exactly one valid package/version line")
    badge_package, badge_code, badge_version = badges[0]
    ensure(badge_package == candidate["package"]
           and int(badge_code) == candidate["version_code"]
           and badge_version == candidate["version_name"],
           "Candidate aapt package/version disagrees with verified APK identity")
    # Reject malformed/ambiguous duplicate records as well as valid but wrong
    # labels or launchers. This is a read-only release identity check, so
    # unexpected aapt formatting must fail closed rather than be ignored.
    raw_label_lines = re.findall(r"^application-label:", candidate_badging, re.M)
    labels = re.findall(r"^application-label:'([^']*)'\s*$", candidate_badging, re.M)
    ensure(len(raw_label_lines) == 1 and labels == ["PhotoCraft"],
           "Candidate must have exactly one valid PhotoCraft app label")
    raw_launcher_lines = re.findall(r"^launchable-activity:", candidate_badging, re.M)
    launchers = re.findall(r"^launchable-activity:\s+name='([^']+)'", candidate_badging, re.M)
    ensure(len(raw_launcher_lines) == 1
           and launchers == ["com.artcraft.photocraft.PhotoCraftActivity"],
           "Candidate must retain exactly one valid production PhotoCraft launcher")
    return {
        "status": "compatible_public_apk_identity",
        "reference_tag": PUBLIC_TAG,
        "reference_version_code": PUBLIC_VERSION_CODE,
        "candidate_tag": candidate_tag,
        "candidate_version_code": candidate["version_code"],
        "android_package": PUBLIC_PACKAGE,
        "certificate_sha256": PUBLIC_SIGNER_SHA256,
        "candidate_apk_sha256": candidate.get("apk_sha256"),
        "caveats": [
            "Identity verification is not owner approval to publish.",
            "Actual in-place update/data preservation must be tested on device.",
            "Possession/availability of the production signing key is not established.",
            "AI model weight rights, runtime lifecycle and rollback remain separate release gates.",
        ],
    }


def self_test() -> None:
    baseline = {
        "tag": PUBLIC_TAG, "package": PUBLIC_PACKAGE,
        "version_code": PUBLIC_VERSION_CODE,
        "version_name": "0.14.0-android.1",
        "signer_certificate_sha256": PUBLIC_SIGNER_SHA256,
    }
    new = {
        "tag": "photocraft-v0.14.0-android.2",
        "package": PUBLIC_PACKAGE, "version_code": PUBLIC_VERSION_CODE + 1,
        "version_name": "0.14.0-android.2",
        "signer_certificate_sha256": PUBLIC_SIGNER_SHA256,
        "apk_sha256": "a" * 64,
    }
    normal = (
        "package: name='com.artcraft.photocraft' versionCode='16790005' "
        "versionName='0.14.0-android.2'\n"
        "application-label:'PhotoCraft'\n"
        "launchable-activity: name='com.artcraft.photocraft.PhotoCraftActivity' "
        "label='PhotoCraft'\n"
    )
    assert check_candidate(baseline, new, normal)["candidate_version_code"] == PUBLIC_VERSION_CODE + 1
    upgraded = {**new, "tag": "photocraft-v0.14.1-android.1", "version_name": "0.14.1-android.1"}
    upgraded_badging = normal.replace("0.14.0-android.2", "0.14.1-android.1")
    assert check_candidate(baseline, upgraded, upgraded_badging)["status"] == "compatible_public_apk_identity"
    rejected = [
        (baseline, {**new, "package": "com.artcraft.photocraft.ai.preview"}, normal),
        (baseline, {**new, "signer_certificate_sha256": "0" * 64}, normal),
        (baseline, {**new, "version_code": PUBLIC_VERSION_CODE}, normal),
        (baseline, {**new, "version_code": PUBLIC_VERSION_CODE - 1}, normal),
        (baseline, {**new, "tag": PUBLIC_TAG, "version_name": "0.14.0-android.1"}, normal),
        (baseline, {**new, "tag": "photocraft-v0.14.0-android.2", "version_name": "0.14.0-android.1"}, normal),
        ({**baseline, "signer_certificate_sha256": "0" * 64}, new, normal),
        ({**baseline, "version_code": 5}, new, normal),
        (baseline, new, normal.replace("application-label:'PhotoCraft'", "application-label:'PhotoCraft AI Preview'")),
        (baseline, new, normal.replace(
            "com.artcraft.photocraft.PhotoCraftActivity",
            "com.artcraft.photocraft.ai.preview.PhotoCraftActivity")),
        (baseline, {**new, "tag": "v0.14.0-android.2"}, normal),
        # Even with the right signer, refuse contradictory/ambiguous aapt data.
        (baseline, new, normal.replace("versionCode='16790005'", "versionCode='16790004'")),
        (baseline, new, normal.replace("versionName='0.14.0-android.2'", "versionName='0.14.0-android.3'")),
        (baseline, new, normal.replace("name='com.artcraft.photocraft'", "name='com.artcraft.photocraft.ai.preview'")),
        (baseline, new, normal + "application-label:'PhotoCraft'\n"),
        (baseline, new, normal + "launchable-activity: name='com.artcraft.photocraft.ai.preview.PhotoCraftActivity'\n"),
        (baseline, new, normal + "package: name='com.artcraft.photocraft' versionCode='16790005' versionName='0.14.0-android.2'\n"),
        # Malformed duplicate identity fields were previously ignored because
        # only valid regex matches were counted. All must now fail closed.
        (baseline, new, normal + "package: malformed-version-field\n"),
        (baseline, new, normal + "application-label:malformed\n"),
        (baseline, new, normal + "launchable-activity: malformed\n"),
        (baseline, new, normal.replace(
            "application-label:'PhotoCraft'\n",
            "application-label:'PhotoCraft'\napplication-label:broken\n")),
        (baseline, new, normal.replace(
            "launchable-activity: name='com.artcraft.photocraft.PhotoCraftActivity'",
            "launchable-activity: name='com.artcraft.photocraft.PhotoCraftActivity'\nlaunchable-activity:broken")),
    ]
    for previous, future, badge in rejected:
        try:
            check_candidate(previous, future, badge)
        except ValueError:
            pass
        else:
            raise AssertionError("An incompatible PhotoCraft APK candidate was accepted")
    # A signer/package match alone is insufficient: reject non-ARM64, corrupt,
    # ambiguous, path-traversal and accidentally bundled model/key APKs.
    def make_zip(path: Path, members: list[str]) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            for name in members:
                archive.writestr(name, b"test-content")

    with tempfile.TemporaryDirectory() as directory:
        candidate_path = Path(directory) / "candidate.apk"
        good = ["AndroidManifest.xml", "classes.dex",
                "lib/arm64-v8a/libphotocraft.so"]
        make_zip(candidate_path, good)
        assert check_arm64_archive(candidate_path)["native_library_count"] == 1
        # ZIP central-directory sizes must be bounded before testzip() can
        # decompress a potentially huge, highly compressible archive.
        try:
            check_arm64_archive(candidate_path, max_uncompressed_bytes=8)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted candidate exceeding uncompressed size limit")
        unsafe_cases = [
            ["classes.dex", "lib/arm64-v8a/libphotocraft.so"],
            ["AndroidManifest.xml", "classes.dex"],
            ["AndroidManifest.xml", "lib/arm64-v8a/libphotocraft.so"],
            ["AndroidManifest.xml", "classes2.dex", "lib/arm64-v8a/libphotocraft.so"],
            good + ["lib/armeabi-v7a/libother.so"],
            good + ["lib/x86_64/libother.so"],
            good + ["assets/u2netp.onnx"],
            good + ["assets/u2netp.tflite"],
            good + ["assets/u2netp.ort"],
            good + ["assets/u2netp.ckpt"],
            good + ["assets/u2netp.gguf"],
            good + ["assets/u2netp.h5"],
            good + ["assets/photocraft-release.p12"],
            good + ["../outside"],
            good + ["/absolute"],
            good + ["assets\\bad.txt"],
            good + ["lib/arm64-v8a/libphotocraft.so"],
        ]
        for members in unsafe_cases:
            make_zip(candidate_path, members)
            try:
                check_arm64_archive(candidate_path)
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe candidate APK ZIP was accepted: " + str(members))
        # A ZIP can have valid central-directory names and CRCs while its
        # manifest, primary DEX or ARM64 library is zero bytes.
        for critical in good:
            with zipfile.ZipFile(candidate_path, "w") as archive:
                for name in good:
                    archive.writestr(name, b"" if name == critical else b"test-content")
            try:
                check_arm64_archive(candidate_path)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted empty critical APK payload: " + critical)
        # A filename can look like a regular manifest/library while carrying
        # UNIX special-file mode bits; the previous gate rejected symlinks
        # but accepted FIFO, block-device and disguised directory entries.
        for forbidden_mode in (stat.S_IFIFO, stat.S_IFBLK, stat.S_IFDIR):
            with zipfile.ZipFile(candidate_path, "w") as archive:
                for name in good:
                    if name == "AndroidManifest.xml":
                        info = zipfile.ZipInfo(name)
                        info.create_system = 3
                        info.external_attr = (forbidden_mode | 0o644) << 16
                        archive.writestr(info, b"test-content")
                    else:
                        archive.writestr(name, b"test-content")
            try:
                check_arm64_archive(candidate_path)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted disguised special-file APK manifest")
        for ambiguous_name in ("assets//test.dat", "assets/./test.dat"):
            make_zip(candidate_path, good + [ambiguous_name])
            try:
                check_arm64_archive(candidate_path)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted noncanonical APK path: " + ambiguous_name)
        candidate_path.write_bytes(b"not-a-zip")
        try:
            check_arm64_archive(candidate_path)
        except ValueError:
            pass
        else:
            raise AssertionError("Corrupt candidate APK ZIP was accepted")
    print("PASS: ARM64 archive and no-embedded-model/key checks (27 rejection scenarios)")
    print(f"PASS: production upgrade compatibility gates ({len(rejected)} rejection scenarios)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true",
                        help="Offline tests only; no APKs, tools or network required")
    parser.add_argument("--reference-apk", type=Path)
    parser.add_argument("--candidate-apk", type=Path)
    parser.add_argument("--candidate-tag")
    parser.add_argument("--aapt", type=Path)
    parser.add_argument("--apksigner", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    ensure(all((args.reference_apk, args.candidate_apk, args.candidate_tag,
                args.aapt, args.apksigner, args.output)),
           "Provide both signed APKs, candidate tag, Android tools and output")
    ensure(args.reference_apk.resolve() != args.candidate_apk.resolve(),
           "Reference APK and candidate APK must be separate files")
    reference = inspect_apk(args.reference_apk, args.aapt, args.apksigner, PUBLIC_TAG)
    candidate = inspect_apk(args.candidate_apk, args.aapt, args.apksigner, args.candidate_tag)
    candidate_badging = subprocess.check_output(
        [str(args.aapt), "dump", "badging", str(args.candidate_apk)], text=True
    )
    report = check_candidate(reference, candidate, candidate_badging)
    report["archive_checks"] = check_arm64_archive(args.candidate_apk)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS: candidate matches published PhotoCraft signing/package identity")
    print("Candidate version:", report["candidate_tag"])
    print("No APK changed, signed, installed or released.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"STOP: PhotoCraft AI production candidate refused: {error}", file=sys.stderr)
        sys.exit(1)
