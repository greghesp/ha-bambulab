# SPDX-License-Identifier: AGPL-3.0-only
"""Entry-scoped lifecycle repairs, including expired credentials while offline."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
pytest.importorskip('homeassistant')
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator


def coordinator(reason, enabled=True, **fields):
    obj = BambuDataUpdateCoordinator.__new__(BambuDataUpdateCoordinator)
    obj._hass = MagicMock()
    obj._shutdown = False
    obj._last_signing_issue = None
    obj._entry = SimpleNamespace(entry_id='fixture', options={'enable_signed_fans': enabled})
    obj.client = MagicMock()
    obj.client.signing_status.return_value = {'reason': reason, 'configured': False, 'valid_until': None, **fields}
    return obj


@pytest.mark.parametrize('reason', ['credentials_missing', 'credentials_invalid', 'credentials_expired', 'provisioning_required', 'device_trust_failed'])
def test_unavailable_signer_creates_owned_fixable_issue(reason):
    obj = coordinator(reason)
    with patch('custom_components.bambu_lab.coordinator.issue_registry.async_create_issue') as create:
        obj._sync_signing_issue()
    assert create.call_args.args == (obj._hass, 'bambu_lab', 'signing_fixture')
    assert create.call_args.kwargs['is_fixable'] is True
    assert create.call_args.kwargs['data'] == {'entry_id': 'fixture'}
    obj.client.publish.assert_not_called()


def test_upcoming_expiry_creates_renewal_issue():
    obj = coordinator('ready', configured=True, review_due=True, valid_until='fixture-deadline')
    with patch('custom_components.bambu_lab.coordinator.issue_registry.async_create_issue') as create:
        obj._sync_signing_issue()
    assert create.call_args.kwargs['translation_placeholders']['reason'] == 'renewal due'


@pytest.mark.parametrize('enabled,reason', [(True, 'ready'), (False, 'credentials_missing')])
def test_disabled_or_ready_clears_only_own_issue(enabled, reason):
    obj = coordinator(reason, enabled=enabled)
    with patch('custom_components.bambu_lab.coordinator.issue_registry.async_delete_issue') as delete:
        obj._sync_signing_issue()
    delete.assert_called_once_with(obj._hass, 'bambu_lab', 'signing_fixture')


def test_completed_but_unresolved_repair_reappears():
    obj = coordinator('provisioning_required')
    with patch('custom_components.bambu_lab.coordinator.issue_registry.async_create_issue') as create, patch('custom_components.bambu_lab.coordinator.issue_registry.async_get') as registry:
        obj._sync_signing_issue()
        registry.return_value.async_get_issue.return_value = object()
        obj._sync_signing_issue()
        assert create.call_count == 1
        registry.return_value.async_get_issue.return_value = None
        obj._sync_signing_issue()
        assert create.call_count == 2
