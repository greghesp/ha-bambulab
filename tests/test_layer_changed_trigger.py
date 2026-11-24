"""Layer changed device trigger checks in a Home Assistant environment."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab.const import DOMAIN
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator
from custom_components.bambu_lab.device_trigger import TRIGGER_SCHEMA, TRIGGER_TYPES, async_get_triggers

EVENT = "event_print_layer_changed"
TRANSLATIONS = Path(__file__).parents[1] / "custom_components" / "bambu_lab" / "translations" / "en.json"


@pytest.fixture
def coordinator():
    # Run the real event handling methods on a stub so no printer connection is needed.
    stub = MagicMock()
    stub._shutdown = False
    stub.get_ha_printer_device.return_value = SimpleNamespace(id="device-id")
    stub.config_entry.options = {"name": "Printer"}
    stub.get_model().print_job = SimpleNamespace(current_layer=5, total_layers=70)
    stub.PublishDeviceTriggerEvent = lambda *args, **kwargs: (
        BambuDataUpdateCoordinator.PublishDeviceTriggerEvent(stub, *args, **kwargs)
    )
    return stub


def test_trigger_needs_no_above_or_below():
    triggers = asyncio.run(async_get_triggers(MagicMock(), "device-id"))
    trigger = next(t for t in triggers if t["type"] == EVENT)
    TRIGGER_SCHEMA({k: v for k, v in trigger.items() if k != "metadata"})


def test_event_carries_the_layer(coordinator):
    BambuDataUpdateCoordinator.event_handler_internal(coordinator, EVENT)
    coordinator._hass.bus.async_fire.assert_called_once_with(
        f"{DOMAIN}_event",
        {"device_id": "device-id", "name": "Printer", "type": EVENT, "layer": 5, "total_layers": 70},
    )


def test_sensors_are_refreshed_before_the_event_fires(coordinator):
    order = []
    coordinator._update_data.side_effect = lambda: order.append("sensors")
    coordinator._hass.bus.async_fire.side_effect = lambda *args: order.append("event")
    BambuDataUpdateCoordinator.event_handler_internal(coordinator, EVENT)
    assert order == ["sensors", "event"]


def test_event_is_skipped_before_device_is_registered(coordinator):
    coordinator.get_ha_printer_device.return_value = None
    BambuDataUpdateCoordinator.event_handler_internal(coordinator, EVENT)
    coordinator.get_ha_printer_device.assert_called_once()
    coordinator._hass.bus.async_fire.assert_not_called()


def test_every_trigger_has_an_english_name():
    names = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))["device_automation"]["trigger_type"]
    assert set(names) == TRIGGER_TYPES
