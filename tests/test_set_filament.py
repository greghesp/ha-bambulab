"""Optional set_filament checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant. These tests
skip when it is absent and make no MQTT connection: the published command is
captured from a mocked client.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.core import Event
from custom_components.bambu_lab import coordinator as coordinator_module
from custom_components.bambu_lab.const import DOMAIN, SERVICE_CALL_EVENT
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator

ENTITY_ID = "sensor.x1c_externalspool_external_spool"


def _publish_set_filament(data: dict) -> list:
    """Fire a set_filament service event at a coordinator and return what it published."""
    printer_device = SimpleNamespace(id="printer-device")
    spool_device = SimpleNamespace(id="spool-device", via_device_id=printer_device.id)
    entity_entry = SimpleNamespace(
        device_id=spool_device.id,
        unique_id="X1C_SERIAL_ExternalSpool_external_spool",
    )
    entity_reg = MagicMock()
    entity_reg.async_get.return_value = entity_entry
    device_reg = MagicMock()
    device_reg.async_get.return_value = spool_device

    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._hass = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.get_device().print_fun.mqtt_signature_required = False
    coordinator.get_ha_printer_device = lambda: printer_device

    async def fire():
        future = asyncio.get_running_loop().create_future()
        coordinator._hass.data = {DOMAIN: {"service_call_future": future}}
        event = Event(SERVICE_CALL_EVENT, {"service": "set_filament", "entity_id": ENTITY_ID, **data})
        await coordinator._handle_service_call_event(event)

    with patch.object(coordinator_module.entity_registry, "async_get", return_value=entity_reg), \
         patch.object(coordinator_module.device_registry, "async_get", return_value=device_reg):
        asyncio.run(fire())

    return [call.args[0] for call in coordinator.client.publish.call_args_list]


@pytest.mark.parametrize(
    ("tray_color", "expected"),
    [
        ("#ff0000", "FF0000FF"),    # '#', lower case and no alpha, all at once
        ("#FF0000FF", "FF0000FF"),  # leading '#'
        ("ff0000ff", "FF0000FF"),   # lower case
        ("FF0000", "FF0000FF"),     # RRGGBB gets an opaque alpha
        ("FF0000FF", "FF0000FF"),   # already RRGGBBAA: unchanged
        ("ff000080", "FF000080"),   # a non-opaque alpha is kept, only upper-cased
        ("FF00FF00", "FF00FF00"),   # the transparent example in docs/actions.mdx
    ],
)
def test_set_filament_publishes_normalized_color(tray_color, expected):
    published = _publish_set_filament({"tray_color": tray_color, "tray_type": "PLA", "tray_info_idx": "GFA00"})

    assert len(published) == 1
    assert published[0]["print"]["tray_color"] == expected


def test_set_filament_without_color_publishes_empty_color():
    published = _publish_set_filament({"tray_type": "PLA", "tray_info_idx": "GFA00"})

    assert len(published) == 1
    assert published[0]["print"]["tray_color"] == ""
