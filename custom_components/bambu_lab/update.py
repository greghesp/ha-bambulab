from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    LOGGER,
    Options,
    OPTION_NAME,
)

from .models import BambuLabEntity
from .definitions import BambuLabUpdateEntityDescription

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature

from .coordinator import BambuDataUpdateCoordinator

FIRMWARE_UPDATE_DESCRIPTION = BambuLabUpdateEntityDescription(
        key="firmware_update",
        translation_key="firmware_update",
        latest_ver_fn=lambda self: self.coordinator.get_model().upgrade.new_version,
        installed_ver_fn=lambda self: self.coordinator.get_model().upgrade.cur_version,
    )

async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    LOGGER.debug(f"UPDATE::async_setup_entry")

    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.get_option_enabled(Options.FIRMWAREUPDATE):
        async_add_entities([BambuLabUpdate(coordinator, FIRMWARE_UPDATE_DESCRIPTION, entry)])


class BambuLabUpdate(BambuLabEntity, UpdateEntity):
    """ Defined the Update """
    
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL |
        UpdateEntityFeature.PROGRESS
    )

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabUpdateEntityDescription,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the update."""
        super().__init__(coordinator=coordinator)
        self.coordinator = coordinator
        self.entity_description = description
        printer = self.coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_{description.key}"
    
    @property
    def available(self) -> bool:
        """Return True if the update is available."""
        return True
    
    @property
    def latest_version(self) -> str:
        """Return the latest version of the software available."""
        return self.entity_description.latest_ver_fn(self)
    
    @property
    def installed_version(self) -> str:
        """Return the version of the software installed."""
        return self.entity_description.installed_ver_fn(self)
    
    @property
    def release_url(self) -> str:
        """Return the release URL."""
        return self.coordinator.get_model().upgrade.release_url()
    
    @property
    def in_progress(self) -> bool:
        """Return True if update is in progress."""
        return self.coordinator.get_model().upgrade.upgrade_progress > 0
    
    @property
    def update_percentage(self) -> int | None:
        """Return the update progress percentage."""
        return self.coordinator.get_model().upgrade.upgrade_progress
    
    def install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self.coordinator.get_model().upgrade.install()
