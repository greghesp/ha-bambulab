# SPDX-License-Identifier: AGPL-3.0-only
"""Generated credential import/rotation boundaries; never vendor material."""
import json
import os
from pathlib import Path
import stat
import zipfile
from unittest.mock import patch

import pytest
from pybambu.signing import CommandSigner, CommandSigningError
from pybambu.signing_store import (
    BUNDLE_FILE, PEM_FILES, CredentialImportError, import_credentials, signing_directory,
)
from test_signing import _write_credentials, _review_vendor_crl


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / 'source'
    _write_credentials(source)
    archive = tmp_path / 'bundle.zip'
    with zipfile.ZipFile(archive, 'w') as out:
        for name in PEM_FILES:
            out.write(source / name, name)
    target = tmp_path / 'managed' / 'TEST'
    return source, archive, target


def install(bundle):
    source, archive, target = bundle
    return import_credentials(archive, target, trust_roots=(source / 'slicer_cert.pem').read_bytes())


def signer(bundle):
    source, _, target = bundle
    return CommandSigner(target, trust_roots=(source / 'slicer_cert.pem').read_bytes())


def test_import_permissions_and_no_provisioning(bundle):
    _, _, target = bundle
    result = install(bundle)
    assert result['configured'] and not result['ready'] and not result['crl_stale']
    assert sorted(p.name for p in target.iterdir()) == [BUNDLE_FILE]
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    assert stat.S_IMODE((target / BUNDLE_FILE).stat().st_mode) == 0o600
    assert not (target / 'sequence.json').exists()
    assert signer(bundle).configured


def test_renewal_preserves_sequence_and_loaded_generation(bundle):
    _, _, target = bundle
    install(bundle)
    old = signer(bundle)
    first = int(old.build_provision_message()['security']['sequence_id'])
    sequence = (target / 'sequence.json').read_bytes()
    lock_inode = (target / 'sequence.lock').stat().st_ino
    install(bundle)
    assert (target / 'sequence.json').read_bytes() == sequence
    assert (target / 'sequence.lock').stat().st_ino == lock_inode
    assert int(signer(bundle).build_provision_message()['security']['sequence_id']) > first
    assert old.configured  # Already-loaded generation remains coherent until reload.


@pytest.mark.parametrize('kind', ['extra', 'missing', 'duplicate', 'path', 'link', 'oversize', 'garbage'])
def test_invalid_archives_preserve_active_bundle(bundle, kind):
    source, archive, target = bundle
    install(bundle)
    before = (target / BUNDLE_FILE).read_bytes()
    if kind == 'garbage':
        archive.write_bytes(b'not a zip')
    else:
        with zipfile.ZipFile(archive, 'w') as out:
            for name in PEM_FILES:
                if kind == 'missing' and name == PEM_FILES[0]:
                    continue
                member = '../' + name if kind == 'path' else name
                info = zipfile.ZipInfo(member)
                if kind == 'link':
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o600) << 16
                content = (source / name).read_bytes()
                if kind == 'oversize':
                    content = b'x' * (256 * 1024 + 1)
                out.writestr(info, content)
            if kind == 'extra':
                out.writestr('crl_compatibility.json', '{}')
            if kind == 'duplicate':
                with pytest.warns(UserWarning):
                    out.writestr(PEM_FILES[0], 'duplicate')
    with pytest.raises(CredentialImportError, match='signing_invalid_archive'):
        install(bundle)
    assert (target / BUNDLE_FILE).read_bytes() == before
    assert signer(bundle).configured


@pytest.mark.parametrize('problem', ['stale', 'revoked', 'untrusted', 'mismatch'])
def test_crypto_rejection_preserves_existing_credentials(bundle, tmp_path, problem):
    source, archive, target = bundle
    install(bundle)
    before = (target / BUNDLE_FILE).read_bytes()
    bad = tmp_path / 'bad'
    _write_credentials(bad, expired=problem == 'stale', revoked=problem == 'revoked')
    trust = (bad / 'slicer_cert.pem').read_bytes()
    if problem == 'untrusted':
        trust = (source / 'slicer_cert.pem').read_bytes()
    if problem == 'mismatch':
        (bad / 'slicer_key.pem').write_bytes((source / 'slicer_key.pem').read_bytes())
    with zipfile.ZipFile(archive, 'w') as out:
        for name in PEM_FILES:
            out.write(bad / name, name)
    with pytest.raises(CredentialImportError, match='signing_credentials_rejected'):
        import_credentials(archive, target, trust_roots=trust)
    assert (target / BUNDLE_FILE).read_bytes() == before
    assert not list(target.glob('.import-*'))


def test_atomic_replace_failure_preserves_old_snapshot(bundle):
    _, _, target = bundle
    install(bundle)
    before = (target / BUNDLE_FILE).read_bytes()
    with patch('pybambu.signing_store.os.replace', side_effect=OSError('synthetic')):
        with pytest.raises(CredentialImportError, match='signing_storage_error'):
            install(bundle)
    assert (target / BUNDLE_FILE).read_bytes() == before
    assert not list(target.glob('.import-*'))


def test_managed_snapshot_never_falls_back_to_legacy(bundle):
    source, _, target = bundle
    install(bundle)
    for name in PEM_FILES:
        p = target / name
        p.write_bytes((source / name).read_bytes())
        p.chmod(0o600)
    (target / BUNDLE_FILE).write_text('{"files": "bad"}')
    with pytest.raises(CommandSigningError):
        signer(bundle)


@pytest.mark.parametrize('location', ['parent', 'target'])
def test_symlink_directory_rejected(bundle, tmp_path, location):
    _, _, target = bundle
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir(mode=0o700)
    if location == 'parent':
        target.parent.symlink_to(elsewhere, target_is_directory=True)
    else:
        target.parent.mkdir(mode=0o700)
        target.symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(CredentialImportError, match='signing_storage_error'):
        install(bundle)
    assert list(elsewhere.iterdir()) == []


@pytest.mark.parametrize('serial', ['../escape', '/absolute', '', 'a/b', '.', '..', 'x' * 65])
def test_serial_path_traversal_refused(tmp_path, serial):
    with pytest.raises(CredentialImportError):
        signing_directory(tmp_path, serial)

@pytest.mark.parametrize('files', [list(PEM_FILES), None, 1])
def test_malformed_snapshot_shape_fails_closed(bundle, files):
    _, _, target = bundle
    install(bundle)
    (target / BUNDLE_FILE).write_text(json.dumps({'version': 1, 'files': files}))
    with pytest.raises(CommandSigningError):
        signer(bundle)

@pytest.mark.parametrize('managed', [False, True])
def test_standalone_validator_supports_both_layouts_without_secrets(bundle, managed):
    import subprocess
    import sys
    source, _, target = bundle
    if managed:
        install(bundle)
    else:
        target = source
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, str(root / 'tools/check_signer.py'), str(target), '--trust-root', str(source / 'slicer_cert.pem')], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['valid'] is True
    assert 'PRIVATE KEY' not in result.stdout + result.stderr
    assert str(target) not in result.stdout + result.stderr
    missing = subprocess.run([sys.executable, str(root / 'tools/check_signer.py'), str(target / 'absent')], capture_output=True, text=True, check=False)
    assert missing.returncode == 1
    assert json.loads(missing.stdout) == {'valid': False, 'reason': 'bundle_missing'}
