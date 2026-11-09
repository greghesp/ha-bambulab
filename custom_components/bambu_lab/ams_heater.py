"""Decision logic for an external AMS heater switched by a smart plug.

Add-on heated lids such as the SUNLU AMS Heater have no data connection: they
never report to the printer, so the only way Home Assistant can control one is
by switching its power. This module decides when that power should be on,
using the AMS's own humidity and temperature readings.

It deliberately has no Home Assistant imports so it can be unit tested in the
lightweight test suite.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_HUMIDITY_ON = 40.0
DEFAULT_HUMIDITY_OFF = 25.0
DEFAULT_MAX_TEMPERATURE = 60.0
DEFAULT_MAX_RUNTIME_HOURS = 12.0

MIN_HUMIDITY = 5.0
MAX_HUMIDITY = 90.0
MIN_TEMPERATURE = 30.0
MAX_TEMPERATURE = 75.0
MAX_RUNTIME_HOURS = 72.0

# Readings outside these ranges are treated as "not reported" rather than real.
_PLAUSIBLE_TEMPERATURE = (-20.0, 120.0)

REASON_HUMID = "humid"
REASON_DRY = "dry"
REASON_HOLDING = "holding"
REASON_OVER_TEMPERATURE = "over_temperature"
REASON_PRINTER_OFFLINE = "printer_offline"
REASON_NO_HUMIDITY = "no_humidity"
REASON_MAX_RUNTIME = "max_runtime"


@dataclass(frozen=True)
class HeaterSettings:
    """User settings for one AMS heater."""

    drying_enabled: bool = False
    humidity_on: float = DEFAULT_HUMIDITY_ON
    humidity_off: float = DEFAULT_HUMIDITY_OFF
    max_temperature: float = DEFAULT_MAX_TEMPERATURE
    # 0 disables the runtime limit.
    max_runtime_hours: float = DEFAULT_MAX_RUNTIME_HOURS


@dataclass(frozen=True)
class HeaterReading:
    """What the printer currently reports for the AMS the heater sits on."""

    humidity: float | None
    temperature: float | None
    printer_online: bool


@dataclass(frozen=True)
class HeaterDecision:
    """Whether the heater's plug should be on, and why."""

    on: bool
    reason: str


def _to_float(raw) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def normalize_humidity(raw) -> float | None:
    """Return the AMS humidity in percent, or None when it is not reported.

    The printer model defaults humidity to 0 until a reading arrives, and a real
    AMS never reads 0% RH, so 0 is treated as missing.
    """
    value = _to_float(raw)
    if value is None or value <= 0 or value > 100:
        return None
    return value


def normalize_temperature(raw) -> float | None:
    """Return the AMS temperature in Celsius, or None when it is not reported."""
    value = _to_float(raw)
    if value is None or value == 0:
        return None
    low, high = _PLAUSIBLE_TEMPERATURE
    if value < low or value > high:
        return None
    return value


def _runtime_exceeded(settings: HeaterSettings, heater_on: bool, on_for_hours: float) -> bool:
    if settings.max_runtime_hours <= 0:
        return False
    return heater_on and on_for_hours >= settings.max_runtime_hours


def decide(
    settings: HeaterSettings,
    reading: HeaterReading,
    heater_on: bool,
    on_for_hours: float,
    locked_out: bool,
) -> HeaterDecision | None:
    """Decide the heater plug state.

    Returns None when drying mode is off, meaning the plug is left alone so it
    can be switched by hand. Safety checks come before the humidity thresholds,
    and any missing reading turns the heater off.
    """
    if not settings.drying_enabled:
        return None
    if not reading.printer_online:
        return HeaterDecision(False, REASON_PRINTER_OFFLINE)
    if reading.humidity is None:
        return HeaterDecision(False, REASON_NO_HUMIDITY)
    if reading.temperature is not None and reading.temperature >= settings.max_temperature:
        return HeaterDecision(False, REASON_OVER_TEMPERATURE)
    if locked_out or _runtime_exceeded(settings, heater_on, on_for_hours):
        return HeaterDecision(False, REASON_MAX_RUNTIME)
    if reading.humidity >= settings.humidity_on:
        return HeaterDecision(True, REASON_HUMID)
    if reading.humidity <= settings.humidity_off:
        return HeaterDecision(False, REASON_DRY)
    return HeaterDecision(heater_on, REASON_HOLDING)


def should_clear_lockout(settings: HeaterSettings, reading: HeaterReading, locked_out: bool) -> bool:
    """A max-runtime lockout ends once the AMS has dried to the off threshold."""
    return locked_out and reading.humidity is not None and reading.humidity <= settings.humidity_off
