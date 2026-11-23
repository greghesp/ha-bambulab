"""Tests for the filament inventory sensors."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfMass
from homeassistant.core import SupportsResponse

from custom_components.bambu_lab import async_setup_entry, async_unload_entry
from custom_components.bambu_lab.definitions import FILAMENT_INVENTORY_SENSORS
from custom_components.bambu_lab.const import DOMAIN, ENTRY_TYPE, ENTRY_TYPE_FILAMENT_INVENTORY, FILAMENT_INVENTORY_DATA
from custom_components.bambu_lab.filamentinventory import async_get_filament_inventory
from custom_components.bambu_lab.pybambu.models import FilamentInventory
from custom_components.bambu_lab.sensor import BambuLabFilamentInventorySensor


def test_filament_inventory_sensors():
    coordinator = MagicMock()
    coordinator.unique_id_prefix = "filament_inventory_account"
    coordinator.inventory = FilamentInventory()
    coordinator.inventory.update({"hits": [
        {"id": 1, "netWeight": 996, "totalNetWeight": 1000},
        {"id": 2, "netWeight": 770, "totalNetWeight": 1000},
    ]})
    sensors = {
        description.key: BambuLabFilamentInventorySensor(coordinator, description)
        for description in FILAMENT_INVENTORY_SENSORS
    }

    count = sensors["filament_inventory"]
    assert count.unique_id == "filament_inventory_account_filament_inventory"
    assert count.native_value == 2
    assert count.extra_state_attributes == {"spools": coordinator.inventory.spools}

    weight = sensors["filament_inventory_total_remaining"]
    assert weight.unique_id == "filament_inventory_account_filament_inventory_total_remaining"
    assert weight.native_value == 1766
    assert weight.native_unit_of_measurement == UnitOfMass.GRAMS
    assert weight.device_class == SensorDeviceClass.WEIGHT
    assert weight.state_class == SensorStateClass.MEASUREMENT
    assert weight.extra_state_attributes == {}

    coordinator.inventory.update({"hits": []})
    assert count.native_value == 0
    assert weight.native_value == 0


def test_get_filament_inventory_targets_standalone_devices():
    payload = {"hits": [{"id": 1, "extra": {"value": 42}}], "extra": "unchanged"}
    first = SimpleNamespace(unique_id_prefix="filament_inventory_first", inventory=SimpleNamespace(raw_data=payload))
    second = SimpleNamespace(unique_id_prefix="filament_inventory_second", inventory=SimpleNamespace(raw_data={"hits": []}))
    devices = {
        "first": SimpleNamespace(config_entries={"first_entry"}, identifiers={(DOMAIN, first.unique_id_prefix)}),
        "second": SimpleNamespace(config_entries={"second_entry"}, identifiers={(DOMAIN, second.unique_id_prefix)}),
        "printer": SimpleNamespace(config_entries={"first_entry"}, identifiers={(DOMAIN, "printer")}),
    }
    hass = SimpleNamespace(data={FILAMENT_INVENTORY_DATA: {"first_entry": first, "second_entry": second}})
    device_registry = SimpleNamespace(async_get=lambda device_id: devices.get(device_id))

    def call(data):
        return asyncio.run(async_get_filament_inventory(SimpleNamespace(hass=hass, data=data)))

    with patch("custom_components.bambu_lab.filamentinventory.device_registry.async_get", return_value=device_registry):
        result = call({"device_id": ["first"]})
        assert result == payload
        result["hits"][0]["extra"]["value"] = 0
        assert payload["hits"][0]["extra"]["value"] == 42
        assert call({"device_id": "second"}) == {"hits": []}
        assert "error" in call({"entity_id": "sensor.inventory"})
        assert "error" in call({"device_id": ""})
        assert "error" in call({"device_id": "printer"})
        assert "error" in call({"device_id": "missing"})
        assert "error" in call({"device_id": ["first", "second"]})
        assert "error" in call({"device_id": "first", "entity_id": "sensor.inventory"})
        first.inventory.raw_data = None
        assert "error" in call({"device_id": "first"})


def test_inventory_service_lifecycle_without_printer():
    async def run():
        hass = SimpleNamespace(
            data={},
            services=MagicMock(),
            config_entries=SimpleNamespace(
                async_forward_entry_setups=AsyncMock(),
                async_unload_platforms=AsyncMock(return_value=True),
            ),
        )
        entries = [
            SimpleNamespace(entry_id=entry_id, data={
                ENTRY_TYPE: ENTRY_TYPE_FILAMENT_INVENTORY, "region": "us", "email": "email",
                "username": entry_id, "auth_token": "token",
            }, options={})
            for entry_id in ("first", "second")
        ]
        coordinators = [SimpleNamespace(async_refresh=AsyncMock(), async_shutdown=AsyncMock()) for entry in entries]
        with patch("custom_components.bambu_lab.BambuCloud"), \
             patch("custom_components.bambu_lab.BambuFilamentCoordinator", side_effect=coordinators):
            for entry in entries:
                assert await async_setup_entry(hass, entry)
            hass.services.async_register.assert_called_with(
                DOMAIN, "get_filament_inventory", async_get_filament_inventory,
                supports_response=SupportsResponse.ONLY,
            )
            hass.config_entries.async_unload_platforms.return_value = False
            assert not await async_unload_entry(hass, entries[0])
            assert "first" in hass.data[FILAMENT_INVENTORY_DATA]
            hass.services.async_remove.assert_not_called()
            hass.config_entries.async_unload_platforms.return_value = True
            assert await async_unload_entry(hass, entries[0])
            hass.services.async_remove.assert_not_called()
            assert await async_unload_entry(hass, entries[1])
            hass.services.async_remove.assert_called_once_with(DOMAIN, "get_filament_inventory")

    asyncio.run(run())