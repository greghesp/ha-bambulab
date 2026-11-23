"""Printers report a rename (issue #2039) in an "update" message on their report topic.

The success payload is the one captured from an H2D renamed through Bambu Cloud:
https://github.com/Doridian/OpenBambuAPI/issues/46#issuecomment-4000706853
"""
import json
from types import SimpleNamespace

import pytest

from pybambu.bambu_client import BambuClient

RENAME_EVENT = "event_printer_name_update"


@pytest.fixture
def client():
    client = BambuClient({"serial": "TESTSERIAL", "device_type": "P1S", "host": "", "local_mqtt": True})
    client.client = object()  # A connected paho client; on_message drops messages without one.
    client._loaded_slicer_settings = True
    client.events = []
    client._callback = client.events.append
    return client


def _receive(client, payload):
    client.on_message(None, None, SimpleNamespace(payload=json.dumps(payload).encode()))


def _rename(**fields):
    return {"update": {"name": "A31_P12", "reason": "success", "result": "success", "sequence_id": "0", **fields}}


def test_rename_updates_the_name_and_signals_it(client):
    _receive(client, _rename())

    assert client.get_device().info.name == "A31_P12"
    assert client.events.count(RENAME_EVENT) == 1


def test_rename_keeps_non_ascii_names(client):
    _receive(client, _rename(name="3Д принтерик"))

    assert client.get_device().info.name == "3Д принтерик"


def test_result_is_not_case_sensitive(client):
    _receive(client, _rename(result="SUCCESS"))

    assert client.get_device().info.name == "A31_P12"


@pytest.mark.parametrize("fields", [
    {"result": "fail", "reason": "fail"},
    {"result": None},
    {"name": ""},
    {"name": "   "},
    {"name": None},
    {"name": 5},
])
def test_failed_or_nameless_updates_are_ignored(client, fields):
    _receive(client, _rename(**fields))

    assert client.get_device().info.name is None
    assert RENAME_EVENT not in client.events


@pytest.mark.parametrize("update", ["A31_P12", ["A31_P12"], {}, {"sequence_id": "0"}])
def test_unexpected_update_payloads_are_ignored(client, update, caplog):
    _receive(client, {"update": update})

    assert client.get_device().info.name is None
    assert RENAME_EVENT not in client.events
    assert "An exception occurred" not in caplog.text
