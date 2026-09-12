# SPDX-License-Identifier: AGPL-3.0-only
"""Signed MQTT command support for authorization-protected Bambu printers.

The protocol is implemented independently from public wire documentation. It
does not contain or download Bambu application credentials; an operator must
place their own credential files in the configured directory.
"""

from __future__ import annotations

import base64
import copy
import json
import os
import fcntl
import hashlib
import re
import stat
import threading
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class CommandSigningError(RuntimeError):
    """Raised when a privileged command cannot be signed safely."""


def _first_certificate(pem: bytes) -> x509.Certificate:
    marker = b"-----END CERTIFICATE-----"
    end = pem.find(marker)
    if end < 0:
        raise CommandSigningError("certificate file contains no PEM certificate")
    return x509.load_pem_x509_certificate(pem[: end + len(marker)] + b"\n")


def _cert_id(certificate: x509.Certificate) -> str:
    serial = format(certificate.serial_number, "x")
    if len(serial) % 2:
        serial = "0" + serial
    return serial + certificate.issuer.rfc4514_string()


def _encrypt_blocks(public_key: rsa.RSAPublicKey, plaintext: str) -> str:
    data = plaintext.encode("utf-8")
    block_size = public_key.key_size // 8 - 11
    chunks = [data[index:index + block_size] for index in range(0, len(data), block_size)]
    if not chunks:
        chunks = [b""]
    ciphertext = b"".join(
        public_key.encrypt(chunk, padding.PKCS1v15()) for chunk in chunks
    )
    return base64.b64encode(ciphertext).decode("ascii")


class CommandSigner:
    """Provision printer trust and sign authorization-protected commands."""

    def __init__(self, credentials_dir: str | os.PathLike[str] | None) -> None:
        self._credentials_dir = Path(credentials_dir) if credentials_dir else None
        self._lock = threading.RLock()
        self._private_key: rsa.RSAPrivateKey | None = None
        self._app_certificate_pem = ""
        self._crl_pem = ""
        self._cert_id = ""
        self._device_public_key: rsa.RSAPublicKey | None = None
        self._provisioned = False
        self._pending_sequence: str | None = None
        self._pending_commands: list[str] = []
        self._valid_from: datetime | None = None
        self._valid_until: datetime | None = None
        self.crl_stale = False
        try:
            self._load_credentials()
        except (ValueError, TypeError, IndexError, InvalidSignature, UnsupportedAlgorithm):
            raise CommandSigningError("signing material failed cryptographic validation") from None

    @property
    def configured(self) -> bool:
        """Return whether a valid app key, certificate and CRL were loaded."""
        with self._lock:
            return bool(
                self._private_key
                and self._app_certificate_pem
                and self._crl_pem
                and self._cert_id
                and self._valid_from <= datetime.now(timezone.utc) < self._valid_until
            )

    @property
    def ready(self) -> bool:
        """Return whether this MQTT session can send privileged commands."""
        with self._lock:
            return self.configured and self._provisioned and self._device_public_key is not None

    def _load_credentials(self) -> None:
        if self._credentials_dir is None:
            return
        key_path = self._credentials_dir / "slicer_key.pem"
        cert_path = self._credentials_dir / "slicer_cert.pem"
        crl_path = self._credentials_dir / "slicer_crl.pem"
        if not all(path.exists() for path in (key_path, cert_path, crl_path)):
            return
        if self._credentials_dir.is_symlink() or self._credentials_dir.stat().st_mode & 0o077:
            raise CommandSigningError("signing directory must be private and not a symlink")

        key = serialization.load_pem_private_key(self._read_private(key_path), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise CommandSigningError("slicer key is not RSA")
        cert_pem = self._read_private(cert_path)
        chain = x509.load_pem_x509_certificates(cert_pem)
        certificate = chain[0]
        cert_public_key = certificate.public_key()
        if not isinstance(cert_public_key, rsa.RSAPublicKey):
            raise CommandSigningError("slicer certificate key is not RSA")
        if key.public_key().public_numbers() != cert_public_key.public_numbers():
            raise CommandSigningError("slicer key does not match slicer certificate")

        crl_bytes = self._read_private(crl_path)
        crl_pem = crl_bytes.decode("utf-8")
        crl_blocks = re.findall(
            r"-----BEGIN X509 CRL-----.*?-----END X509 CRL-----", crl_pem, re.DOTALL
        )
        if not crl_blocks:
            raise CommandSigningError("CRL file contains no PEM CRL")
        crls = [x509.load_pem_x509_crl(block.encode()) for block in crl_blocks]
        for crl in crls:
            issuers = [cert for cert in chain if cert.subject == crl.issuer]
            if not any(crl.is_signature_valid(cert.public_key()) for cert in issuers):
                raise CommandSigningError("CRL signature cannot be verified against the app chain")
            for cert in chain:
                if cert.issuer == crl.issuer and crl.get_revoked_certificate_by_serial_number(cert.serial_number):
                    raise CommandSigningError("app certificate is revoked")
        for cert in chain:
            issuer = next((c for c in chain if c.subject == cert.issuer), None)
            if issuer is not None:
                cert.verify_directly_issued_by(issuer)
        starts = [cert.not_valid_before_utc for cert in chain]
        ends = [cert.not_valid_after_utc for cert in chain]
        starts.extend(crl.last_update_utc for crl in crls)
        if any(crl.next_update_utc is None for crl in crls):
            raise CommandSigningError("CRL has no expiry")
        now = datetime.now(timezone.utc)
        crl_end = min(crl.next_update_utc for crl in crls)
        self.crl_stale = crl_end <= now
        if self.crl_stale:
            # Current official clients can supply signed CRLs beyond nextUpdate;
            # firmware still consults their revocation entries. Default remains
            # strict. A reviewed, hash-pinned, time-bounded local exception is
            # required for that exact vendor bundle, never arbitrary stale data.
            ends.append(self._reviewed_crl_deadline(cert_pem, crl_bytes, now))
        else:
            ends.append(crl_end)
        if not max(starts) <= now < min(ends):
            raise CommandSigningError("signing material is expired or not yet valid")

        with self._lock:
            self._private_key = key
            self._app_certificate_pem = cert_pem.decode("utf-8")
            self._crl_pem = crl_pem
            self._cert_id = _cert_id(certificate)
            self._valid_from, self._valid_until = max(starts), min(ends)

    def _reviewed_crl_deadline(self, cert: bytes, crl: bytes, now: datetime) -> datetime:
        path = self._credentials_dir / "crl_compatibility.json"
        try:
            policy = json.loads(self._read_private(path))
            reviewed = datetime.fromisoformat(policy["reviewed_at"])
            deadline = datetime.fromisoformat(policy["valid_until"])
            if (
                policy["policy"] != "reviewed-vendor-crl-v1"
                or policy["certificate_sha256"] != hashlib.sha256(cert).hexdigest()
                or policy["crl_sha256"] != hashlib.sha256(crl).hexdigest()
                or not re.fullmatch(r"[0-9a-f]{64}", policy["source_plugin_sha256"])
                or reviewed.tzinfo is None
                or deadline.tzinfo is None
                or not reviewed <= now < deadline <= reviewed + timedelta(days=30)
            ):
                raise ValueError
            return deadline
        except (OSError, ValueError, KeyError, TypeError, CommandSigningError):
            raise CommandSigningError(
                "expired CRL requires a current hash-pinned vendor compatibility review"
            ) from None

    @staticmethod
    def _read_private(path: Path) -> bytes:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
                raise CommandSigningError("invalid signing file type or size")
            if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise CommandSigningError("signing files require owner-only permissions")
            return stream.read(1024 * 1024 + 1)

    def reset_session(self) -> None:
        """Require fresh printer trust provisioning after a disconnect."""
        with self._lock:
            self._provisioned = False
            self._pending_sequence = None
            self._device_public_key = None
            self._pending_commands.clear()

    def _next_sequence_id(self) -> str:
        with self._lock:
            if self._credentials_dir is None:
                raise CommandSigningError("sequence storage is unavailable")
            # One durable counter across reconnects, HA restarts and processes.
            # Never use epoch milliseconds: firmware has signed-32-bit paths.
            path = self._credentials_dir / "sequence.json"
            lock_path = self._credentials_dir / "sequence.lock"
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "r+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    value = json.loads(self._read_private(path))["next"] if path.exists() else 20000
                    if type(value) is not int or not 20000 <= value <= 2147483647:
                        raise ValueError
                    out, temporary = tempfile.mkstemp(prefix="sequence-", dir=self._credentials_dir)
                    try:
                        with os.fdopen(out, "w") as stream:
                            json.dump({"next": value + 1}, stream)
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.replace(temporary, path)
                    finally:
                        if os.path.exists(temporary):
                            os.unlink(temporary)
                    directory = os.open(self._credentials_dir, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                    return str(value)
                except (OSError, ValueError, KeyError, TypeError):
                    raise CommandSigningError("sequence storage is invalid or exhausted") from None

    def build_provision_message(self) -> dict[str, Any]:
        """Build the unsigned security command that installs app trust."""
        if not self.configured:
            raise CommandSigningError("slicer credentials are not configured")
        with self._lock:
            self._provisioned = False
            self._device_public_key = None
            self._pending_sequence = self._next_sequence_id()
            return {
                "security": {
                    "sequence_id": self._pending_sequence,
                    "command": "app_cert_install",
                    "app_cert": self._app_certificate_pem,
                    "crl": self._crl_pem,
                }
            }

    def handle_security_report(self, report: dict[str, Any]) -> bool:
        """Harvest the printer certificate from a successful install reply."""
        with self._lock:
            return self._handle_security_report_locked(report)

    def _handle_security_report_locked(self, report: dict[str, Any]) -> bool:
        if report.get("command") != "app_cert_install":
            return False
        if not self.configured or self._pending_sequence is None:
            return False
        if str(report.get("sequence_id")) != self._pending_sequence:
            return False
        if str(report.get("result")).upper() != "SUCCESS" or not report.get("printer_cert"):
            self.reset_session()
            return False

        printer_pem = str(report["printer_cert"]).encode("utf-8")
        certificate = _first_certificate(printer_pem)
        now = datetime.now(timezone.utc)
        if not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc:
            raise CommandSigningError("printer certificate is expired or not yet valid")
        public_key = certificate.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise CommandSigningError("printer certificate key is not RSA")

        with self._lock:
            self._device_public_key = public_key
            self._provisioned = True
            self._pending_sequence = None
            self._valid_until = min(self._valid_until, certificate.not_valid_after_utc)
        return True

    def sign_print_message(self, message: dict[str, Any]) -> str:
        """Encrypt protected fields and return a byte-exact signed envelope."""
        if "print" not in message or not isinstance(message["print"], dict):
            return json.dumps(message, separators=(",", ":"), ensure_ascii=False)
        if not self.ready:
            raise CommandSigningError("command signer is not ready for this MQTT session")

        with self._lock:
            if not self.ready:
                raise CommandSigningError("command signer session changed")
            print_data = copy.deepcopy(message["print"])
            print_data["sequence_id"] = self._next_sequence_id()
            assert self._device_public_key is not None
            fields = {"gcode_line": ("param",), "project_file": ("url", "param")}.get(
                print_data.get("command"), ()
            )
            for field in fields:
                value = print_data.get(field)
                encrypted_field = field + "_enc"
                if encrypted_field in print_data:
                    raise CommandSigningError("pre-encrypted command fields are not accepted")
                if isinstance(value, str):
                    print_data[encrypted_field] = _encrypt_blocks(
                        self._device_public_key,
                        value,
                    )
                    del print_data[field]

            print_text = json.dumps(
                print_data,
                separators=(",", ":"),
                sort_keys=True,
                ensure_ascii=False,
            )
            signed_text = '{"print":' + print_text + "}"
            assert self._private_key is not None
            signature = self._private_key.sign(
                signed_text.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            header = {
                "cert_id": self._cert_id,
                "payload_len": len(signed_text.encode("utf-8")),
                "sign_alg": "RSA_SHA256",
                "sign_string": base64.b64encode(signature).decode("ascii"),
                "sign_ver": "v1.0",
            }
            header_text = json.dumps(
                header,
                separators=(",", ":"),
                sort_keys=True,
                ensure_ascii=False,
            )
            self._pending_commands.append(print_data["sequence_id"])
            self._pending_commands = self._pending_commands[-32:]
            return '{"header":' + header_text + ',"print":' + print_text + "}"

    def handle_print_report(self, report: dict[str, Any]) -> bool:
        """Invalidate trust on our own verification rejection, never replay motion."""
        with self._lock:
            sequence = str(report.get("sequence_id"))
            if sequence not in self._pending_commands:
                return False
            self._pending_commands.remove(sequence)
            try:
                code = int(report.get("err_code", 0))
            except (TypeError, ValueError):
                return False
            if 84033543 <= code <= 84033548:
                self.reset_session()
                return True
            return False
