# SPDX-License-Identifier: AGPL-3.0-only
"""Real HA form/repair classes with mocked transport; no accounts or hardware."""
import asyncio
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
pytest.importorskip('homeassistant')
from homeassistant.data_entry_flow import FlowResultType
from custom_components.bambu_lab.config_flow import BambuLabFlowHandler, BambuOptionsFlowHandler
from custom_components.bambu_lab.pybambu.bambu_cloud import (
    CodeRequiredError, CodeIncorrectError, CodeExpiredError, TfaCodeRequiredError,
)
from custom_components.bambu_lab.pybambu.signing_store import CredentialImportError
from custom_components.bambu_lab.repairs import SigningRepairFlow, async_create_fix_flow


@pytest.fixture
def entry():
    return SimpleNamespace(entry_id='entry-test', domain='bambu_lab',
        data={'serial': 'TEST', 'device_type': 'X1C'},
        options={'region': 'Europe', 'email': 'fixture@example.invalid', 'username': 'fixture',
                 'auth_token': 'fixture-token', 'host': 'fixture.invalid', 'local_mqtt': True,
                 'disable_ssl_verify': False, 'enable_signed_fans': False})


def setup_flow(flow, tmp_path):
    hass = MagicMock()
    hass.data = {}
    async def executor(fn, *args):
        return fn(*args)
    hass.async_add_executor_job = AsyncMock(side_effect=executor)
    hass.config.path.side_effect = lambda *args: str(tmp_path.joinpath(*args))
    hass.config_entries.async_reload = AsyncMock(return_value=True)
    flow.hass = hass
    flow.context = {}
    return hass


def test_options_menu_does_not_attempt_login(entry, tmp_path):
    async def run():
        flow = BambuOptionsFlowHandler(entry)
        setup_flow(flow, tmp_path)
        flow._bambu_cloud.test_authentication = MagicMock(side_effect=AssertionError('network'))
        result = await flow.async_step_init()
        assert result['type'] == FlowResultType.MENU
        assert result['menu_options'] == ['connection', 'signed_fans']
    asyncio.run(run())


@pytest.mark.parametrize('flow_type', [BambuOptionsFlowHandler, SigningRepairFlow])
@pytest.mark.parametrize('consent', [True, False, 'true', 1])
def test_import_consent_cleanup_and_preserved_connection(entry, tmp_path, flow_type, consent):
    async def run():
        flow = flow_type(entry)
        hass = setup_flow(flow, tmp_path)
        seen = []
        @contextmanager
        def uploaded(hass, file_id):
            assert file_id == 'opaque-id'
            try:
                yield tmp_path / 'fixture.zip'
            finally:
                seen.append('cleaned')
        with patch('custom_components.bambu_lab.signing_flow.process_uploaded_file', uploaded), patch('custom_components.bambu_lab.signing_flow.import_credentials') as importer:
            result = await flow.async_step_signing_import({'credential_bundle': 'opaque-id', 'consent': consent})
        assert seen == ['cleaned']
        if consent is True:
            importer.assert_called_once()
            options = hass.config_entries.async_update_entry.call_args.kwargs['options']
            assert options == {**entry.options, 'enable_signed_fans': True}
            hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)
            assert result['type'] == FlowResultType.CREATE_ENTRY
            # None is deliberate: OptionsFlow must not replace the entry with {}.
            assert result['data'] is None
        else:
            importer.assert_not_called()
            hass.config_entries.async_update_entry.assert_not_called()
            assert result['errors'] == {'base': 'signing_consent_required'}
    asyncio.run(run())


def test_failed_import_leaves_enabled_entry_and_options_untouched(entry, tmp_path):
    async def run():
        entry.options['enable_signed_fans'] = True
        flow = BambuOptionsFlowHandler(entry)
        hass = setup_flow(flow, tmp_path)
        @contextmanager
        def uploaded(*args):
            yield tmp_path / 'fixture.zip'
        with patch('custom_components.bambu_lab.signing_flow.process_uploaded_file', uploaded), patch('custom_components.bambu_lab.signing_flow.import_credentials', side_effect=CredentialImportError('signing_credentials_rejected')):
            result = await flow.async_step_signing_import({'credential_bundle': 'id', 'consent': True})
        assert result['errors'] == {'base': 'signing_credentials_rejected'}
        hass.config_entries.async_update_entry.assert_not_called()
        hass.config_entries.async_reload.assert_not_called()
    asyncio.run(run())


@pytest.mark.parametrize('configured,stale', [(False, False), (True, True)])
def test_retry_refuses_invalid_or_stale_material(entry, tmp_path, configured, stale):
    async def run():
        flow = BambuOptionsFlowHandler(entry)
        hass = setup_flow(flow, tmp_path)
        flow._signing_status = AsyncMock(return_value={'configured': configured, 'crl_stale': stale})
        result = await flow.async_step_signing_retry({'consent': True})
        assert result['errors'] == {'base': 'signing_credentials_rejected'}
        hass.config_entries.async_reload.assert_not_called()
    asyncio.run(run())


def test_disable_preserves_connection_and_credentials(entry, tmp_path):
    async def run():
        flow = BambuOptionsFlowHandler(entry)
        hass = setup_flow(flow, tmp_path)
        with patch('custom_components.bambu_lab.signing_flow.ir.async_delete_issue') as delete:
            await flow.async_step_signing_disable({})
        assert hass.config_entries.async_update_entry.call_args.kwargs['options'] == entry.options
        delete.assert_called_once_with(hass, 'bambu_lab', 'signing_entry-test')
        assert not list(tmp_path.iterdir())
    asyncio.run(run())


def test_unsupported_model_cannot_import(entry, tmp_path):
    async def run():
        entry.data['device_type'] = 'P1S'
        flow = BambuOptionsFlowHandler(entry)
        hass = setup_flow(flow, tmp_path)
        result = await flow.async_step_signing_import({'credential_bundle': 'id', 'consent': True})
        assert result['reason'] == 'signing_unsupported'
        hass.async_add_executor_job.assert_not_called()
    asyncio.run(run())


def test_repair_owned_by_exact_entry(entry):
    async def run():
        hass = MagicMock()
        hass.config_entries.async_get_entry.return_value = entry
        assert isinstance(await async_create_fix_flow(hass, 'signing_entry-test', {'entry_id': entry.entry_id}), SigningRepairFlow)
        assert await async_create_fix_flow(hass, 'signing_other', {'entry_id': entry.entry_id}) is None
    asyncio.run(run())


def test_cloud_printer_missing_does_not_select_last_device(entry, tmp_path):
    async def run():
        flow = BambuOptionsFlowHandler(entry)
        hass = setup_flow(flow, tmp_path)
        flow._bambu_cloud.get_device_list = MagicMock(return_value=[{'dev_id': 'OTHER', 'name': 'Other', 'dev_access_code': 'fixture'}])
        with patch('custom_components.bambu_lab.config_flow.BambuClient') as client:
            result = await flow.async_step_Bambu_Lan()
        assert result['type'] == FlowResultType.ABORT
        assert result['reason'] == 'device_not_found'
        client.assert_not_called()
        hass.config_entries.async_update_entry.assert_not_called()
    asyncio.run(run())


@pytest.mark.parametrize('flow_type', [BambuLabFlowHandler, BambuOptionsFlowHandler])
@pytest.mark.parametrize('challenge,field', [(CodeRequiredError, 'verifyCode'), (TfaCodeRequiredError, 'tfaCode')])
def test_login_requests_challenge_and_continues(entry, tmp_path, flow_type, challenge, field):
    async def run():
        flow = flow_type(entry) if flow_type is BambuOptionsFlowHandler else flow_type()
        setup_flow(flow, tmp_path)
        flow._bambu_cloud.login = MagicMock(side_effect=challenge())
        next_step = 'async_step_Bambu_Lan' if flow_type is BambuOptionsFlowHandler else 'async_step_Bambu_Choose_Device'
        setattr(flow, next_step, AsyncMock(return_value={'next': True}))
        result = await flow.async_step_Bambu({'region': 'Europe', 'email': 'fixture@example.invalid', 'password': 'SENSITIVE-fixture'})
        assert result['errors']['base'] == field
        assert 'password' not in result['data_schema'].schema
        method = 'login_with_verification_code' if field == 'verifyCode' else 'login_with_2fa_code'
        setattr(flow._bambu_cloud, method, MagicMock())
        result = await flow.async_step_Bambu({field: '123456'})
        assert result == {'next': True}
    asyncio.run(run())


@pytest.mark.parametrize('error,reason', [(CodeIncorrectError, 'code_incorrect'), (CodeExpiredError, 'code_expired')])
def test_code_failure_can_request_new_code(entry, tmp_path, error, reason):
    async def run():
        flow = BambuOptionsFlowHandler(entry)
        setup_flow(flow, tmp_path)
        flow.authentication_type = 'verifyCode'
        flow._bambu_cloud.login_with_verification_code = MagicMock(side_effect=error())
        result = await flow.async_step_Bambu({'verifyCode': '123456'})
        assert result['errors']['base'] == reason
        flow._bambu_cloud.request_new_code = MagicMock()
        result = await flow.async_step_Bambu({'newCode': True})
        flow._bambu_cloud.request_new_code.assert_called_once()
        assert result['step_id'] == 'Bambu'
    asyncio.run(run())

@pytest.mark.parametrize('flow_type', [BambuLabFlowHandler, BambuOptionsFlowHandler])
def test_failed_login_does_not_echo_password_or_exception(entry, tmp_path, flow_type, caplog):
    async def run():
        flow = flow_type(entry) if flow_type is BambuOptionsFlowHandler else flow_type()
        setup_flow(flow, tmp_path)
        flow._bambu_cloud.login = MagicMock(side_effect=RuntimeError('SENSITIVE-fixture'))
        result = await flow.async_step_Bambu({'region': 'Europe', 'email': 'fixture@example.invalid', 'password': 'SENSITIVE-fixture'})
        assert result['errors']['base'] == 'cannot_connect'
        password_marker = next(k for k in result['data_schema'].schema if str(k) == 'password')
        assert password_marker.default() == ''
        assert 'SENSITIVE-fixture' not in caplog.text
    asyncio.run(run())


def test_unsupported_existing_entry_still_offers_disable(entry, tmp_path):
    async def run():
        entry.data['device_type'] = 'P1S'
        entry.options['enable_signed_fans'] = True
        flow = BambuOptionsFlowHandler(entry)
        setup_flow(flow, tmp_path)
        flow._signing_status = AsyncMock(return_value={'configured': False, 'reason': 'credentials_missing'})
        result = await flow.async_step_signed_fans()
        assert result['menu_options'] == ['signing_disable']
    asyncio.run(run())


def test_failed_reload_is_reported_and_disable_applies_beforehand(entry, tmp_path):
    async def run():
        flow = BambuOptionsFlowHandler(entry)
        hass = setup_flow(flow, tmp_path)
        client = MagicMock()
        hass.data = {'bambu_lab': {entry.entry_id: SimpleNamespace(client=client)}}
        async def reload(entry_id):
            client.disable_signing.assert_called_once()
            return False
        hass.config_entries.async_reload.side_effect = reload
        with patch('custom_components.bambu_lab.signing_flow.ir.async_delete_issue'), patch('custom_components.bambu_lab.signing_flow.ir.async_create_issue') as create:
            result = await flow.async_step_signing_disable({})
        assert result['type'] == FlowResultType.ABORT
        assert result['reason'] == 'signing_reload_failed'
        assert create.call_args.kwargs['is_fixable']
        client.publish.assert_not_called()
    asyncio.run(run())
