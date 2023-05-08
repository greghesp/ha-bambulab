"""Support for Bambu Lab through MQTT."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator
from .definitions import PRINTER_BINARY_SENSORS, BambuLabBinarySensorEntityDescription
from .models import BambuLabEntity


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BambuLab sensor based on a config entry."""
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for sensor in PRINTER_BINARY_SENSORS:    
        if sensor.exists_fn(coordinator):
            async_add_entities([BambuLabBinarySensor(coordinator, sensor, entry)])


class BambuLabBinarySensor(BambuLabEntity, BinarySensorEntity):
    """Representation of a BambuLab that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabBinarySensorEntityDescription,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self.coordinator = coordinator
        self.entity_description = description
        printer = self.coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_{description.key}"
    
    @property
    def is_on(self) -> bool:
        """Return if binary sensor is on."""
        return self.entity_description.is_on_fn(self)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self.entity_description.extra_attributes(self)
