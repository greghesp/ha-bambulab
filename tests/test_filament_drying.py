"""Optional filament drying service checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant. These tests
skip when it is absent and make no MQTT connection: the published command is
captured from a mocked client.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import coordinator as coordinator_module
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator


def _call_filament_drying(model: str, data: dict, ams_index: int = 32) -> tuple[bool, list]:
    """Invoke _service_call_filament_drying for a mocked AMS device and return (result, published)."""
    ams_serial = "AMS3H_SERIAL"
    ams_device = SimpleNamespace(
        id="ams-device",
        model=model,
        identifiers={("bambu_lab", ams_serial)},
    )
    device_reg = MagicMock()
    device_reg.async_get.return_value = ams_device

    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._hass = MagicMock()
    coordinator.client = MagicMock()
    coordinator.get_model = lambda: SimpleNamespace(
        ams=SimpleNamespace(data={ams_index: SimpleNamespace(serial=ams_serial)})
    )

    with patch.object(coordinator_module.device_registry, "async_get", return_value=device_reg):
        result = coordinator._service_call_filament_drying({"device_id": ams_device.id, **data})

    published = [call.args[0] for call in coordinator.client.publish.call_args_list]
    return result, published


def test_start_filament_drying_accepts_ams_3h():
    result, published = _call_filament_drying(
        "AMS 3H",
        {"service": "start_filament_drying", "temp": 50, "duration": 6, "rotate_tray": False},
    )

    assert result is True
    assert len(published) == 1
    assert published[0]["print"]["command"] == "ams_filament_drying"
    assert published[0]["print"]["ams_id"] == 32
    assert published[0]["print"]["temp"] == 50
    assert published[0]["print"]["cooling_temp"] == 45
    assert published[0]["print"]["duration"] == 6
    assert published[0]["print"]["mode"] == 1
    assert published[0]["print"]["rotate_tray"] is False


def test_stop_filament_drying_accepts_ams_3h():
    result, published = _call_filament_drying(
        "AMS 3H",
        {"service": "stop_filament_drying"},
    )

    assert result is True
    assert len(published) == 1
    assert published[0]["print"]["command"] == "ams_filament_drying"
    assert published[0]["print"]["ams_id"] == 32
    assert published[0]["print"]["mode"] == 0


def test_start_filament_drying_rejects_excessive_temp_for_ams_3h():
    result, published = _call_filament_drying(
        "AMS 3H",
        {"service": "start_filament_drying", "temp": 70, "duration": 6},
    )

    assert result is False
    assert published == []


def test_start_filament_drying_rejects_unsupported_ams():
    result, published = _call_filament_drying(
        "AMS",
        {"service": "start_filament_drying", "temp": 50, "duration": 6},
        ams_index=0,
    )

    assert result is False
    assert published == []
