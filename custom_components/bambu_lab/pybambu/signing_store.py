# SPDX-License-Identifier: AGPL-3.0-only
"""Offline credential import. No account login, downloader or printer commands."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile
import zlib

from .signing import CommandSigner, CommandSigningError

BUNDLE_FILE = "credentials.json"
PEM_FILES = ("slicer_key.pem", "slicer_cert.pem", "slicer_crl.pem")
MAX_ARCHIVE = 1024 * 1024
MAX_PEM = 256 * 1024


class CredentialImportError(ValueError):
    """A safe, translatable error code, never parser input or private paths."""


def signing_directory(storage: str | Path, serial: str) -> Path:
    """Never allow an entry identity to escape the managed private directory."""
    if not isinstance(serial, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", serial):
        raise CredentialImportError("signing_invalid_identity")
    return Path(storage) / "bambu_lab_signing" / serial


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise CredentialImportError("signing_storage_error")


def _read_archive(path: Path) -> dict[str, str]:
    # Uploaded files are HA-owned temporary files, not user-selected server paths.
    with path.open("rb") as stream:
        content = stream.read(MAX_ARCHIVE + 1)
    if len(content) > MAX_ARCHIVE:
        raise CredentialImportError("signing_invalid_archive")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) != 3 or {item.filename for item in entries} != set(PEM_FILES):
                raise ValueError
            result = {}
            for item in entries:
                file_type = stat.S_IFMT(item.external_attr >> 16)
                if (item.flag_bits & 1 or item.file_size > MAX_PEM
                        or file_type not in (0, stat.S_IFREG)
                        or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError
                with archive.open(item) as source:
                    data = source.read(MAX_PEM + 1)
                if not data or len(data) > MAX_PEM:
                    raise ValueError
                result[item.filename] = data.decode("ascii")
            return result
    except (ValueError, KeyError, RuntimeError, NotImplementedError, zipfile.BadZipFile, EOFError, zlib.error):
        raise CredentialImportError("signing_invalid_archive") from None


def inspect_credentials(directory: Path, *, trust_roots: bytes | None = None) -> dict:
    """Inspect only; no provisioning, renewal, compatibility extension or writes."""
    try:
        return CommandSigner(directory, trust_roots=trust_roots).status()
    except (CommandSigningError, OSError, ValueError):
        return {"reason": "credentials_invalid", "configured": False, "ready": False,
                "review_due": False, "valid_until": None, "crl_stale": False}


def import_credentials(archive_path: Path, directory: Path, *,
                       trust_roots: bytes | None = None) -> dict:
    """Validate a fresh bundle then atomically replace its one active snapshot.

    Legacy PEMs, sequence.json and sequence.lock are never overwritten. The
    snapshot is authoritative once present; an invalid snapshot cannot fall
    back to older authorization. No stale-CRL receipts can enter via this flow.
    """
    material = _read_archive(archive_path)
    try:
        _private_directory(directory.parent)
        _private_directory(directory)
        # Validate in an owner-only staging directory on the same filesystem.
        # No active credential file is modified until every check succeeds.
        with tempfile.TemporaryDirectory(prefix=".import-", dir=directory) as temporary:
            stage = Path(temporary)
            for name, pem in material.items():
                fd = os.open(stage / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(pem)
            try:
                signer = CommandSigner(stage, trust_roots=trust_roots)
                if not signer.configured or signer.crl_stale:
                    raise CommandSigningError("fresh credentials required")
            except (CommandSigningError, ValueError):
                raise CredentialImportError("signing_credentials_rejected") from None
            snapshot = stage / BUNDLE_FILE
            fd = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump({"version": 1, "files": material}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(snapshot, directory / BUNDLE_FILE)
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return signer.status()
    except OSError:
        raise CredentialImportError("signing_storage_error") from None
