"""Standalone Filament Inventory account coordinator."""
from __future__ import annotations

import copy
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BRAND, DOMAIN, FILAMENT_INVENTORY_DATA, LOGGER
from .pybambu.bambu_cloud import BambuCloud
from .pybambu.models import FilamentInventory
from .pybambu.utils import normalize_service_target


async def async_get_filament_inventory(call: ServiceCall) -> dict:
    """Return the latest cloud response for the selected inventory device."""
    try:
        target = normalize_service_target(call.data)
    except ValueError as err:
        return {"error": str(err)}

    device_id = target.get("device_id")
    if not device_id or target.get("entity_id"):
        return {"error": "Specify a filament inventory device_id without an entity_id"}
    registry = device_registry.async_get(call.hass)
    device = registry.async_get(device_id)
    if device is not None:
        for entry_id, coordinator in call.hass.data.get(FILAMENT_INVENTORY_DATA, {}).items():
            if hasattr(device, "config_entry_id"):
                belongs_to_entry = device.config_entry_id == entry_id
            else:
                belongs_to_entry = any(
                    entry_device.id == device.id
                    for entry_device in device_registry.async_entries_for_config_entry(registry, entry_id)
                )
            if belongs_to_entry and (DOMAIN, coordinator.unique_id_prefix) in device.identifiers:
                payload = coordinator.inventory.raw_data
                if payload is None:
                    return {"error": "Filament inventory has not been fetched"}
                return copy.deepcopy(payload)
    return {"error": "Filament inventory device not found"}


class BambuFilamentCoordinator(DataUpdateCoordinator):
    """Poll the account-level filament inventory independently of printers."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
        bambu_cloud: BambuCloud,
        interval_minutes: int,
    ) -> None:
        self.entry = entry
        self.bambu_cloud = bambu_cloud
        self.username = entry.data["username"]
        self.inventory = FilamentInventory()
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_filament_inventory",
            update_interval=timedelta(minutes=max(1, int(interval_minutes))),
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"filament_inventory_{self.username}")},
            name="Filament Inventory",
            manufacturer=BRAND,
            model="Filament Manager",
        )

    @property
    def unique_id_prefix(self) -> str:
        return f"filament_inventory_{self.username}"

    async def _async_update_data(self):
        if not self.bambu_cloud.bambu_connected:
            LOGGER.debug("Filament inventory: cloud auth not available; skipping fetch.")
            return self.inventory

        payload = await self.hass.async_add_executor_job(self.bambu_cloud.get_filaments)
        if payload is None:
            raise UpdateFailed("Failed to fetch filament inventory from Bambu cloud")

        self.inventory.update(payload)
        LOGGER.debug("Filament inventory updated: %s spools", self.inventory.total_spool_count)
        return self.inventory
