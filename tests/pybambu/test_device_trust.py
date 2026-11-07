# SPDX-License-Identifier: AGPL-3.0-only
"""Independent device CA and exact identity checks, with generated peers."""
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pybambu.signing import CommandSigningError
from test_signing import _write_credentials, _test_signer, _device_certificate, _certificate


@pytest.mark.parametrize('problem', ['wrong_serial', 'untrusted', 'expired', 'missing_identity', 'oversize', 'malformed'])
def test_device_reply_rejected_and_session_invalidated(tmp_path, problem):
    _write_credentials(tmp_path)
    signer = _test_signer(tmp_path)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = _device_certificate(key, 'OTHER' if problem == 'wrong_serial' else 'TEST-SERIAL', expired=problem == 'expired')
    if problem == 'untrusted':
        cert = _certificate(key, 'TEST-SERIAL')
    if problem == 'missing_identity':
        signer._expected_serial = None
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    if problem == 'oversize':
        pem = 'x' * (64 * 1024 + 1)
    if problem == 'malformed':
        pem = 'not a certificate'
    request = signer.build_provision_message()['security']
    with pytest.raises(CommandSigningError, match='trust validation failed'):
        signer.handle_security_report({'command': 'app_cert_install', 'sequence_id': request['sequence_id'], 'result': 'SUCCESS', 'printer_cert': pem})
    assert not signer.ready and signer._device_public_key is None
    assert signer.status()['reason'] == 'device_trust_failed'
    with pytest.raises(CommandSigningError):
        signer.sign_fan_command(3, 20)
    assert not signer._pending_commands


def test_valid_peer_after_rejection_requires_new_correlated_exchange(tmp_path):
    _write_credentials(tmp_path)
    signer = _test_signer(tmp_path)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    old = signer.build_provision_message()['security']['sequence_id']
    with pytest.raises(CommandSigningError):
        signer.handle_security_report({'command': 'app_cert_install', 'sequence_id': old, 'result': 'SUCCESS', 'printer_cert': 'bad'})
    valid = _device_certificate(key).public_bytes(serialization.Encoding.PEM).decode()
    assert not signer.handle_security_report({'command': 'app_cert_install', 'sequence_id': old, 'result': 'SUCCESS', 'printer_cert': valid})
    new = signer.build_provision_message()['security']['sequence_id']
    assert new != old
    assert signer.handle_security_report({'command': 'app_cert_install', 'sequence_id': new, 'result': 'SUCCESS', 'printer_cert': valid})
    assert signer.ready and signer.status()['reason'] == 'ready'
    assert not signer._pending_commands
