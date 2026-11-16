"""Optional entity checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant. These tests
skip when it is absent and make no service call or MQTT connection.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import HomeAssistantError
from custom_components.bambu_lab.fan import BambuLabFan, FANS
from custom_components.bambu_lab.definitions import PRINTER_SENSORS
from custom_components.bambu_lab.pybambu.const import FansEnum, Printers
from custom_components.bambu_lab.sensor import BambuLabSensor


@pytest.fixture
def fan():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.get_model().fans.set_fan_speed.return_value = True
    return BambuLabFan(coordinator, FANS[2], SimpleNamespace(data={"serial": "TESTSERIAL"}))


@pytest.mark.parametrize("percentage", [0, 20, 100])
def test_turn_on_preserves_percentage(fan, percentage):
    fan.turn_on(percentage=percentage)
    fan.coordinator.get_model().fans.set_fan_speed.assert_called_once_with(FansEnum.CHAMBER, percentage)


def test_turn_on_without_percentage_defaults_to_full_speed(fan):
    fan.turn_on()
    fan.coordinator.get_model().fans.set_fan_speed.assert_called_once_with(FansEnum.CHAMBER, 100)


def test_failed_publish_raises_service_error(fan):
    fan.coordinator.get_model().fans.set_fan_speed.return_value = False
    with pytest.raises(HomeAssistantError, match="could not be published"):
        fan.set_percentage(20)


def test_turn_off_requests_zero(fan):
    fan.turn_off()
    fan.coordinator.get_model().fans.set_fan_speed.assert_called_once_with(FansEnum.CHAMBER, 0)


def test_h3c_has_separate_exhaust_and_chamber_entities():
    coordinator = MagicMock()
    coordinator.get_model().info.device_type = Printers.H3C
    entry = SimpleNamespace(data={"serial": "TESTSERIAL"})
    descriptions = {description.key: description for description in FANS}
    assert not descriptions["chamber_fan"].exists_fn(coordinator)
    assert descriptions["exhaust_fan"].exists_fn(coordinator)
    assert descriptions["h3c_chamber_fan"].exists_fn(coordinator)
    exhaust = BambuLabFan(coordinator, descriptions["exhaust_fan"], entry)
    chamber = BambuLabFan(coordinator, descriptions["h3c_chamber_fan"], entry)
    assert exhaust.unique_id == "TESTSERIAL_exhaust_fan"
    assert chamber.unique_id == "TESTSERIAL_h3c_chamber_fan"
    assert chamber.unique_id != "TESTSERIAL_chamber_fan"
    assert exhaust.entity_description.translation_key == "exhaust_fan"
    assert chamber.entity_description.translation_key == "chamber_fan"

    sensors = {description.key: description for description in PRINTER_SENSORS}
    assert not sensors["chamber_fan_speed"].exists_fn(coordinator)
    assert sensors["exhaust_fan_speed"].exists_fn(coordinator)
    assert sensors["h3c_chamber_fan_speed"].exists_fn(coordinator)


@pytest.mark.parametrize("key,expected_key,fan_type", [
    ("cooling_fan", "part_fan", FansEnum.PART_COOLING),
    ("aux_fan", "right_aux_fan", FansEnum.AUXILIARY),
    ("secondary_aux_fan", "left_aux_fan", FansEnum.SECONDARY_AUXILIARY),
    ("exhaust_fan", "exhaust_fan", FansEnum.CHAMBER),
    ("h3c_chamber_fan", "h3c_chamber_fan", FansEnum.H3C_CHAMBER),
])
def test_h3c_fan_names_and_commands_match_printer(key, expected_key, fan_type):
    coordinator = MagicMock()
    coordinator.get_model().info.device_type = Printers.H3C
    coordinator.get_model().fans.h3c_chamber_fan_controllable = True
    coordinator.get_model().fans.set_fan_speed.return_value = True
    description = next(description for description in FANS if description.key == key)
    fan = BambuLabFan(coordinator, description, SimpleNamespace(data={"serial": "TESTSERIAL"}))
    assert fan.unique_id == f"TESTSERIAL_{expected_key}"
    expected_translation = "chamber_fan" if key == "h3c_chamber_fan" else expected_key
    assert fan.translation_key == expected_translation
    description.value_fn(coordinator.get_model())
    coordinator.get_model().fans.get_fan_speed.assert_called_once_with(fan_type)
    fan.set_percentage(60)
    coordinator.get_model().fans.set_fan_speed.assert_called_once_with(fan_type, 60)


@pytest.mark.parametrize("key,expected_key,fan_type", [
    ("cooling_fan_speed", "part_fan_speed", FansEnum.PART_COOLING),
    ("aux_fan_speed", "right_aux_fan_speed", FansEnum.AUXILIARY),
    ("secondary_aux_fan_speed", "left_aux_fan_speed", FansEnum.SECONDARY_AUXILIARY),
    ("exhaust_fan_speed", "exhaust_fan_speed", FansEnum.CHAMBER),
    ("h3c_chamber_fan_speed", "h3c_chamber_fan_speed", FansEnum.H3C_CHAMBER),
])
def test_h3c_fan_speed_sensor_names_match_printer(key, expected_key, fan_type):
    coordinator = MagicMock()
    coordinator.get_model().info.device_type = Printers.H3C
    coordinator.get_model().info.serial = "TESTSERIAL"
    description = next(description for description in PRINTER_SENSORS if description.key == key)
    sensor = BambuLabSensor(coordinator, description)
    assert sensor.unique_id == f"TESTSERIAL_{expected_key}"
    expected_translation = "chamber_fan_speed" if key == "h3c_chamber_fan_speed" else expected_key
    assert sensor.translation_key == expected_translation
    description.value_fn(sensor)
    coordinator.get_model().fans.get_fan_speed.assert_called_once_with(fan_type)


def test_h3c_chamber_fan_unknown_and_mode_restriction():
    coordinator = MagicMock()
    coordinator.get_model().info.device_type = Printers.H3C
    coordinator.get_model().fans.get_fan_speed.return_value = None
    coordinator.get_model().fans.h3c_chamber_fan_controllable = False
    description = next(description for description in FANS if description.key == "h3c_chamber_fan")
    fan = BambuLabFan(coordinator, description, SimpleNamespace(data={"serial": "TESTSERIAL"}))
    assert fan.is_on is None
    assert fan.percentage is None
    with pytest.raises(HomeAssistantError, match="not controllable"):
        fan.set_percentage(60)
    coordinator.get_model().fans.set_fan_speed.assert_not_called()


@pytest.mark.parametrize("model", [Printers.X1C, Printers.X2D, Printers.H2D])
def test_h3c_fan_entities_are_not_exposed_on_other_models(model):
    coordinator = MagicMock()
    coordinator.get_model().info.device_type = model
    descriptions = {description.key: description for description in FANS}
    assert descriptions["chamber_fan"].exists_fn(coordinator)
    assert not descriptions["exhaust_fan"].exists_fn(coordinator)
    assert not descriptions["h3c_chamber_fan"].exists_fn(coordinator)
