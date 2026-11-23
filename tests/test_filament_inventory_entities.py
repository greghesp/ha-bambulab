"""Tests for the filament inventory sensors."""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfMass

from custom_components.bambu_lab.definitions import FILAMENT_INVENTORY_SENSORS
from custom_components.bambu_lab.pybambu.models import FilamentInventory
from custom_components.bambu_lab.sensor import BambuLabFilamentInventorySensor


def test_filament_inventory_sensors():
    coordinator = MagicMock()
    coordinator.printer_coordinator.get_model().info.serial = "PRINTER"
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
    assert count.unique_id == "PRINTER_filament_inventory"
    assert count.native_value == 2
    assert count.extra_state_attributes == {"spools": coordinator.inventory.spools}

    weight = sensors["filament_inventory_total_remaining"]
    assert weight.unique_id == "PRINTER_filament_inventory_total_remaining"
    assert weight.native_value == 1766
    assert weight.native_unit_of_measurement == UnitOfMass.GRAMS
    assert weight.device_class == SensorDeviceClass.WEIGHT
    assert weight.state_class == SensorStateClass.MEASUREMENT
    assert weight.extra_state_attributes == {}

    coordinator.inventory.update({"hits": []})
    assert count.native_value == 0
    assert weight.native_value == 0