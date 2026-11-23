"""Protocol helpers for the BIQU (BIGTREETECH) Panda Status / Panda Aura status light.

Like the Panda Breath, it serves an unauthenticated JSON WebSocket at
ws://<host>/ws with root keys such as "settings" and "printer". Field names
follow the MIT-licensed community integration
https://github.com/ping-localhost/panda-status:

  settings.list2[1].brightness  idle light brightness (0 = off)
  settings.current_mode         light effect mode (0 = music, 1 = H2D)
  printer.state / printer.sn    bound printer status and serial
  {"settings": {"rgb_info_brightness": "100"}}  set idle light brightness
  {"settings": {"rgb_info_mode": 1}}            set light effect mode

This module has no Home Assistant imports so it can be unit tested in the
lightweight test suite.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

EFFECT_MODES = {0: "music", 1: "h2d"}
EFFECT_MODE_IDS = {name: number for number, name in EFFECT_MODES.items()}

IDLE_LIGHT_ON_BRIGHTNESS = "100"


@dataclass(frozen=True)
class PandaStatusState:
    """Last known Panda Status state. None means not reported yet."""

    idle_light_on: bool | None = None
    effect_mode: str | None = None
    printer_state: str | None = None
    bound_printer_serial: str | None = None


def _int(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _settings_changes(settings: dict) -> dict:
    changes = {}
    mode = EFFECT_MODES.get(_int(settings.get("current_mode", settings.get("rgb_info_mode"))))
    if mode is not None:
        changes["effect_mode"] = mode
    idle = settings.get("list2")
    if isinstance(idle, list) and len(idle) > 1 and isinstance(idle[1], dict):
        brightness = _int(idle[1].get("brightness", 0))
        if brightness is not None:
            changes["idle_light_on"] = brightness > 0
    elif "rgb_info_brightness" in settings:
        brightness = _int(settings["rgb_info_brightness"])
        if brightness is not None:
            changes["idle_light_on"] = brightness > 0
    return changes


def _printer_changes(printer: dict) -> dict:
    changes = {}
    if isinstance(printer.get("state"), str) and printer["state"]:
        changes["printer_state"] = printer["state"]
    if isinstance(printer.get("sn"), str) and printer["sn"]:
        changes["bound_printer_serial"] = printer["sn"]
    return changes


def apply_status_message(state: PandaStatusState, message: dict[str, Any]) -> PandaStatusState:
    """Return a new state with the fields of one device message applied."""
    if not isinstance(message, dict):
        return state
    changes = {}
    if isinstance(message.get("settings"), dict):
        changes.update(_settings_changes(message["settings"]))
    if isinstance(message.get("printer"), dict):
        changes.update(_printer_changes(message["printer"]))
    return replace(state, **changes) if changes else state


def build_idle_light(on: bool) -> list[dict[str, Any]]:
    return [{"settings": {"rgb_info_brightness": IDLE_LIGHT_ON_BRIGHTNESS if on else "0"}}]


def build_effect_mode(mode: str) -> list[dict[str, Any]]:
    if mode not in EFFECT_MODE_IDS:
        raise ValueError(f"Unknown Panda Status light effect mode: {mode}")
    return [{"settings": {"rgb_info_mode": EFFECT_MODE_IDS[mode]}}]
