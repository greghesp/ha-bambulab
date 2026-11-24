"""P3C entity checks: run in a Home Assistant Python environment, skipped when it is absent."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab.button import BambuLabHotendRackButton, async_setup_entry
from custom_components.bambu_lab.const import DOMAIN
from custom_components.bambu_lab.definitions import (
    AMS_BINARY_SENSORS,
    AMS_SENSORS,
    HOTEND_RACK_HOTEND_SENSORS,
    HOTEND_RACK_SENSORS,
    PRINTER_SENSORS,
)
from custom_components.bambu_lab.fan import FANS, BambuLabFan
from custom_components.bambu_lab.pybambu.const import Features, FansEnum, Printers
from custom_components.bambu_lab.sensor import BambuLabSensor

TOOL_COUNTS = {Printers.H3C: 9, Printers.P3C: 7}


def make_coordinator(model=Printers.P3C):
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.get_model().info.device_type = model
    coordinator.get_model().info.serial = "TESTSERIAL"
    coordinator.get_model().hotend_rack.tool_count = TOOL_COUNTS.get(model)
    return coordinator


def existing(descriptions, coordinator, *args):
    return {d.key for d in descriptions if d.exists_fn(coordinator, *args)}


def test_fans_follow_bambu_studio_names():
    coordinator = make_coordinator()
    entry = SimpleNamespace(data={"serial": "TESTSERIAL"})
    fans = {d.key: d for d in FANS if d.exists_fn(coordinator)}
    assert set(fans) == {"cooling_fan", "aux_fan", "secondary_aux_fan", "exhaust_fan"}
    names = {key: BambuLabFan(coordinator, d, entry).translation_key for key, d in fans.items()}
    assert names == {"cooling_fan": "part_fan", "aux_fan": "right_aux_fan",
                     "secondary_aux_fan": "left_aux_fan", "exhaust_fan": "exhaust_fan"}


def test_exhaust_fan_command():
    coordinator = make_coordinator()
    description = next(d for d in FANS if d.key == "exhaust_fan")
    fan = BambuLabFan(coordinator, description, SimpleNamespace(data={"serial": "TESTSERIAL"}))
    fan.set_percentage(60)
    coordinator.get_model().fans.set_fan_speed.assert_called_once_with(FansEnum.CHAMBER, 60)


@pytest.mark.parametrize("key,expected", [
    ("cooling_fan_speed", "part_fan_speed"), ("aux_fan_speed", "right_aux_fan_speed"),
    ("secondary_aux_fan_speed", "left_aux_fan_speed"), ("exhaust_fan_speed", "exhaust_fan_speed"),
])
def test_fan_speed_sensor_names(key, expected):
    coordinator = make_coordinator()
    description = next(d for d in PRINTER_SENSORS if d.key == key)
    sensor = BambuLabSensor(coordinator, description)
    assert sensor.unique_id == f"TESTSERIAL_{expected}"
    assert sensor.translation_key == expected


def test_printer_sensors():
    keys = existing(PRINTER_SENSORS, make_coordinator())
    assert {"exhaust_fan_speed", "external_storage_connection", "external_storage_total"} <= keys
    assert not {"chamber_fan_speed", "h3c_chamber_fan_speed"} & keys


@pytest.mark.parametrize("model", list(TOOL_COUNTS))
def test_one_set_of_printtool_sensors_per_tool(model):
    count = TOOL_COUNTS[model]
    keys = existing(HOTEND_RACK_HOTEND_SENSORS, make_coordinator(model))
    suffixes = ("", "_temperature", "_target_temperature", "_used_time")
    assert keys == {f"printtool_{n}{suffix}" for n in range(1, count + 1) for suffix in suffixes}


def test_h2c_keeps_its_six_vortek_hotends():
    keys = existing(HOTEND_RACK_HOTEND_SENSORS, make_coordinator(Printers.H2C))
    assert keys == {f"hotend_{sid}{suffix}" for sid in range(16, 22) for suffix in ("", "_used_time")}


def test_rack_position_uses_the_swaptek_sensors():
    coordinator = make_coordinator()
    names = {d.translation_key for d in HOTEND_RACK_SENSORS if d.exists_fn(coordinator)}
    assert names == {"hotend_rack_swaptek_holder_position", "hotend_rack_swaptek_holder_state"}


def test_rack_buttons():
    coordinator = make_coordinator()
    model = coordinator.get_model()
    model.has_full_printer_data = True
    model.print_fun.mqtt_signature_required = False
    model.supports_feature.side_effect = lambda feature: feature == Features.HOTEND_RACK
    coordinator.get_hotend_rack_device.return_value = {"identifiers": {(DOMAIN, "TESTSERIAL_rack")}}
    hass = SimpleNamespace(data={DOMAIN: {"entry": coordinator}})
    entry = SimpleNamespace(entry_id="entry", data={"serial": "TESTSERIAL"})
    entities = []
    asyncio.run(async_setup_entry(hass, entry, entities.extend))
    assert sum(isinstance(entity, BambuLabHotendRackButton) for entity in entities) == 2


def ams_coordinator(model, zones, trays):
    coordinator = make_coordinator()
    coordinator.get_model().ams.data = {36: SimpleNamespace(model=model, zones=zones, tray=[None] * trays)}
    coordinator.get_model().supports_feature.side_effect = lambda feature: feature != Features.DUAL_NOZZLES
    return coordinator


def test_ams_3p_shows_the_zones_it_reports():
    keys = existing(AMS_SENSORS, ams_coordinator("AMS 3P", {0: {}}, 7), 36)
    assert {"zone_1_temp", "zone_1_humidity_raw"} <= keys
    assert not {"zone_2_temp", "zone_2_humidity_raw"} & keys
    assert not {"humidity", "humidity_index", "temperature"} & keys
    assert {key for key in keys if key.startswith("tray_")} == {f"tray_{n}" for n in range(1, 8)}


def test_ams_3p_first_zone_does_not_wait_for_the_zone_report():
    """Entities are only set up again when the version info changes."""
    keys = existing(AMS_SENSORS, ams_coordinator("AMS 3P", {}, 7), 36)
    assert {"zone_1_temp", "zone_1_humidity_raw"} <= keys


def test_ams_3p_shows_a_second_zone_when_reported():
    keys = existing(AMS_SENSORS, ams_coordinator("AMS 3P", {0: {}, 1: {}}, 7), 36)
    assert {"zone_2_temp", "zone_2_humidity_raw"} <= keys


def test_ams_3h_always_has_both_zones():
    keys = existing(AMS_SENSORS, ams_coordinator("AMS 3H", {}, 9), 36)
    assert {"zone_1_temp", "zone_2_temp", "remaining_drying_time"} <= keys


def test_ams_3p_has_no_drying_entities():
    coordinator = ams_coordinator("AMS 3P", {0: {}}, 7)
    assert "remaining_drying_time" not in existing(AMS_SENSORS, coordinator, 36)
    assert "drying" not in existing(AMS_BINARY_SENSORS, coordinator, 36)
