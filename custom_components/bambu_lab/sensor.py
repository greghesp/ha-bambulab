"""Support for Bambu Lab through MQTT."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

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
            sensor_class = BambuLabRestoreSensor if sensor.is_restoring else BambuLabSensor
            async_add_entities([sensor_class(coordinator, sensor)])


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


class BambuLabRestoreSensor(BambuLabSensor, RestoreEntity):
    """A BambuLabSensor that restores its state on restart."""

    def __init__(self, coordinator, description):
        super().__init__(coordinator, description)
        self._restored_state = None

    async def async_added_to_hass(self) -> None:
        """Handle restore logic"""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in ("unknown", "unavailable"):
                self._restored_state = last_state.state
                LOGGER.debug(f"State pulled from Restore Entity: {last_state}")

    def _start_time_avail_fn(self) -> bool:
        """
        Availability callback with restored state handling for LAN only Start Time
        """
        model = self.coordinator.get_model()
        if model.print_job.start_time is not None:
            return True
        job = model.print_job
        has_end_time = job.end_time is not None
        is_lan_mode = model.info.mqtt_mode == "local"
        if is_lan_mode and has_end_time and self._restored_state is not None:
            return True
        return False

    def _start_time_value_fn(self):
        """
        Value callback with restored state handling for LAN only Start Time
        """
        model = self.coordinator.get_model()
        live_value = model.print_job.start_time
        if live_value is not None:
            return dt_util.as_local(live_value).replace(tzinfo=None)
        job = model.print_job
        is_printing = job.gcode_state.lower() in ("running", "pause")
        has_end_time = job.end_time is not None
        is_lan_mode = model.info.mqtt_mode == "local"
        if is_printing and is_lan_mode and has_end_time and self._restored_state is not None:
            if isinstance(self._restored_state, str):
                try:
                    dt_value = dt_util.parse_datetime(self._restored_state)
                    if dt_value.tzinfo is None:
                        dt_value = dt_value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
                    job.start_time = dt_value
                    LOGGER.debug(f"LAN Mode: Injected restored start_time into pybambu: {dt_value}")
                except (ValueError, TypeError):
                    LOGGER.error("Failed to parse restored start_time string for pybambu")
                    return None
            return self._restored_state
        return None


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
