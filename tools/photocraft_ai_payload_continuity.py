#!/usr/bin/env python3
"""Read-only PhotoCraft AI unsigned-to-signed APK payload continuity gate.

Compare ZIP member bytes of the verified unsigned input against owner-signed
APK. zipalign and APK Signing Block changes are permitted; application payload
bytes must be identical. This does NOT verify signatures, package/version or
model rights. Run the separate compatibility gate before any device test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import struct
import sys
import tempfile
import zipfile

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SIGNATURE_FILE = re.compile(
    r"META-INF/(?:MANIFEST\.MF|[A-Za-z0-9_-]{1,64}\.(?:SF|RSA|DSA|EC))\Z", re.I
)
MAX_APK_BYTES = 512 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def signature_metadata(name: str) -> bool:
    return name == "META-INF/" or bool(SIGNATURE_FILE.fullmatch(name))


def contains_apk_signing_block(path: Path, archive: zipfile.ZipFile) -> bool:
    """Detect a stale APK v2/v3 signing block without parsing secret material.

    Android's APK Signing Block ends immediately before the ZIP central
    directory with the 16-byte magic "APK Sig Block 42". ZIP readers can
    accept this extra block even when the archive is called UNSIGNED.
    Reject the marker, including malformed blocks, before owner signing.
    """
    if archive.start_dir < 24:
        return False
    with path.open("rb") as stream:
        stream.seek(archive.start_dir - 16)
        return stream.read(16) == b"APK Sig Block 42"


def archive_members(apk: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    entries = apk.infolist()
    names = [entry.filename for entry in entries]
    require(len(names) == len(set(names)), "APK contains duplicate ZIP members")
    require("AndroidManifest.xml" in names, "APK is missing AndroidManifest.xml")
    require(any(name.startswith("classes") and name.endswith(".dex") for name in names),
            "APK is missing dex bytecode")
    total = 0
    for entry in entries:
        name = entry.filename
        segments = name.split("/")
        if entry.is_dir():
            segments = segments[:-1]
        require(bool(segments) and all(segment not in ("", ".", "..") for segment in segments)
                and not name.startswith("/") and "\\" not in name and "\x00" not in name,
                "APK contains a noncanonical ZIP path")
        require(not (entry.flag_bits & 1), "APK contains encrypted ZIP member")
        mode = stat.S_IFMT(entry.external_attr >> 16)
        require(mode in ((0, stat.S_IFDIR) if entry.is_dir() else (0, stat.S_IFREG)),
                "APK contains special-file ZIP member")
        require(not entry.is_dir() or entry.file_size == 0,
                "APK contains nonempty directory ZIP member")
        total += entry.file_size
        require(total <= MAX_UNCOMPRESSED_BYTES, "APK exceeds total uncompressed size limit")
    return {entry.filename: entry for entry in entries}


def check(unsigned_path: Path, signed_path: Path, expected_unsigned_sha256: str) -> dict:
    require(bool(SHA256.fullmatch(expected_unsigned_sha256)),
            "Pinned unsigned APK SHA256 is required (from verified artifact SHA256SUMS)")
    require(unsigned_path.resolve() != signed_path.resolve(), "Unsigned and signed APK must differ")
    for path in (unsigned_path, signed_path):
        require(path.is_file() and not path.is_symlink(), "APK input must be a regular file")
        require(0 < path.stat().st_size <= MAX_APK_BYTES, "APK input exceeds safe file size")
    with unsigned_path.open("rb") as stream:
        require(sha256_stream(stream) == expected_unsigned_sha256,
                "Unsigned APK does not match externally verified artifact checksum")
    try:
        with zipfile.ZipFile(unsigned_path) as unsigned, zipfile.ZipFile(signed_path) as signed:
            before = archive_members(unsigned)
            after = archive_members(signed)
            # Only the *newly signed* APK may introduce v1 JAR signature
            # metadata. The source is an explicitly unsigned signing input:
            # silently exempting an existing META-INF/CERT.RSA or MANIFEST.MF
            # from payload comparison could hide a stale/disposable signature.
            require(not any(SIGNATURE_FILE.fullmatch(name) for name in before),
                    "Unsigned signing input contains preexisting JAR signature metadata")
            require(not contains_apk_signing_block(unsigned_path, unsigned),
                    "Unsigned signing input contains a stale APK v2/v3 signing block")
            for name in before.keys() | after.keys():
                if signature_metadata(name):
                    continue
                require(name in before and name in after,
                        "Application payload ZIP member added or removed: " + name)
                a, b = before[name], after[name]
                require(a.is_dir() == b.is_dir(), "Application payload type changed: " + name)
                if not a.is_dir():
                    with unsigned.open(a) as left, signed.open(b) as right:
                        require(sha256_stream(left) == sha256_stream(right),
                                "Application payload bytes changed: " + name)
            # Read allowed signing metadata too, to detect corrupt CRCs.
            for name in after.keys():
                if signature_metadata(name) and not after[name].is_dir():
                    with signed.open(name) as stream:
                        sha256_stream(stream)
            with signed_path.open("rb") as stream:
                signed_digest = sha256_stream(stream)
            return {
                "status": "payload_continuity_only_not_signature_verified",
                "unsigned_apk_sha256": expected_unsigned_sha256,
                "signed_apk_sha256": signed_digest,
                "preserved_non_signature_members": sum(
                    not signature_metadata(n) for n in before
                ),
                "signature_metadata_members": sum(signature_metadata(n) for n in after),
                "warning": "Run original-certificate/package/version compatibility and owner device checks separately. Do not publish or install on this report alone.",
            }
    except (zipfile.BadZipFile, EOFError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("APK ZIP payload could not be verified") from exc


def self_test() -> None:
    files = {
        "AndroidManifest.xml": b"manifest-bytes",
        "classes.dex": b"dex-bytes",
        "lib/arm64-v8a/libphotocraft.so": b"elf-placeholder",
        "assets/ai-ui.txt": b"local-consent",
    }

    def write(path: Path, members: list[tuple[str, bytes]],
              special: str | None = None) -> None:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in members:
                if name == special:
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFIFO | 0o644) << 16
                    archive.writestr(info, content)
                else:
                    archive.writestr(name, content)

    with tempfile.TemporaryDirectory() as directory:
        unsigned = Path(directory) / "unsigned.apk"
        signed = Path(directory) / "signed.apk"
        write(unsigned, list(files.items()))
        with unsigned.open("rb") as stream:
            pinned = sha256_stream(stream)
        signed_members = list(files.items()) + [
            ("META-INF/MANIFEST.MF", b"manifest-signature"),
            ("META-INF/CERT.SF", b"signature-file"),
            ("META-INF/CERT.RSA", b"signature-bytes"),
        ]
        write(signed, signed_members)
        assert check(unsigned, signed, pinned)["preserved_non_signature_members"] == 4
        # The old comparator skipped all known signature paths even if they
        # were already in the purportedly UNSIGNED input. A stale v1 signature
        # must be rejected, even with a correctly pinned input checksum.
        for stale in ("META-INF/MANIFEST.MF", "META-INF/CERT.RSA"):
            write(unsigned, list(files.items()) + [(stale, b"stale-disposable-signature")])
            with unsigned.open("rb") as stream:
                contaminated_pinned = sha256_stream(stream)
            try:
                check(unsigned, signed, contaminated_pinned)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted stale signature metadata in unsigned APK")
        # Repacked APKs must also be free of v2/v3 APK Signing Blocks.
        # Python zipfile still accepts a ZIP with this opaque block, so a
        # valid payload checksum alone does not prove an unsigned input.
        for footer_size in (24, 0):
            write(unsigned, list(files.items()))
            raw = unsigned.read_bytes()
            with zipfile.ZipFile(unsigned) as archive:
                central = archive.start_dir
            eocd = raw.rfind(bytes.fromhex("504b0506"))
            assert eocd >= 0
            block = struct.pack("<QQ", 24, footer_size) + b"APK Sig Block 42"
            modified = raw[:central] + block + raw[central:]
            eocd += len(block)
            old_offset = struct.unpack_from("<I", modified, eocd + 16)[0]
            modified = (modified[:eocd + 16]
                        + struct.pack("<I", old_offset + len(block))
                        + modified[eocd + 20:])
            unsigned.write_bytes(modified)
            with zipfile.ZipFile(unsigned) as archive:
                assert archive.read("classes.dex") == files["classes.dex"]
            with unsigned.open("rb") as stream:
                contaminated_pinned = sha256_stream(stream)
            try:
                check(unsigned, signed, contaminated_pinned)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted stale APK signing block in unsigned APK")
        write(unsigned, list(files.items()))
        cases = [
            (list(files.items())[:-1], None),
            (list(files.items()) + [("assets/extra.txt", b"surprise")], None),
            ([(n, b"changed" if n == "classes.dex" else b) for n, b in files.items()], None),
            (signed_members + [("META-INF/rogue.txt", b"unexpected")], None),
            (signed_members + [("../outside", b"unsafe")], None),
            (signed_members + [("assets/./odd", b"unsafe")], None),
            (signed_members + [("assets//odd", b"unsafe")], None),
            (signed_members + [("classes.dex", b"duplicate")], None),
            (signed_members, "AndroidManifest.xml"),
        ]
        for members, special in cases:
            write(signed, members, special)
            try:
                check(unsigned, signed, pinned)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted modified or malformed signed APK")
        write(signed, signed_members)
        for wrong in ("0" * 64, "0" * 63):
            try:
                check(unsigned, signed, wrong)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted wrong or missing source checksum")
        try:
            check(unsigned, unsigned, pinned)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted same APK for both roles")
    print("PASS: owner-signed APK payload continuity (16 negative scenarios)")
    print("No APK built, signed, installed, uploaded or published")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--unsigned-apk", type=Path)
    parser.add_argument("--signed-apk", type=Path)
    parser.add_argument("--expected-unsigned-sha256")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not (args.unsigned_apk and args.signed_apk and args.expected_unsigned_sha256):
        parser.error("--unsigned-apk, --signed-apk and --expected-unsigned-sha256 required")
    print(json.dumps(check(args.unsigned_apk, args.signed_apk,
                           args.expected_unsigned_sha256), indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        print("STOP: PhotoCraft AI payload continuity refused: " + str(exc), file=sys.stderr)
        sys.exit(1)
