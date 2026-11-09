# SPDX-License-Identifier: AGPL-3.0-only
"""Generated, independently anchored application-chain negative tests."""
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pybambu.signing import CommandSigner, CommandSigningError
from test_signing import _write_credentials


def cert(key, name, issuer_key, issuer_name, *, ca=False, path_length=None,
         can_sign=True, expired=False):
    now = datetime.now(timezone.utc)
    return (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)]))
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2))
            .not_valid_after(now + timedelta(days=-1 if expired else 10))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=path_length), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                key_encipherment=not ca, data_encipherment=False, key_agreement=False,
                key_cert_sign=ca and can_sign, crl_sign=ca and can_sign,
                encipher_only=None, decipher_only=None), critical=True)
            .sign(issuer_key, hashes.SHA256()))


@pytest.fixture
def chain():
    keys = [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(3)]
    root = cert(keys[0], 'root', keys[0], 'root', ca=True, path_length=1)
    intermediate = cert(keys[1], 'intermediate', keys[0], 'root', ca=True, path_length=0)
    leaf = cert(keys[2], 'app', keys[1], 'intermediate')
    signer = CommandSigner(None, trust_roots=root.public_bytes(serialization.Encoding.PEM))
    return signer, [leaf, intermediate, root], keys


def test_complete_path_reaches_independent_anchor(chain):
    signer, certificates, _ = chain
    # Root need not be supplied by the bundle. The independent anchor is used.
    assert signer._validate_app_chain(certificates[:2]) == certificates


def test_untrusted_supplied_root_is_not_an_anchor(chain):
    signer, certificates, keys = chain
    rogue_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue = cert(rogue_key, 'rogue', rogue_key, 'rogue', ca=True)
    signer._trust_roots = [rogue]
    with pytest.raises(CommandSigningError):
        signer._validate_app_chain(certificates)


def test_incomplete_path_fails(chain):
    signer, certificates, _ = chain
    with pytest.raises(CommandSigningError):
        signer._validate_app_chain(certificates[:1])


@pytest.mark.parametrize('ca,can_sign,expired', [(False, True, False), (True, False, False), (True, True, True)])
def test_issuer_constraints_and_dates_fail_closed(chain, ca, can_sign, expired):
    signer, certificates, keys = chain
    certificates[1] = cert(keys[1], 'intermediate', keys[0], 'root', ca=ca,
                           can_sign=can_sign, expired=expired)
    with pytest.raises(CommandSigningError):
        signer._validate_app_chain(certificates)


def test_root_path_length_enforced(chain):
    signer, certificates, keys = chain
    root = cert(keys[0], 'root', keys[0], 'root', ca=True, path_length=0)
    signer._trust_roots = [root]
    with pytest.raises(CommandSigningError):
        signer._validate_app_chain(certificates[:2])


def test_wrong_key_with_same_issuer_name_fails(chain):
    signer, certificates, keys = chain
    impostor_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    certificates[1] = cert(impostor_key, 'intermediate', keys[0], 'root', ca=True)
    with pytest.raises(CommandSigningError):
        signer._validate_app_chain(certificates)


def test_unrelated_bundle_certificate_is_not_a_crl_issuer(chain):
    signer, certificates, _ = chain
    rogue_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue = cert(rogue_key, 'intermediate', rogue_key, 'intermediate', ca=True)
    verified = signer._validate_app_chain([certificates[0], rogue, *certificates[1:]])
    assert rogue not in verified
    assert verified == certificates


def test_generated_bundle_is_not_trusted_without_explicit_anchor(tmp_path):
    _write_credentials(tmp_path)
    with pytest.raises(CommandSigningError, match='trusted issuer'):
        CommandSigner(tmp_path)


def test_unhandled_critical_extension_is_refused(chain):
    signer, certificates, keys = chain
    now = datetime.now(timezone.utc)
    root = (x509.CertificateBuilder().subject_name(certificates[2].subject)
            .issuer_name(certificates[2].issuer).public_key(keys[0].public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1))
            .not_valid_after(now+timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True,path_length=1),critical=True)
            .add_extension(x509.UnrecognizedExtension(x509.ObjectIdentifier('1.2.3.4.5'),b'\x05\x00'),critical=True)
            .sign(keys[0],hashes.SHA256()))
    signer._trust_roots = [root]
    with pytest.raises(CommandSigningError, match='unsupported critical'):
        signer._validate_app_chain(certificates[:2])
