"""Support for Bambu Lab through MQTT."""
from __future__ import annotations
import json
from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, LOGGER
from .definitions import SENSORS, BambuLabSensorEntityDescription
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED sensor based on a config entry."""

    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    LOGGER.debug(f"Entry {entry.data['serial']}")
    LOGGER.debug(f"Async Setup Sensor {coordinator.data}")
    async_add_entities(
        BambuLabSensor(coordinator, description, entry)
        for description in SENSORS
        if description.exists_fn(coordinator.data)
    )


class BambuLabSensor(BambuLabEntity, SensorEntity):
    """Representation of a BambuLab that is updated via MQTT."""

    entity_description: BambuLabSensorEntityDescription

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabSensorEntityDescription,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.data['serial']}_{description.key}"
        super().__init__(coordinator=coordinator)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        #LOGGER.debug(f"Extra Attributes: {self.entity_description.extra_attributes(self.coordinator.data)}")
        return self.entity_description.extra_attributes(self.coordinator.data)

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
