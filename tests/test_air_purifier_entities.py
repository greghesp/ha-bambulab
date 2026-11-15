"""E1 child device and entity checks in a Home Assistant environment."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.fan import FanEntityFeature
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
from homeassistant.exceptions import HomeAssistantError

from custom_components.bambu_lab.const import DOMAIN
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator
from custom_components.bambu_lab.definitions import AIR_PURIFIER_SENSORS
from custom_components.bambu_lab.fan import BambuLabAirPurifierFan
from custom_components.bambu_lab.fan import async_setup_entry as setup_fans
from custom_components.bambu_lab.pybambu.air_purifier import AirPurifier
from custom_components.bambu_lab.sensor import BambuLabAirPurifierSensor
from custom_components.bambu_lab.sensor import async_setup_entry as setup_sensors


@pytest.fixture
def coordinator():
    client = MagicMock()
    client.publish.return_value = True
    purifier = AirPurifier(client)
    purifier.info_update({"module": [{"name": "aps", "sn": "TEST-E1", "product_name": "E1 Air Purifier",
                                     "hw_ver": "APS04", "sw_ver": "00.00.25.92"}]})
    purifier.print_update({"aux": "2000000000", "device": {"aps": {"gear": 15, "pm": 3, "rpm": 3509}}})
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.get_model().air_purifier = purifier
    coordinator.get_model().info.online = True
    coordinator.get_model().info.serial = "PRINTER"
    coordinator.get_model().has_full_printer_data = True
    coordinator.get_model().print_fun.mqtt_signature_required = False
    coordinator.get_air_purifier_device.return_value = {"identifiers": {(DOMAIN, "TEST-E1")}}
    return coordinator


def test_purifier_device_uses_actual_serial_and_parent(coordinator):
    coordinator.config_entry.data = {"serial": "PRINTER", "device_type": "H3C"}
    device = BambuDataUpdateCoordinator.get_air_purifier_device(coordinator)
    assert device["identifiers"] == {(DOMAIN, "TEST-E1")}
    assert device["model"] == "E1 Air Purifier"
    assert device["hw_version"] == "APS04"
    assert device["sw_version"] == "00.00.25.92"
    coordinator._set_via_device.assert_called_once_with(device)


def test_sensors_belong_to_purifier_and_follow_availability(coordinator):
    values = {}
    for description in AIR_PURIFIER_SENSORS:
        entity = BambuLabAirPurifierSensor(coordinator, description)
        assert entity.device_info == {"identifiers": {(DOMAIN, "TEST-E1")}}
        assert entity.unique_id == f"TEST-E1_{description.key}"
        assert entity.available
        values[description.key] = entity.native_value
    assert values == {"pm25": 3, "fan_speed": 3509}
    coordinator.get_model().air_purifier.connected = False
    assert not entity.available
    coordinator.get_model().air_purifier.connected = True
    coordinator.get_model().info.online = False
    assert not entity.available


def test_particulate_sensor_is_pm25(coordinator):
    description = next(sensor for sensor in AIR_PURIFIER_SENSORS if sensor.key == "pm25")
    sensor = BambuLabAirPurifierSensor(coordinator, description)
    assert sensor.unique_id == "TEST-E1_pm25"
    assert sensor.translation_key == "air_purifier_pm25"
    assert sensor.device_class == SensorDeviceClass.PM25
    assert sensor.native_unit_of_measurement == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    assert sensor.state_class == SensorStateClass.MEASUREMENT
    assert sensor.native_value == 3


@pytest.mark.parametrize("gear,mode,on", [
    (0, None, False), (1, "silent", True), (2, "standard", True),
    (3, "max", True), (15, "auto", True), (99, None, None),
])
def test_fan_reports_modes_without_percentage_speed(coordinator, gear, mode, on):
    coordinator.get_model().air_purifier.gear = gear
    fan = BambuLabAirPurifierFan(coordinator)
    assert fan.device_info == {"identifiers": {(DOMAIN, "TEST-E1")}}
    assert fan.unique_id == "TEST-E1_air_purifier"
    assert fan.icon == "mdi:air-purifier"
    assert fan.is_on is on
    assert fan.preset_mode == mode
    assert fan.supported_features == (FanEntityFeature.PRESET_MODE | FanEntityFeature.TURN_ON |
                                      FanEntityFeature.TURN_OFF)
    assert fan.state_attributes == {"preset_mode": mode}


def test_features_remain_stable_when_switching_modes(coordinator):
    fan = BambuLabAirPurifierFan(coordinator)
    features = fan.supported_features
    fan.set_preset_mode("standard")
    coordinator.get_model().air_purifier.gear = 2
    assert fan.supported_features == features
    assert fan.preset_mode == "standard"


@pytest.mark.parametrize("mode,action", [("auto", "15"), ("silent", "1"), ("standard", "2"), ("max", "3")])
def test_fan_presets_publish_the_requested_mode(coordinator, mode, action):
    fan = BambuLabAirPurifierFan(coordinator)
    fan.set_preset_mode(mode)
    coordinator.get_model().air_purifier._client.publish.assert_called_once_with({"print": {
        "sequence_id": "0", "command": "part_control", "module": "aps", "action": action,
    }})


def test_turn_on_with_percentage_is_rejected_without_publishing(coordinator):
    fan = BambuLabAirPurifierFan(coordinator)
    with pytest.raises(HomeAssistantError, match="does not support percentage"):
        fan.turn_on(percentage=50, preset_mode="silent")
    coordinator.get_model().air_purifier._client.publish.assert_not_called()


def test_fan_preset_turn_on_off_and_error_handling(coordinator):
    fan = BambuLabAirPurifierFan(coordinator)
    client = coordinator.get_model().air_purifier._client
    fan.set_preset_mode("silent")
    assert client.publish.call_args.args[0]["print"]["action"] == "1"
    fan.turn_on()
    assert client.publish.call_args.args[0]["print"]["action"] == "15"
    fan.turn_off()
    assert client.publish.call_args.args[0]["print"]["action"] == "0"
    with pytest.raises(HomeAssistantError):
        fan.set_preset_mode("invalid")
    client.publish.return_value = False
    with pytest.raises(HomeAssistantError, match="could not be published"):
        fan.set_preset_mode("max")


def test_signed_commands_and_detachment_block_control(coordinator):
    fan = BambuLabAirPurifierFan(coordinator)
    coordinator.get_model().print_fun.mqtt_signature_required = True
    assert fan.supported_features == FanEntityFeature(0)
    with pytest.raises(HomeAssistantError, match="unsigned"):
        fan.turn_on()
    coordinator.get_model().print_fun.mqtt_signature_required = False
    coordinator.get_model().air_purifier.connected = False
    assert not fan.available
    with pytest.raises(HomeAssistantError):
        fan.turn_on()
    coordinator.get_model().air_purifier._client.publish.assert_not_called()


def test_same_printer_with_different_purifier_invalidates_old_entity(coordinator):
    fan = BambuLabAirPurifierFan(coordinator)
    coordinator.get_model().air_purifier.serial = "DIFFERENT-E1"
    assert not fan.available


def test_restored_purifier_entities_survive_temporary_disconnect(coordinator):
    coordinator.config_entry.entry_id = "entry"
    coordinator.hass.states.get.return_value = SimpleNamespace(attributes={"restored": True})
    purifier_entity = SimpleNamespace(config_entry_id="entry", entity_id="fan.purifier", device_id="purifier")
    other_entity = SimpleNamespace(config_entry_id="entry", entity_id="sensor.other", device_id="other")
    entities = MagicMock()
    entities.entities.values.return_value = [purifier_entity, other_entity]
    devices = MagicMock()
    devices.async_get.side_effect = lambda device_id: SimpleNamespace(
        model="E1 Air Purifier" if device_id == "purifier" else "Other"
    )
    with patch("custom_components.bambu_lab.coordinator.er.async_get", return_value=entities), \
         patch("custom_components.bambu_lab.coordinator.device_registry.async_get", return_value=devices):
        BambuDataUpdateCoordinator._remove_dead_entities(coordinator)
    entities.async_remove.assert_called_once_with("sensor.other")


def test_platforms_create_child_entities_for_ready_purifier(coordinator):
    coordinator.makerworld = None
    coordinator.get_model().supports_feature.return_value = False
    coordinator.get_model().ams.data = {}
    hass = SimpleNamespace(data={DOMAIN: {"entry": coordinator}})
    entry = SimpleNamespace(entry_id="entry", data={"serial": "PRINTER"})
    fans, sensors = [], []
    asyncio.run(setup_fans(hass, entry, fans.extend))
    with patch("custom_components.bambu_lab.sensor._migrate_h3c_storage_entities"), \
         patch("custom_components.bambu_lab.sensor.er.async_get"), \
         patch("custom_components.bambu_lab.sensor.PRINTER_SENSORS", ()), \
         patch("custom_components.bambu_lab.sensor.VIRTUAL_TRAY_SENSORS", ()):
        asyncio.run(setup_sensors(hass, entry, sensors.extend))
    assert sum(isinstance(fan, BambuLabAirPurifierFan) for fan in fans) == 1
    assert sum(isinstance(sensor, BambuLabAirPurifierSensor) for sensor in sensors) == 2
