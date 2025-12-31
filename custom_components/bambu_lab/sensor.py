"""Support for Bambu Lab through MQTT."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .definitions import (
    PRINTER_SENSORS,
    VIRTUAL_TRAY_SENSORS,
    AMS_SENSORS,
    BambuLabAMSSensorEntityDescription,
    BambuLabSensorEntityDescription,
)
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity, AMSEntity, VirtualTrayEntity
from .pybambu.const import Features


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BambuLab sensor based on a config entry."""
    
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.get_model().has_full_printer_data:
        return

    for sensor in VIRTUAL_TRAY_SENSORS:
        if sensor.exists_fn(coordinator):
            if coordinator.get_model().supports_feature(Features.DUAL_NOZZLES):
                async_add_entities([BambuLabVirtualTraySensor(coordinator, sensor, 1, "")])  # Left
                async_add_entities([BambuLabVirtualTraySensor(coordinator, sensor, 0, "2")]) # Right
            else:
                async_add_entities([BambuLabVirtualTraySensor(coordinator, sensor, 0, "")])

    for sensor in AMS_SENSORS:
        for index in coordinator.get_model().ams.data.keys():
            if sensor.exists_fn(coordinator, index):
                async_add_entities([BambuLabAMSSensor(coordinator, sensor, index)])

    for sensor in PRINTER_SENSORS:    
        if sensor.exists_fn(coordinator):
            async_add_entities([BambuLabSensor(coordinator, sensor)])


class BambuLabSensor(BambuLabEntity, SensorEntity):
    """Representation of a BambuLab that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        printer = coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self.entity_description.extra_attributes(self)

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entity_description.available_fn(self)

    @property
    def icon(self) -> str | None:
        """Return a dynamic icon if needed"""
        return self.entity_description.icon_fn(self) if self.entity_description.icon_fn else self.entity_description.icon
    

class BambuLabAMSSensor(AMSEntity, SensorEntity):
    """Representation of a BambuLab AMS that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabAMSSensorEntityDescription,
            index: int
    ) -> None:
        """Initialise the sensor"""
        super().__init__(coordinator=coordinator)
        self.index = index
        printer = coordinator.get_model().info
        ams_instance = coordinator.get_model().ams.data[index]
        self.entity_description = description
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_AMS_{ams_instance.serial}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self.entity_description.extra_attributes(self)

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entity_description.available_fn(self)


class BambuLabVirtualTraySensor(VirtualTrayEntity, SensorEntity):
    """Representation of a BambuLab AMS that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabSensorEntityDescription,
            index: int,
            suffix: str
    ) -> None:
        """Initialise the sensor"""
        super().__init__(coordinator=coordinator)
        printer = coordinator.get_model().info
        self.index = index
        self.suffix = suffix
        self.entity_description = description
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_ExternalSpool{suffix}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self.entity_description.extra_attributes(self)

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entity_description.available_fn(self)
