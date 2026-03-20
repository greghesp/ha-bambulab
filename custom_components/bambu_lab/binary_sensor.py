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
    VIRTUAL_TRAY_BINARY_SENSORS,
    FIRE_EXTINGUISHER_BINARY_SENSORS,
    LASER_BINARY_SENSORS,
    ROTARY_BINARY_SENSORS,
    BambuLabAMSBinarySensorEntityDescription,
    BambuLabBinarySensorEntityDescription,
)
from .models import (
    AMSEntity,
    BambuLabEntity,
    FireExtinguisherEntity,
    ToolModuleEntity,
    VirtualTrayEntity,
)
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

    if coordinator.get_model().supports_feature(Features.FIRE_EXTINGUISHER):
        for sensor in FIRE_EXTINGUISHER_BINARY_SENSORS:
            if sensor.exists_fn(coordinator):
                async_add_entities([BambuLabFireExtinguisherBinarySensor(coordinator, sensor)])

    for module in coordinator.get_model().extruder_tool.get_modules_by_type("laser"):
        for sensor in LASER_BINARY_SENSORS:
            if sensor.exists_fn(coordinator):
                async_add_entities([BambuLabToolModuleBinarySensor(coordinator, sensor, module.serial)])

    for module in coordinator.get_model().extruder_tool.get_modules_by_type("rotary"):
        for sensor in ROTARY_BINARY_SENSORS:
            if sensor.exists_fn(coordinator):
                async_add_entities([BambuLabToolModuleBinarySensor(coordinator, sensor, module.serial)])

    for sensor in PRINTER_BINARY_SENSORS:
        if sensor.exists_fn(coordinator):
            async_add_entities([BambuLabBinarySensor(coordinator, sensor)])

    for sensor in AMS_BINARY_SENSORS:
        for index in coordinator.get_model().ams.data.keys():
            if coordinator.get_model().ams.data[index] is not None:
                if sensor.exists_fn(coordinator, index):
                    async_add_entities([BambuLabAMSBinarySensor(coordinator, sensor, index)])

    for sensor in VIRTUAL_TRAY_BINARY_SENSORS:    
        if sensor.exists_fn(coordinator):
            if coordinator.get_model().supports_feature(Features.DUAL_NOZZLES):
                async_add_entities([BambuLabExternalSpoolBinarySensor(coordinator, sensor, 1, "")])  # Left
                async_add_entities([BambuLabExternalSpoolBinarySensor(coordinator, sensor, 0, "2")]) # Right
            else:
                async_add_entities([BambuLabExternalSpoolBinarySensor(coordinator, sensor, 0, "")])


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
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entity_description.available_fn(self)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self.entity_description.extra_attributes(self)


class BambuLabAMSBinarySensor(AMSEntity, BambuLabBinarySensor):
    """Representation of a BambuLab AMS binary sensor that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabAMSBinarySensorEntityDescription,
            index: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        printer = coordinator.get_model().info
        ams_instance = coordinator.get_model().ams.data[index]
        self.index = index
        self.entity_description = description
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_AMS_{ams_instance.serial}_{description.key}"


class BambuLabExternalSpoolBinarySensor(VirtualTrayEntity, BambuLabBinarySensor):
    """Representation of a BambuLab External Spool binary sensor that is updated via MQTT."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabBinarySensorEntityDescription,
            index: int,
            suffix: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        printer = coordinator.get_model().info
        self.index = index
        self.suffix = suffix
        self.entity_description = description
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_ExternalSpool{suffix}_{description.key}"


class BambuLabFireExtinguisherBinarySensor(FireExtinguisherEntity, BambuLabBinarySensor):
    """Representation of a BambuLab Fire Extinguisher binary sensor."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        printer = coordinator.get_model().info
        self.entity_description = description
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_FireExtinguisher_{description.key}"


class BambuLabToolModuleBinarySensor(ToolModuleEntity, BambuLabBinarySensor):
    """Representation of a BambuLab Tool Module binary sensor."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabBinarySensorEntityDescription,
            module_serial: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self.module_serial = module_serial
        printer = coordinator.get_model().info
        self.entity_description = description
        self._attr_unique_id = f"{printer.device_type}_{module_serial}_{description.key}"
