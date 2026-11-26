"""Controls go away when the printer starts requiring signed commands (issue #1851).

Run in a Home Assistant Python environment; skips when Home Assistant is absent.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import coordinator as coordinator_module
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator
from custom_components.bambu_lab.pybambu.models import PrintFun

DEVELOPER_MODE_OFF = {"flag3": 0x229F}  # A1 mini on 01.07.02.00, from issue #1851
DEVELOPER_MODE_ON = {"flag3": 0x228F}


@pytest.fixture
def coordinator(monkeypatch):
    for registry in (coordinator_module.device_registry, coordinator_module.issue_registry):
        monkeypatch.setattr(registry, "async_get", MagicMock())
    monkeypatch.setattr(coordinator_module.device_registry, "async_entries_for_config_entry", lambda *_: [])

    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._shutdown = False
    coordinator._controls_set_up = False
    coordinator._hass = coordinator.hass = MagicMock()
    coordinator.config_entry = SimpleNamespace(
        entry_id="entry", data={"serial": "TESTSERIAL", "device_type": "A1MINI"}, options={})
    coordinator.client = MagicMock()
    coordinator.client.get_device().ams.data = {}
    coordinator._reinitialize_sensors = MagicMock()
    # event_printer_ready queues a serialized reinitialize pass (#2341).
    coordinator._request_reinitialize = MagicMock()
    return coordinator


@pytest.fixture
def print_fun(coordinator):
    """The real detection, delivering its events to the coordinator."""
    return PrintFun(client=SimpleNamespace(callback=coordinator.event_handler_internal))


def _printer_ready(coordinator):
    coordinator.event_handler_internal("event_printer_ready")
    coordinator._reinitialize_sensors.reset_mock()
    coordinator._request_reinitialize.reset_mock()


def test_turning_developer_mode_off_rebuilds_the_entities(coordinator, print_fun):
    print_fun.print_update(DEVELOPER_MODE_ON)
    _printer_ready(coordinator)

    print_fun.print_update(DEVELOPER_MODE_OFF)

    coordinator._reinitialize_sensors.assert_called_once_with()


def test_startup_with_developer_mode_off_sets_up_the_entities_once(coordinator, print_fun):
    print_fun.print_update(DEVELOPER_MODE_OFF)
    coordinator.event_handler_internal("event_printer_ready")

    # Only the setup requested by printer ready, no extra pass for the encryption requirement.
    coordinator._reinitialize_sensors.assert_not_called()
    coordinator._request_reinitialize.assert_called_once_with()


def test_unchanged_requirement_does_not_rebuild_again(coordinator, print_fun):
    print_fun.print_update(DEVELOPER_MODE_OFF)
    _printer_ready(coordinator)

    print_fun.print_update(DEVELOPER_MODE_OFF)
    print_fun.print_update({"gcode_state": "RUNNING"})

    coordinator._reinitialize_sensors.assert_not_called()
