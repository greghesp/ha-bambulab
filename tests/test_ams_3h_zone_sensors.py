"""Optional AMS 3H zone sensor checks: run in a Home Assistant Python environment.

The cards find entities by translation_key, so the AMS 3H zone sensors need one rather
than a fixed English name. These tests skip when Home Assistant is absent.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.helpers.typing import UNDEFINED
from custom_components.bambu_lab.definitions import AMS_BINARY_SENSORS, AMS_SENSORS
from custom_components.bambu_lab.pybambu.models import AMSInstance

EN = json.loads(
    (Path(__file__).resolve().parents[1] / "custom_components" / "bambu_lab" / "translations" / "en.json")
    .read_text(encoding="utf-8")
)
ZONE_KEYS = {
    "zone_temperature": "temp",
    "zone_humidity": "humidity_raw",
}


def _zone_descriptions():
    return [d for d in AMS_SENSORS if d.key.startswith("zone_")]


def _entity(zones):
    ams = SimpleNamespace(model="AMS 3H", zones=zones)
    coordinator = MagicMock()
    coordinator.get_model().ams.data = {32: ams}
    return SimpleNamespace(coordinator=coordinator, index=32)


def test_zone_sensors_are_named_by_translation_key():
    descriptions = _zone_descriptions()
    assert len(descriptions) == 4
    for description in descriptions:
        assert description.translation_key in ZONE_KEYS, description.key
        assert description.name in (None, UNDEFINED), description.key
        assert description.translation_placeholders["zone_number"] in ("1", "2")


def test_zone_translation_strings_exist_with_their_placeholder():
    sensors = EN["entity"]["sensor"]
    for key in ZONE_KEYS:
        assert "{zone_number}" in sensors[key]["name"], key
        attributes = sensors[key]["state_attributes"]
        assert {"zone", "zone_id", "slots", "dry_setting"} <= set(attributes), key


def test_zone_sensor_keys():
    assert {d.key for d in _zone_descriptions()} == {
        "zone_1_temp", "zone_1_humidity_raw",
        "zone_2_temp", "zone_2_humidity_raw",
    }


def test_zone_attributes_include_the_one_based_zone_and_slots():
    entity = _entity({1: {"zone_slots": [0, 1, 2], "dry_setting": {"dry_duration": -1}}})
    description = next(d for d in _zone_descriptions() if d.key == "zone_2_temp")
    attributes = description.extra_attributes(entity)
    assert attributes["zone"] == 2
    assert attributes["zone_id"] == 1
    assert attributes["slots"] == [1, 2, 3]


def test_zone_values_read_their_own_zone():
    entity = _entity({0: {"temp": "28.2", "humidity_raw": "24", "dry_time": 95},
                      1: {"temp": "27.7", "humidity_raw": "33", "dry_time": 0}})
    values = {d.key: d.value_fn(entity) for d in _zone_descriptions()}
    assert values["zone_1_temp"] == 28.2
    assert values["zone_2_humidity_raw"] == 33


def test_ams_3h_remaining_drying_time_sensor_uses_heated_zone():
    ams = AMSInstance(MagicMock(), "AMS 3H", 32)
    coordinator = MagicMock()
    coordinator.get_model().ams.data = {32: ams}
    entity = SimpleNamespace(coordinator=coordinator, index=32)
    description = next(d for d in AMS_SENSORS if d.key == "remaining_drying_time")
    assert description.exists_fn(coordinator, 32)
    assert description.value_fn(entity) is None
    ams.zones = {0: {"dry_time": 719}, 1: {"dry_time": 0}}
    assert description.value_fn(entity) == 719
    ams.zones[0]["dry_time"] = 0
    assert description.value_fn(entity) == 0

    for model in ("AMS 2 Pro", "AMS HT"):
        ams.model = model
        ams.remaining_drying_time = 42
        assert description.exists_fn(coordinator, 32)
        assert description.value_fn(entity) == 42


def test_ams_3h_drying_binary_sensor_uses_heated_zone_timer():
    ams = AMSInstance(MagicMock(), "AMS 3H", 32)
    coordinator = MagicMock()
    coordinator.get_model().ams.data = {32: ams}
    entity = SimpleNamespace(coordinator=coordinator, index=32)
    description = next(d for d in AMS_BINARY_SENSORS if d.key == "drying")
    assert description.exists_fn(coordinator, 32)
    assert description.is_on_fn(entity) is None
    ams.zones = {0: {"dry_time": 1079}, 1: {"dry_time": 1079}}
    assert description.is_on_fn(entity) is True
    ams.zones = {0: {"dry_time": 0}, 1: {"dry_time": 1079}}
    assert description.is_on_fn(entity) is False
