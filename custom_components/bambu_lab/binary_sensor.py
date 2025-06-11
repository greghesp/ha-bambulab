"""Support for Bambu Lab through MQTT."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator
from .definitions import (
    AMS_BINARY_SENSORS,
    PRINTER_BINARY_SENSORS,
    BambuLabBinarySensorEntityDescription,
)
from .models import (
    AMSEntity,
    BambuLabEntity,
)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BambuLab sensor based on a config entry."""
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for sensor in PRINTER_BINARY_SENSORS:    
        if sensor.exists_fn(coordinator):
            async_add_entities([BambuLabBinarySensor(coordinator, sensor)])

    for sensor in AMS_BINARY_SENSORS:
        for index in coordinator.get_model().ams.data.keys():
            if coordinator.get_model().ams.data[index] is not None:
                async_add_entities([BambuLabAMSBinarySensor(coordinator, sensor, index)])


class BambuLabBinarySensor(BambuLabEntity, BinarySensorEntity):
    """Representation of a BambuLab binary sensor that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabBinarySensorEntityDescription
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

class BambuLabAMSBinarySensor(AMSEntity, BambuLabBinarySensor):
    """Representation of a BambuLab AMS binary sensor that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabBinarySensorEntityDescription,
            index: int
    ) -> None:
        """Initialize the sensor."""
        self.index = index
        super().__init__(coordinator=coordinator, description=description)
        printer = coordinator.get_model().info
        ams_instance = coordinator.get_model().ams.data[index]
        self.entity_description = description
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_AMS_{ams_instance.serial}_{description.key}"
