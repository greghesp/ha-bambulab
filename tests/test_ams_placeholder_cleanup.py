"""AMS devices registered without a serial are removed from every printer (issue #1938).

Older versions registered an AMS whose serial was not known yet under a placeholder identifier.
That identifier is the same for every printer, so one device was shown under all of them, named
after whichever printer registered it last.

Run in a Home Assistant Python environment; skips when Home Assistant is absent.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import coordinator as coordinator_module
from custom_components.bambu_lab.const import DOMAIN
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator

ENTRY_ID = "entry_x6"


def _device(device_id, serial, model, name="X1C_X6SERIAL_AMS_1"):
    return SimpleNamespace(
        id=device_id, identifiers={(DOMAIN, serial)}, model=model, name=name)


@pytest.fixture
def removed_devices(monkeypatch):
    """Return a function running _printer_ready and giving back the ids of the removed devices."""

    def run(devices, *, attached=("AMSSERIAL",), resolved=True):
        registry = MagicMock()
        monkeypatch.setattr(coordinator_module.device_registry, "async_get", lambda hass: registry)
        monkeypatch.setattr(
            coordinator_module.device_registry, "async_entries_for_config_entry",
            lambda reg, entry_id: devices if entry_id == ENTRY_ID else [])

        model = MagicMock()
        model.ams.data = {index: SimpleNamespace(serial=serial)
                          for index, serial in enumerate(attached)}
        model.ams_identities_resolved = resolved

        coordinator = object.__new__(BambuDataUpdateCoordinator)
        coordinator._hass = coordinator.hass = MagicMock()
        coordinator.config_entry = SimpleNamespace(
            entry_id=ENTRY_ID, data={"serial": "X6SERIAL", "device_type": "X1C"})
        coordinator.client = MagicMock()
        coordinator.client.get_device.return_value = model
        coordinator._reinitialize_sensors = MagicMock()

        coordinator._printer_ready()
        return [call.args[0] for call in registry.async_remove_device.call_args_list]

    return run


def test_placeholder_named_after_this_printer_is_removed(removed_devices):
    assert removed_devices([_device("ghost", "", "Unknown")]) == ["ghost"]


def test_placeholder_named_after_another_printer_is_removed(removed_devices):
    ghost = _device("ghost", "", "Unknown", name="H2D_H3SERIAL_AMS_1")

    assert removed_devices([ghost]) == ["ghost"]


def test_placeholder_is_removed_while_an_ams_is_still_unidentified(removed_devices):
    devices = [_device("blank", "", "Unknown"), _device("na", "N/A", "AMS 2 Pro")]

    assert removed_devices(devices, attached=("",), resolved=False) == ["blank", "na"]


def test_attached_ams_is_kept(removed_devices):
    assert removed_devices([_device("ams", "AMSSERIAL", "AMS")]) == []


def test_unattached_ams_is_kept_while_an_ams_is_still_unidentified(removed_devices):
    ams = _device("ams", "AMSSERIAL", "AMS")

    assert removed_devices([ams], attached=("",), resolved=False) == []


def test_unattached_ams_is_removed_once_every_ams_is_identified(removed_devices):
    assert removed_devices([_device("ams", "OTHERSERIAL", "AMS")]) == ["ams"]


def test_devices_that_are_not_an_ams_are_kept(removed_devices):
    devices = [
        _device("printer", "X6SERIAL", "X1C", name="X1C_X6SERIAL"),
        _device("spool", "X6SERIAL_ExternalSpool", "External Spool"),
        _device("unknown", "SOMESERIAL", "Unknown"),
        _device("purifier", "N/A", "E1 Air Purifier", name="X1C_X6SERIAL_AirPurifier"),
    ]

    assert removed_devices(devices) == []
