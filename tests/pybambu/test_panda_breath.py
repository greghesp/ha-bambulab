"""Tests for the BIQU Panda Breath WebSocket protocol helpers.

panda_breath.py has no Home Assistant imports, so it runs in the lightweight suite.
"""
import pytest

from panda_breath import (
    MODE_ALWAYS_ON,
    MODE_AUTO,
    MODE_FILAMENT_DRYING,
    PandaBreathState,
    apply_message,
    build_auto_trigger,
    build_drying_temperature,
    build_drying_time,
    build_mode,
    build_power,
    build_start_drying,
    build_stop_drying,
    build_target_temperature,
    parse_message,
)

EMPTY = PandaBreathState()


def test_parse_message_accepts_settings_json():
    assert parse_message('{"settings": {"work_on": true}}') == {"settings": {"work_on": True}}


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", "42", ""])
def test_parse_message_rejects_non_objects(raw):
    assert parse_message(raw) is None


def test_prefers_calibrated_chamber_temperature():
    state = apply_message(EMPTY, {"settings": {"warehouse_temper": 38.5}})
    assert state.chamber_temperature == 38.5
    state = apply_message(state, {"settings": {"cal_warehouse_temp": 37.9}})
    assert state.chamber_temperature == 37.9
    # A later raw reading must not replace the calibrated one.
    state = apply_message(state, {"settings": {"warehouse_temper": 39.0}})
    assert state.chamber_temperature == 37.9


def test_chamber_temp_alias_is_used_without_calibrated_value():
    state = apply_message(EMPTY, {"settings": {"chamber_temp": 41.2, "target_temp": 45}})
    assert state.chamber_temperature == 41.2
    assert state.target_temperature == 45


def test_power_and_mode():
    state = apply_message(EMPTY, {"settings": {"work_on": True, "work_mode": 2}})
    assert state.power is True
    assert state.mode == MODE_ALWAYS_ON


def test_unknown_mode_is_ignored():
    state = apply_message(EMPTY, {"settings": {"work_mode": 9}})
    assert state.mode is None


@pytest.mark.parametrize(("raw", "expected"), [("ON", True), ("OFF", False), (1, True), (0, False), (True, True)])
def test_drying_running_accepts_mixed_types(raw, expected):
    state = apply_message(EMPTY, {"settings": {"drying_running": raw}})
    assert state.drying is expected


def test_drying_remaining_from_minutes_or_seconds():
    assert apply_message(EMPTY, {"settings": {"drying_remaining_min": 72}}).drying_remaining_minutes == 72
    assert apply_message(EMPTY, {"settings": {"remaining_seconds": 3600}}).drying_remaining_minutes == 60


def test_heater_and_metadata_fields():
    state = apply_message(EMPTY, {"settings": {
        "cal_ptc_temp": 88.4, "fw_version": "V1.0.4", "ptc_sensor_status": 1,
        "printer_sn": "01P00A000000000", "hotbedtemp": 50,
    }})
    assert state.heater_temperature == 88.4
    assert state.firmware_version == "V1.0.4"
    assert state.heater_sensor_status == "open_circuit"
    assert state.bound_printer_serial == "01P00A000000000"
    assert state.auto_trigger_bed_temperature == 50


def test_bad_values_and_other_roots_are_ignored():
    state = apply_message(EMPTY, {"settings": {"cal_warehouse_temp": "hot", "work_on": "maybe"}})
    assert state == EMPTY
    assert apply_message(EMPTY, {"wifi": {"scan": 1}}) == EMPTY
    assert apply_message(EMPTY, {"settings": "nope"}) == EMPTY


def test_apply_message_returns_new_state():
    state = apply_message(EMPTY, {"settings": {"work_on": True}})
    assert state is not EMPTY
    assert EMPTY.power is None


def test_build_power():
    assert build_power(True) == [{"settings": {"work_on": True}}]
    assert build_power(False) == [{"settings": {"work_on": False}}]


def test_build_mode():
    assert build_mode(MODE_AUTO) == [{"settings": {"work_mode": 1}}]
    with pytest.raises(ValueError):
        build_mode("turbo")


def test_target_temperature_depends_on_mode():
    assert build_target_temperature(MODE_ALWAYS_ON, 45) == [{"settings": {"set_temp": 45, "target_temp": 45}}]
    assert build_target_temperature(MODE_AUTO, 40) == [{"settings": {"temp": 40, "target_temp": 40}}]
    with pytest.raises(ValueError):
        build_target_temperature(MODE_ALWAYS_ON, 75)


@pytest.mark.parametrize("mode", [None, MODE_FILAMENT_DRYING])
def test_target_temperature_refused_when_mode_is_drying_or_unknown(mode):
    with pytest.raises(ValueError, match="Auto or Always on"):
        build_target_temperature(mode, 45)


def test_target_temperature_reads_field_for_current_mode():
    auto = apply_message(EMPTY, {"settings": {"work_mode": 1}})
    assert apply_message(auto, {"settings": {"temp": 40, "set_temp": 55}}).target_temperature == 40
    always = apply_message(EMPTY, {"settings": {"work_mode": 2}})
    assert apply_message(always, {"settings": {"temp": 40, "set_temp": 55}}).target_temperature == 55
    assert apply_message(always, {"settings": {"set_temp": 55, "target_temp": 48}}).target_temperature == 48
    assert apply_message(EMPTY, {"settings": {"set_temp": 55}}).target_temperature is None


def test_non_finite_numbers_are_ignored():
    for raw in ('{"settings": {"work_mode": NaN}}', '{"settings": {"cal_warehouse_temp": Infinity}}'):
        assert apply_message(EMPTY, parse_message(raw)) == EMPTY


def test_stopping_drying_clears_remaining_time():
    state = apply_message(EMPTY, {"settings": {"drying_running": "ON", "drying_remaining_min": 72}})
    for message in build_stop_drying():
        state = apply_message(state, message)
    assert state.drying is False
    assert state.drying_remaining_minutes == 0


def test_auto_trigger():
    assert build_auto_trigger(55) == [{"settings": {"hotbedtemp": 55}}]
    with pytest.raises(ValueError):
        build_auto_trigger(5)


def test_drying_commands():
    assert build_start_drying(55, 6) == [{"settings": {
        "work_mode": 3, "filament_temp": 55, "filament_timer": 6, "isrunning": 1, "drying_running": True,
    }}]
    assert build_stop_drying() == [{"settings": {"isrunning": 0, "drying_running": False}}]
    assert build_drying_temperature(50) == [{"settings": {"filament_temp": 50}}]
    assert build_drying_time(4) == [{"settings": {"filament_timer": 4}}]
    with pytest.raises(ValueError):
        build_start_drying(80, 6)
    with pytest.raises(ValueError):
        build_start_drying(55, 13)


def test_commands_apply_back_to_state_optimistically():
    state = EMPTY
    for message in build_start_drying(55, 6):
        state = apply_message(state, message)
    assert state.mode == MODE_FILAMENT_DRYING
    assert state.drying is True
    assert state.drying_temperature == 55
    assert state.drying_hours == 6
