"""BIQU Panda devices that can be linked to a printer from the integration options.

Each linked device gets its own client, a Home Assistant device under the
printer, and entities from panda_entities.py. Supported:

  breath  Panda Breath chamber heater     WebSocket ws://<host>/ws
  status  Panda Status / Aura status light WebSocket ws://<host>/ws
  pwr     Panda PWR smart power switch     HTTP polling
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry

from .const import (
    CONF_PANDA_BREATH_HOST,
    CONF_PANDA_PWR_HOST,
    CONF_PANDA_STATUS_HOST,
    DOMAIN,
)
from .panda_breath import PandaBreathState, apply_message
from .panda_pwr_client import PandaPwrClient, async_test_pwr_connection
from .panda_status import PandaStatusState, apply_status_message
from .panda_ws_client import PandaWebSocketClient, async_test_connection

PANDA_BREATH = "breath"
PANDA_STATUS = "status"
PANDA_PWR = "pwr"


@dataclass(frozen=True)
class PandaKind:
    option: str
    identifier_suffix: str
    model: str


PANDA_KINDS: dict[str, PandaKind] = {
    PANDA_BREATH: PandaKind(CONF_PANDA_BREATH_HOST, "PandaBreath", "Panda Breath"),
    PANDA_STATUS: PandaKind(CONF_PANDA_STATUS_HOST, "PandaStatus", "Panda Status"),
    PANDA_PWR: PandaKind(CONF_PANDA_PWR_HOST, "PandaPWR", "Panda PWR"),
}


def create_client(hass: HomeAssistant, kind: str, host: str) -> Any:
    if kind == PANDA_BREATH:
        return PandaWebSocketClient(hass, host, PandaBreathState(), apply_message, "Panda Breath")
    if kind == PANDA_STATUS:
        return PandaWebSocketClient(hass, host, PandaStatusState(), apply_status_message, "Panda Status")
    if kind == PANDA_PWR:
        return PandaPwrClient(hass, host)
    raise ValueError(f"Unknown Panda device kind: {kind}")


async def async_test_panda_connection(hass: HomeAssistant, kind: str, host: str) -> bool:
    if kind == PANDA_PWR:
        return await async_test_pwr_connection(hass, host)
    return await async_test_connection(hass, host)


def firmware_version(kind: str, client) -> str | None:
    if kind == PANDA_BREATH:
        return client.state.firmware_version
    if kind == PANDA_PWR:
        return client.firmware_version
    return None


def device_identifier(coordinator, kind: str) -> tuple[str, str]:
    return (DOMAIN, f"{coordinator.config_entry.data['serial']}_{PANDA_KINDS[kind].identifier_suffix}")


@callback
def async_update_panda_device(coordinator, kind: str) -> None:
    """Fill in firmware and the printer link once known.

    Panda entities are added before the printer reports in and before the device
    first connects, so the values given at creation are often incomplete.
    """
    client = coordinator.panda_devices.get(kind)
    if client is None:
        return
    dev_reg = device_registry.async_get(coordinator.hass)
    device = dev_reg.async_get_device(identifiers={device_identifier(coordinator, kind)})
    if device is None:
        return
    changes = {}
    firmware = firmware_version(kind, client)
    if firmware and device.sw_version != firmware:
        changes["sw_version"] = firmware
    printer_device = coordinator.get_ha_printer_device()
    if printer_device is not None and device.via_device_id != printer_device.id:
        changes["via_device_id"] = printer_device.id
    if changes:
        dev_reg.async_update_device(device.id, **changes)


@callback
def async_setup_panda_devices(hass: HomeAssistant, entry: ConfigEntry, coordinator) -> dict[str, Any]:
    """Start a client for each linked Panda device and drop devices that were unlinked."""
    clients: dict[str, Any] = {}
    dev_reg = device_registry.async_get(hass)
    for kind, spec in PANDA_KINDS.items():
        host = str(entry.options.get(spec.option, "") or "").strip()
        if not host:
            device = dev_reg.async_get_device(identifiers={device_identifier(coordinator, kind)})
            if device is not None:
                dev_reg.async_remove_device(device.id)
            continue
        client = create_client(hass, kind, host)
        clients[kind] = client
        entry.async_on_unload(
            client.async_add_listener(lambda kind=kind: async_update_panda_device(coordinator, kind))
        )
        client.async_start(entry)
        entry.async_on_unload(client.async_stop)
    return clients
