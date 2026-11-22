"""Standalone Filament Inventory account coordinator."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BRAND, DOMAIN, LOGGER
from .pybambu.bambu_cloud import BambuCloud
from .pybambu.models import FilamentInventory


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
