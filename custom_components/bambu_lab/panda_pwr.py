"""Protocol helpers for the BIQU (BIGTREETECH) Panda PWR smart power switch.

The Panda PWR serves a small unauthenticated HTTP API:
  GET  /update_ele_data  -> JSON with power_state, usb_state, voltage, current, power, ele (kWh)
  GET  /get_state        -> JSON with fw_version, ap_ssid (and the AP password, which we drop)
  POST /set              -> form-style body such as "power=1" or "usb=0"

The firmware sends some numbers as strings. Field names follow the MIT-licensed
community integration https://github.com/juanillo62gm/HA-Panda-PWR.

This module has no Home Assistant imports so it can be unit tested in the
lightweight test suite.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PandaPwrState:
    """One reading of the Panda PWR. None means not reported."""

    power_on: bool | None = None
    usb_on: bool | None = None
    voltage: float | None = None
    current: float | None = None
    power: float | None = None
    energy: float | None = None


def _float(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _on(value) -> bool | None:
    number = _float(value)
    if number not in (0.0, 1.0):
        return None
    return number == 1.0


def parse_ele_data(data) -> PandaPwrState:
    """Parse a /update_ele_data reply. Raises ValueError if it is not a JSON object."""
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected Panda PWR reply: {type(data).__name__}")
    return PandaPwrState(
        power_on=_on(data.get("power_state")),
        usb_on=_on(data.get("usb_state")),
        voltage=_float(data.get("voltage")),
        current=_float(data.get("current")),
        power=_float(data.get("power")),
        energy=_float(data.get("ele")),
    )


def parse_device_info(data) -> dict[str, str]:
    """Keep only what we need from /get_state; the reply also holds the AP password."""
    if not isinstance(data, dict):
        return {}
    info = {}
    firmware = str(data.get("fw_version") or "").split(" ", 1)[0]
    if firmware:
        info["firmware_version"] = firmware
    if isinstance(data.get("ap_ssid"), str) and data["ap_ssid"]:
        info["ap_ssid"] = data["ap_ssid"]
    return info


def build_power(on: bool) -> str:
    return f"power={1 if on else 0}"


def build_usb(on: bool) -> str:
    return f"usb={1 if on else 0}"
