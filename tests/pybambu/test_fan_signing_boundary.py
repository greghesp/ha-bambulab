# SPDX-License-Identifier: AGPL-3.0-only
"""Credential-free fan-only contract: generated certificates, no network."""
import base64
import json
import math
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric import padding

from pybambu.bambu_client import BambuClient
from pybambu.const import FansEnum
from pybambu.signing import CommandSigner, CommandSigningError
from test_signing import _make_ready, _write_credentials


@pytest.fixture
def ready(tmp_path):
    _write_credentials(tmp_path)
    signer = CommandSigner(tmp_path)
    key, _ = _make_ready(signer)
    return signer, key


@pytest.mark.parametrize('fan_id', [1, 2, 3])
@pytest.mark.parametrize('percentage', [0, 10, 25, 50, 100])
def test_canonical_fan_only_ciphertext(ready, fan_id, percentage):
    signer, key = ready
    envelope = json.loads(signer.sign_fan_command(fan_id, percentage))
    assert set(envelope) == {'header', 'print'}
    assert set(envelope['print']) == {'command', 'sequence_id', 'param_enc'}
    plain = key.decrypt(base64.b64decode(envelope['print']['param_enc']), padding.PKCS1v15())
    speed = math.ceil(255 * (round(percentage / 10) * 10) / 100)
    assert plain == f'M106 P{fan_id} S{speed}\n'.encode()


@pytest.mark.parametrize('fan_id,percentage', [
    (0, 20), (4, 20), (5, 20), (10, 20), (True, 20), ('3', 20),
    ('3 S0\nM104 S300', 20), (3, True), (3, -1), (3, 101),
    (3, float('nan')), (3, float('inf')), (3, float('-inf')),
    (3, 10**400), (3, '20'), (3, '0\nG28'), (3, {'print': {'command': 'stop'}}),
])
def test_invalid_request_reserves_no_sequence(ready, tmp_path, fan_id, percentage):
    signer, _ = ready
    before = (tmp_path / 'sequence.json').read_bytes()
    with pytest.raises(CommandSigningError):
        signer.sign_fan_command(fan_id, percentage)
    assert (tmp_path / 'sequence.json').read_bytes() == before
    assert not signer._pending_commands


@pytest.mark.parametrize('payload', [
    {'print': {'command': 'gcode_line', 'param': 'M106 P3 S0\n'}},
    {'print': {'command': 'gcode_line', 'param': 'M106 P3 S0\nM104 S300\n'}},
    {'print': {'command': 'gcode_line', 'param_enc': 'opaque'}},
    {'print': {'command': 'project_file', 'url': 'https://example.invalid/job'}},
    {'print': {'command': 'pause'}}, {'print': {'command': 'print_speed', 'param': '2'}},
    {'print': None}, {'print': [], 'system': {'command': 'ledctrl'}},
])
def test_generic_print_payload_cannot_reach_signer_or_transport(payload):
    client = BambuClient({'host': '', 'serial': 'TEST-SERIAL'})
    client.get_device().print_fun._encryption_enabled = True
    client.client = MagicMock()
    client.command_signer = MagicMock()
    assert client.publish(payload) is False
    client.command_signer.sign_fan_command.assert_not_called()
    client.client.publish.assert_not_called()


@pytest.mark.parametrize('secured', [False, True])
def test_read_only_and_light_traffic_remain_unsigned(secured):
    from pybambu.commands import GET_VERSION, PUSH_ALL, START_PUSH, CHAMBER_LIGHT_ON
    client = BambuClient({'host': '', 'serial': 'TEST-SERIAL'})
    client.get_device().print_fun._encryption_enabled = secured
    client.client = MagicMock()
    client.client.publish.return_value.rc = 0
    client.command_signer = MagicMock()
    for message in (GET_VERSION, PUSH_ALL, START_PUSH, CHAMBER_LIGHT_ON):
        assert client.publish(message)
        assert json.loads(client.client.publish.call_args.args[1]) == message
    client.command_signer.sign_fan_command.assert_not_called()


def test_unsigned_generic_print_behavior_is_unchanged():
    client = BambuClient({'host': '', 'serial': 'TEST-SERIAL'})
    client.get_device().print_fun._encryption_enabled = False
    client.client = MagicMock()
    client.client.publish.return_value.rc = 0
    message = {'print': {'command': 'pause'}}
    assert client.publish(message)
    assert json.loads(client.client.publish.call_args.args[1]) == message


@pytest.mark.parametrize('fan', [FansEnum.HEATBREAK, FansEnum.SECONDARY_AUXILIARY, 3, '3'])
def test_typed_client_rejects_unsupported_fans(fan):
    client = BambuClient({'host': '', 'serial': 'TEST-SERIAL'})
    client.client = MagicMock()
    client.command_signer = MagicMock()
    assert client.publish_fan(fan, 20) is False
    client.client.publish.assert_not_called()
    client.command_signer.sign_fan_command.assert_not_called()


def test_broker_failure_is_not_success_or_replay(ready):
    signer, _ = ready
    client = BambuClient({'host': '', 'serial': 'TEST-SERIAL'})
    client.command_signer = signer
    client.client = MagicMock()
    client.client.publish.return_value.rc = 4
    assert client.publish_fan(FansEnum.CHAMBER, 20) is False
    client.client.publish.assert_called_once()
    signer.reset_session()
    assert not signer.ready
    # Neither disconnect nor a new provisioning request resends the fan action.
    signer.build_provision_message()
    client.client.publish.assert_called_once()
