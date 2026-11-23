"""Protocol helpers for the BIQU (BIGTREETECH) Panda Breath chamber heater.

The Panda Breath serves an unauthenticated JSON WebSocket at ws://<host>/ws.
Every message has one root key, e.g. {"settings": {"work_on": true}}. The
device pushes fields one or a few at a time and has no "get state" command.

The field names follow the community reverse-engineered protocol at
https://justinh-rahb.github.io/pandabreath-klipper/protocol/ (firmware
V1.0.1 to V1.0.4). There is no official API documentation.

This module has no Home Assistant imports so it can be unit tested in the
lightweight test suite. Our own commands are fed back through apply_message
as an optimistic update, because the device does not echo state changes.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from typing import Any

MODE_AUTO = "auto"
MODE_ALWAYS_ON = "always_on"
MODE_FILAMENT_DRYING = "filament_drying"

WORK_MODES = {1: MODE_AUTO, 2: MODE_ALWAYS_ON, 3: MODE_FILAMENT_DRYING}
WORK_MODE_IDS = {name: number for number, name in WORK_MODES.items()}

SENSOR_STATUS = {0: "ok", 1: "open_circuit", 2: "short_circuit"}

TARGET_TEMPERATURE_RANGE = (20, 60)
DRYING_TEMPERATURE_RANGE = (40, 60)
# The firmware stops drying after 12 hours regardless of the timer.
DRYING_HOURS_RANGE = (1, 12)
AUTO_TRIGGER_RANGE = (30, 120)

DEFAULT_DRYING_TEMPERATURE = 50
DEFAULT_DRYING_HOURS = 6


@dataclass(frozen=True)
class PandaBreathState:
    """Last known Panda Breath state. None means not reported yet."""

    chamber_temperature: float | None = None
    chamber_temperature_calibrated: bool = False
    heater_temperature: float | None = None
    target_temperature: int | None = None
    power: bool | None = None
    mode: str | None = None
    drying: bool | None = None
    drying_remaining_minutes: int | None = None
    drying_temperature: int | None = None
    drying_hours: int | None = None
    auto_trigger_bed_temperature: int | None = None
    firmware_version: str | None = None
    heater_sensor_status: str | None = None
    bound_printer_serial: str | None = None


def parse_message(raw: str) -> dict[str, Any] | None:
    """Decode one WebSocket text frame, or None if it is not a JSON object."""
    try:
        message = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return message if isinstance(message, dict) else None


def _float(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # json.loads accepts NaN and Infinity; never let them reach int() or a sensor.
    return number if math.isfinite(number) else None


def _int(value) -> int | None:
    number = _float(value)
    return None if number is None else int(round(number))


def _bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().upper() in ("ON", "OFF", "TRUE", "FALSE", "1", "0"):
        return value.strip().upper() in ("ON", "TRUE", "1")
    return None


def _chamber_changes(state: PandaBreathState, settings: dict) -> dict:
    calibrated = _float(settings.get("cal_warehouse_temp"))
    if calibrated is not None:
        return {"chamber_temperature": calibrated, "chamber_temperature_calibrated": True}
    if state.chamber_temperature_calibrated:
        return {}
    for key in ("chamber_temp", "warehouse_temper"):
        raw = _float(settings.get(key))
        if raw is not None:
            return {"chamber_temperature": raw}
    return {}


def _remaining_minutes(settings: dict) -> int | None:
    minutes = _int(settings.get("drying_remaining_min"))
    if minutes is not None:
        return minutes
    seconds = _int(settings.get("remaining_seconds"))
    return None if seconds is None else seconds // 60


def _target_temperature(state: PandaBreathState, settings: dict) -> int | None:
    """target_temp is the live target; otherwise read the field of the current mode."""
    if "target_temp" in settings:
        return _int(settings["target_temp"])
    if state.mode == MODE_AUTO:
        return _int(settings.get("temp"))
    if state.mode == MODE_ALWAYS_ON:
        return _int(settings.get("set_temp"))
    return None


def _first(settings: dict, keys: tuple[str, ...], convert):
    for key in keys:
        if key in settings:
            value = convert(settings[key])
            if value is not None:
                return value
    return None


def apply_message(state: PandaBreathState, message: dict[str, Any]) -> PandaBreathState:
    """Return a new state with the fields of one device message applied."""
    settings = message.get("settings") if isinstance(message, dict) else None
    if not isinstance(settings, dict):
        return state

    mode_number = _int(settings.get("work_mode"))
    status_number = _int(settings.get("ptc_sensor_status"))
    serial = settings.get("printer_sn")
    candidates = {
        "heater_temperature": _float(settings.get("cal_ptc_temp")),
        "target_temperature": _target_temperature(state, settings),
        "power": _bool(settings.get("work_on")),
        "mode": WORK_MODES.get(mode_number),
        "drying": _first(settings, ("drying_running", "isrunning"), _bool),
        "drying_remaining_minutes": _remaining_minutes(settings),
        "drying_temperature": _first(settings, ("filament_temp", "custom_temp"), _int),
        "drying_hours": _first(settings, ("filament_timer", "custom_timer"), _int),
        "auto_trigger_bed_temperature": _int(settings.get("hotbedtemp")),
        "firmware_version": settings.get("fw_version") if isinstance(settings.get("fw_version"), str) else None,
        "heater_sensor_status": SENSOR_STATUS.get(status_number),
        "bound_printer_serial": serial if isinstance(serial, str) and serial else None,
    }
    changes = {key: value for key, value in candidates.items() if value is not None}
    changes.update(_chamber_changes(state, settings))
    if changes.get("drying") is False and "drying_remaining_minutes" not in changes:
        changes["drying_remaining_minutes"] = 0
    return replace(state, **changes) if changes else state


def _check_range(value: float, bounds: tuple[int, int], name: str) -> int:
    low, high = bounds
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}, got {value}")
    return int(round(value))


def _settings(**fields) -> list[dict[str, Any]]:
    return [{"settings": fields}]


def build_power(on: bool) -> list[dict[str, Any]]:
    return _settings(work_on=bool(on))


def build_mode(mode: str) -> list[dict[str, Any]]:
    if mode not in WORK_MODE_IDS:
        raise ValueError(f"Unknown Panda Breath mode: {mode}")
    return _settings(work_mode=WORK_MODE_IDS[mode])


def build_target_temperature(mode: str | None, temperature: float) -> list[dict[str, Any]]:
    """Auto mode stores its target in "temp", Always On in "set_temp"; both send "target_temp".

    Drying uses its own temperature, and with an unknown mode we can't tell which
    field to write, so both are refused rather than risk changing the wrong setpoint.
    """
    value = _check_range(temperature, TARGET_TEMPERATURE_RANGE, "Target temperature")
    if mode == MODE_AUTO:
        return _settings(temp=value, target_temp=value)
    if mode == MODE_ALWAYS_ON:
        return _settings(set_temp=value, target_temp=value)
    raise ValueError("Target temperature can only be set in Auto or Always on mode. Use the drying temperature while drying.")


def build_auto_trigger(bed_temperature: float) -> list[dict[str, Any]]:
    value = _check_range(bed_temperature, AUTO_TRIGGER_RANGE, "Auto trigger bed temperature")
    return _settings(hotbedtemp=value)


def build_drying_temperature(temperature: float) -> list[dict[str, Any]]:
    return _settings(filament_temp=_check_range(temperature, DRYING_TEMPERATURE_RANGE, "Drying temperature"))


def build_drying_time(hours: float) -> list[dict[str, Any]]:
    return _settings(filament_timer=_check_range(hours, DRYING_HOURS_RANGE, "Drying time"))


def build_start_drying(temperature: float, hours: float) -> list[dict[str, Any]]:
    return _settings(
        work_mode=WORK_MODE_IDS[MODE_FILAMENT_DRYING],
        filament_temp=_check_range(temperature, DRYING_TEMPERATURE_RANGE, "Drying temperature"),
        filament_timer=_check_range(hours, DRYING_HOURS_RANGE, "Drying time"),
        isrunning=1,
        drying_running=True,
    )


def build_stop_drying() -> list[dict[str, Any]]:
    return _settings(isrunning=0, drying_running=False)
