"""A rename reported by the printer reaches the config entry (issue #2039).

Run in a Home Assistant Python environment; skips when Home Assistant is absent.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator
from custom_components.bambu_lab.definitions import PRINTER_SENSORS

OPTIONS = {"name": "A11_P12", "host": "192.0.2.1", "usage_hours": 12.5}


@pytest.fixture
def coordinator():
    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._shutdown = False
    entry = SimpleNamespace(data={"serial": "TESTSERIAL"}, options=dict(OPTIONS))

    def update_entry(entry, *, options):
        entry.options = options

    coordinator._hass = MagicMock()
    coordinator._hass.config_entries.async_update_entry.side_effect = update_entry
    coordinator.config_entry = entry
    coordinator.client = MagicMock()
    coordinator._update_data = MagicMock()
    return coordinator


def _report_name(coordinator, name):
    coordinator.client.get_device().info.name = name
    coordinator.event_handler_internal("event_printer_name_update")


def _sensor_value(coordinator):
    description = next(d for d in PRINTER_SENSORS if d.key == "name")
    return description.value_fn(SimpleNamespace(coordinator=coordinator))


def test_rename_changes_the_printer_name_sensor(coordinator):
    _report_name(coordinator, "A31_P12")

    assert _sensor_value(coordinator) == "A31_P12"
    coordinator._update_data.assert_called_once_with()


def test_rename_keeps_the_other_options(coordinator):
    _report_name(coordinator, "A31_P12")

    assert coordinator.config_entry.options == {**OPTIONS, "name": "A31_P12"}


def test_unchanged_name_does_not_write_the_config_entry(coordinator):
    _report_name(coordinator, "A11_P12")

    coordinator._hass.config_entries.async_update_entry.assert_not_called()
