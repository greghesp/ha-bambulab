"""Tests for the external AMS heater (e.g. SUNLU AMS Heater, EIBOS Series X) control logic.

ams_heater.py has no Home Assistant imports, so it runs in the lightweight suite.
"""
from dataclasses import replace

import pytest

from ams_heater import (
    HeaterReading,
    HeaterSettings,
    decide,
    normalize_humidity,
    normalize_temperature,
    should_clear_lockout,
)

ENABLED = HeaterSettings(
    drying_enabled=True,
    humidity_on=40,
    humidity_off=25,
    max_temperature=60,
    max_runtime_hours=12,
)


def reading(humidity=30.0, temperature=35.0, online=True):
    return HeaterReading(humidity=humidity, temperature=temperature, printer_online=online)


def run(settings=ENABLED, rd=None, heater_on=False, on_for_hours=0.0, locked_out=False):
    return decide(settings, rd or reading(), heater_on, on_for_hours, locked_out)


def test_drying_mode_off_leaves_plug_alone():
    assert run(settings=replace(ENABLED, drying_enabled=False), rd=reading(humidity=90)) is None


def test_turns_on_at_or_above_on_threshold():
    result = run(rd=reading(humidity=40))
    assert result.on is True
    assert result.reason == "humid"


def test_turns_off_at_or_below_off_threshold():
    result = run(rd=reading(humidity=25), heater_on=True)
    assert result.on is False
    assert result.reason == "dry"


@pytest.mark.parametrize("heater_on", [True, False])
def test_holds_current_state_between_thresholds(heater_on):
    result = run(rd=reading(humidity=30), heater_on=heater_on)
    assert result.on is heater_on
    assert result.reason == "holding"


def test_over_temperature_turns_off_even_when_humid():
    result = run(rd=reading(humidity=80, temperature=60), heater_on=True)
    assert result.on is False
    assert result.reason == "over_temperature"


def test_unknown_temperature_does_not_block_heating():
    result = run(rd=reading(humidity=80, temperature=None))
    assert result.on is True


def test_printer_offline_turns_off():
    result = run(rd=reading(humidity=80, online=False), heater_on=True)
    assert result.on is False
    assert result.reason == "printer_offline"


def test_missing_humidity_turns_off():
    result = run(rd=reading(humidity=None), heater_on=True)
    assert result.on is False
    assert result.reason == "no_humidity"


def test_max_runtime_turns_off():
    result = run(rd=reading(humidity=80), heater_on=True, on_for_hours=12)
    assert result.on is False
    assert result.reason == "max_runtime"


def test_lockout_keeps_heater_off_while_still_humid():
    result = run(rd=reading(humidity=80), heater_on=False, locked_out=True)
    assert result.on is False
    assert result.reason == "max_runtime"


def test_zero_max_runtime_means_no_limit():
    settings = replace(ENABLED, max_runtime_hours=0)
    result = run(settings=settings, rd=reading(humidity=80), heater_on=True, on_for_hours=100)
    assert result.on is True


@pytest.mark.parametrize(
    ("humidity", "locked_out", "expected"),
    [(25, True, True), (20, True, True), (26, True, False), (20, False, False), (None, True, False)],
)
def test_should_clear_lockout(humidity, locked_out, expected):
    assert should_clear_lockout(ENABLED, reading(humidity=humidity), locked_out) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), (0, None), (-3, None), (101, None), ("x", None), (45, 45.0), ("37", 37.0), (100, 100.0)],
)
def test_normalize_humidity(raw, expected):
    assert normalize_humidity(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), (0, None), ("bad", None), (150, None), (42, 42.0), ("31.5", 31.5)],
)
def test_normalize_temperature(raw, expected):
    assert normalize_temperature(raw) == expected


def test_settings_are_immutable():
    with pytest.raises(Exception):
        ENABLED.humidity_on = 10
