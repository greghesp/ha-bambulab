# SPDX-License-Identifier: AGPL-3.0-only
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from pybambu.signing import CommandSigner, CommandSigningError
from pybambu.bambu_client import BambuClient


def _certificate(key, common_name):
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )


def _write_credentials(path, *, revoked=False, expired=False):
    app_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    app_cert = _certificate(app_key, "test-app")
    path.mkdir(mode=0o700, exist_ok=True)
    (path / "slicer_key.pem").write_bytes(
        app_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (path / "slicer_cert.pem").write_bytes(app_cert.public_bytes(serialization.Encoding.PEM))
    now = datetime.now(timezone.utc)
    crl = (x509.CertificateRevocationListBuilder()
           .issuer_name(app_cert.issuer)
           .last_update(now - timedelta(days=2))
           .next_update(now + timedelta(days=-1 if expired else 20)))
    if revoked:
        crl = crl.add_revoked_certificate(x509.RevokedCertificateBuilder()
              .serial_number(app_cert.serial_number)
              .revocation_date(now - timedelta(days=1)).build())
    (path / "slicer_crl.pem").write_bytes(crl.sign(app_key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
    for p in path.iterdir():
        p.chmod(0o600)
    return app_key


def test_missing_credentials_fail_closed(tmp_path):
    signer = CommandSigner(tmp_path)
    assert not signer.configured
    assert not signer.ready
    with pytest.raises(CommandSigningError):
        signer.build_provision_message()
    with pytest.raises(CommandSigningError):
        signer.sign_print_message({"print": {"command": "pause"}})


def _review_vendor_crl(path, **changes):
    now = datetime.now(timezone.utc)
    policy = {
        "policy": "reviewed-vendor-crl-v1",
        "certificate_sha256": hashlib.sha256((path / "slicer_cert.pem").read_bytes()).hexdigest(),
        "crl_sha256": hashlib.sha256((path / "slicer_crl.pem").read_bytes()).hexdigest(),
        "source_plugin_sha256": "a" * 64,
        "reviewed_at": (now - timedelta(seconds=1)).isoformat(),
        "valid_until": (now + timedelta(days=7)).isoformat(),
    }
    policy.update(changes)
    receipt = path / "crl_compatibility.json"
    receipt.write_text(json.dumps(policy))
    receipt.chmod(0o600)


def test_reviewed_vendor_crl_requires_exact_bundle_and_deadline(tmp_path):
    _write_credentials(tmp_path, expired=True)
    with pytest.raises(CommandSigningError):
        CommandSigner(tmp_path)
    _review_vendor_crl(tmp_path)
    signer = CommandSigner(tmp_path)
    assert signer.configured and signer.crl_stale and not signer.ready
    assert signer._valid_until < datetime.now(timezone.utc) + timedelta(days=8)
    _review_vendor_crl(tmp_path, crl_sha256="0" * 64)
    with pytest.raises(CommandSigningError):
        CommandSigner(tmp_path)


@pytest.mark.parametrize("changes", [
    {"valid_until": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()},
    {"valid_until": (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()},
    {"reviewed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()},
    {"certificate_sha256": "0" * 64},
])
def test_vendor_crl_review_rejects_invalid_scope_or_lifetime(tmp_path, changes):
    _write_credentials(tmp_path, expired=True)
    _review_vendor_crl(tmp_path, **changes)
    with pytest.raises(CommandSigningError):
        CommandSigner(tmp_path)


def test_reviewed_vendor_crl_still_rejects_revoked_certificate(tmp_path):
    _write_credentials(tmp_path, expired=True, revoked=True)
    _review_vendor_crl(tmp_path)
    with pytest.raises(CommandSigningError, match="revoked"):
        CommandSigner(tmp_path)


def test_provision_sign_encrypt_and_reset(tmp_path):
    app_key = _write_credentials(tmp_path)
    signer = CommandSigner(tmp_path)
    assert signer.configured
    assert not signer.ready

    provision = signer.build_provision_message()["security"]
    assert provision["command"] == "app_cert_install"
    assert 20000 <= int(provision["sequence_id"]) < 30000
    assert "PRIVATE KEY" not in provision["app_cert"]

    device_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    device_cert = _certificate(device_key, "test-printer")
    assert signer.handle_security_report(
        {
            "command": "app_cert_install",
            "sequence_id": provision["sequence_id"],
            "result": "SUCCESS",
            "printer_cert": device_cert.public_bytes(serialization.Encoding.PEM).decode(),
        }
    )
    assert signer.ready
    assert not (tmp_path / "printer_cert.pem").exists()  # Session-only trust.

    envelope_text = signer.sign_print_message(
        {
            "print": {
                "sequence_id": "0",
                "command": "gcode_line",
                "param": "M106 P3 S26\n",
            }
        }
    )
    envelope = json.loads(envelope_text)
    assert "param" not in envelope["print"]
    assert envelope["header"]["sign_alg"] == "RSA_SHA256"
    assert envelope["header"]["sign_ver"] == "v1.0"
    assert 20000 <= int(envelope["print"]["sequence_id"]) < 30000

    print_text = json.dumps(
        envelope["print"], separators=(",", ":"), sort_keys=True, ensure_ascii=False
    )
    signed_text = '{"print":' + print_text + "}"
    assert envelope["header"]["payload_len"] == len(signed_text.encode("utf-8"))
    app_key.public_key().verify(
        base64.b64decode(envelope["header"]["sign_string"]),
        signed_text.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    decrypted = device_key.decrypt(
        base64.b64decode(envelope["print"]["param_enc"]),
        padding.PKCS1v15(),
    )
    assert decrypted == b"M106 P3 S26\n"

    signer.reset_session()
    assert not signer.ready
    with pytest.raises(CommandSigningError):
        signer.sign_print_message({"print": {"command": "pause"}})


def test_non_print_message_passes_through(tmp_path):
    signer = CommandSigner(tmp_path)
    text = signer.sign_print_message({"system": {"command": "ledctrl"}})
    assert json.loads(text) == {"system": {"command": "ledctrl"}}


def test_bambu_client_publish_uses_signed_envelope(tmp_path):
    _write_credentials(tmp_path)
    client = BambuClient(
        {
            "host": "",
            "serial": "TEST-SERIAL",
            "signing_path": str(tmp_path),
        }
    )
    device_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    device_cert = _certificate(device_key, "test-printer")
    provision = client.command_signer.build_provision_message()["security"]
    client.command_signer.handle_security_report(
        {
            "command": "app_cert_install",
            "sequence_id": provision["sequence_id"],
            "result": "SUCCESS",
            "printer_cert": device_cert.public_bytes(serialization.Encoding.PEM).decode(),
        }
    )
    client.get_device().print_fun._encryption_enabled = True

    class Result:
        rc = 0

    class CaptureMqtt:
        def __init__(self):
            self.topic = None
            self.payload = None

        def publish(self, topic, payload):
            self.topic = topic
            self.payload = payload
            return Result()

    mqtt = CaptureMqtt()
    client.client = mqtt
    assert client.publish(
        {
            "print": {
                "sequence_id": "0",
                "command": "gcode_line",
                "param": "M106 P2 S128\n",
            }
        }
    )
    assert mqtt.topic == "device/TEST-SERIAL/request"
    assert "header" in json.loads(mqtt.payload)


def _make_ready(signer):
    request = signer.build_provision_message()["security"]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    reply = {"command": "app_cert_install", "sequence_id": request["sequence_id"],
             "result": "SUCCESS", "printer_cert": _certificate(key, "printer").public_bytes(serialization.Encoding.PEM).decode()}
    assert signer.handle_security_report(reply)
    return key, reply


@pytest.mark.parametrize("kind", ["expired", "revoked"])
def test_invalid_crl_blocks_credentials(tmp_path, kind):
    _write_credentials(tmp_path, **{kind: True})
    with pytest.raises(CommandSigningError):
        CommandSigner(tmp_path)


def test_invalid_crl_signature_blocks_credentials(tmp_path):
    _write_credentials(tmp_path)
    data = bytearray((tmp_path / "slicer_crl.pem").read_bytes())
    pos = len(data) - len(b"-----END X509 CRL-----\n") - 20
    data[pos] = ord('A') if data[pos] != ord('A') else ord('B')
    (tmp_path / "slicer_crl.pem").write_bytes(data)
    with pytest.raises(CommandSigningError):
        CommandSigner(tmp_path)


def test_permissions_and_symlinks_fail_closed(tmp_path):
    _write_credentials(tmp_path)
    key = tmp_path / "slicer_key.pem"
    key.chmod(0o644)
    with pytest.raises(CommandSigningError):
        CommandSigner(tmp_path)
    key.chmod(0o600)
    key.rename(tmp_path / "real.pem")
    key.symlink_to(tmp_path / "real.pem")
    with pytest.raises(OSError):
        CommandSigner(tmp_path)


def test_unsolicited_and_stale_provision_reports_do_not_authorize(tmp_path):
    _write_credentials(tmp_path)
    signer = CommandSigner(tmp_path)
    _, reply = _make_ready(signer)
    signer.reset_session()
    assert not signer.handle_security_report(reply)
    request = signer.build_provision_message()["security"]
    assert not signer.handle_security_report(reply)
    assert not signer.ready
    reply["sequence_id"] = request["sequence_id"]
    reply["result"] = "FAIL"
    assert not signer.handle_security_report(reply)
    assert not signer.ready


def test_sequence_survives_restart_and_range_boundary(tmp_path):
    _write_credentials(tmp_path)
    (tmp_path / "sequence.json").write_text('{"next":29999}')
    (tmp_path / "sequence.json").chmod(0o600)
    first = CommandSigner(tmp_path).build_provision_message()["security"]["sequence_id"]
    second = CommandSigner(tmp_path).build_provision_message()["security"]["sequence_id"]
    assert [first, second] == ["29999", "30000"]


@pytest.mark.parametrize("counter", ['{"next":2147483648}', '{"next":true}', 'broken'])
def test_corrupt_or_exhausted_sequence_fails_closed(tmp_path, counter):
    _write_credentials(tmp_path)
    (tmp_path / "sequence.json").write_text(counter)
    (tmp_path / "sequence.json").chmod(0o600)
    with pytest.raises(CommandSigningError):
        CommandSigner(tmp_path).build_provision_message()


def test_encryption_long_unicode_payload_and_no_input_mutation(tmp_path):
    _write_credentials(tmp_path)
    signer = CommandSigner(tmp_path)
    key, _ = _make_ready(signer)
    param = 'M106 P3 S26\n; ' + 'é' * 400
    message = {"print": {"command": "gcode_line", "param": param}}
    payload = json.loads(signer.sign_print_message(message))["print"]
    encrypted = base64.b64decode(payload["param_enc"])
    decoded = b''.join(key.decrypt(encrypted[i:i+256], padding.PKCS1v15()) for i in range(0, len(encrypted), 256))
    assert decoded.decode() == param
    assert "param" not in payload
    assert message == {"print": {"command": "gcode_line", "param": param}}


def test_non_gcode_params_remain_plain_and_preencrypted_gcode_is_rejected(tmp_path):
    _write_credentials(tmp_path)
    signer = CommandSigner(tmp_path)
    _make_ready(signer)
    payload = json.loads(signer.sign_print_message({"print": {"command": "print_speed", "param": "2"}}))
    assert payload["print"]["param"] == "2"
    assert "param_enc" not in payload["print"]
    with pytest.raises(CommandSigningError):
        signer.sign_print_message({"print": {"command": "gcode_line", "param_enc": "untrusted"}})


def test_material_expiry_during_running_session_disables_controls(tmp_path):
    _write_credentials(tmp_path)
    signer = CommandSigner(tmp_path)
    _make_ready(signer)
    signer._valid_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert not signer.ready
    with pytest.raises(CommandSigningError):
        signer.sign_print_message({"print": {"command": "gcode_line", "param": "M106 P3 S0"}})


def test_verification_rejection_invalidates_only_our_own_command(tmp_path):
    _write_credentials(tmp_path)
    signer = CommandSigner(tmp_path)
    _make_ready(signer)
    payload = json.loads(signer.sign_print_message({"print": {"command": "gcode_line", "param": "M106 P3 S0"}}))
    assert not signer.handle_print_report({"sequence_id": "unrelated", "err_code": 84033545})
    assert signer.ready
    assert signer.handle_print_report({"sequence_id": payload["print"]["sequence_id"], "err_code": 84033545})
    assert not signer.ready


def test_concurrent_signer_instances_reserve_unique_sequences(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    _write_credentials(tmp_path)
    signers = [CommandSigner(tmp_path) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        values = list(executor.map(lambda i: int(signers[i % 4].build_provision_message()["security"]["sequence_id"]), range(20)))
    assert sorted(values) == list(range(20000, 20020))


def test_signed_fan_speed_is_not_optimistically_reported():
    from unittest.mock import MagicMock
    from pybambu.models import Fans
    from pybambu.const import FansEnum
    client = MagicMock()
    client.publish.return_value = True
    client.get_device.return_value.print_fun.mqtt_signature_required = True
    fans = Fans(client)
    before = fans.get_fan_speed(FansEnum.CHAMBER)
    assert fans.set_fan_speed(FansEnum.CHAMBER, 20)
    assert fans.get_fan_speed(FansEnum.CHAMBER) == before
    client.callback.assert_not_called()
    client.publish.return_value = False
    assert fans.set_fan_speed(FansEnum.CHAMBER, 40) is False
    assert fans.get_fan_speed(FansEnum.CHAMBER) == before


def test_standalone_bundle_validator_runs_without_homeassistant(tmp_path):
    import subprocess
    _write_credentials(tmp_path)
    tool = Path(__file__).parents[2] / "tools/check_signer.py"
    result = subprocess.run([sys.executable, str(tool), str(tmp_path)], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["valid"] is True
    assert "PRIVATE KEY" not in result.stdout + result.stderr
    result = subprocess.run([sys.executable, str(tool), str(tmp_path / "missing")], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"valid": False, "reason": "bundle_missing"}
