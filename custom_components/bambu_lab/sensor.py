"""Support for Bambu Lab through MQTT."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity, RestoredExtraData
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ENTRY_TYPE, ENTRY_TYPE_MAKERWORLD, LOGGER, MAKERWORLD_DATA
from .definitions import (
    AIR_PURIFIER_SENSORS,
    PRINTER_SENSORS,
    VIRTUAL_TRAY_SENSORS,
    AMS_SENSORS,
    HOTEND_RACK_SENSORS,
    HOTEND_RACK_HOTEND_SENSORS,
    H3C_FAN_ENTITY_KEYS,
    X2D_TRANSLATION_KEYS,
    MAKERWORLD_SENSORS,
    FILAMENT_INVENTORY_SENSORS,
    BambuLabAMSSensorEntityDescription,
    BambuLabHotendRackSensorEntityDescription,
    BambuLabMakerWorldSensorEntityDescription,
    BambuLabSensorEntityDescription,
)
from .coordinator import BambuDataUpdateCoordinator, BambuFilamentCoordinator
from . import panda_entities
from .makerworld import MakerWorldDataUpdateCoordinator, MakerWorldEntity
from .models import AirPurifierEntity, BambuLabEntity, AMSEntity, VirtualTrayEntity, HotendRackEntity, FilamentInventoryEntity
from .pybambu.const import Features, Printers


def _migrate_h3c_storage_entities(registry, entry_id, printer):
    """Preserve existing registry entries while renaming the initial USB sensors."""
    if printer.device_type != Printers.H3C:
        return
    keys = {
        "usb_connection": "external_storage_connection",
        "usb_storage_total": "external_storage_total",
        "usb_storage_used": "external_storage_used",
        "usb_storage_free": "external_storage_free",
    }
    for old_key, new_key in keys.items():
        old_id = registry.async_get_entity_id("sensor", DOMAIN, f"{printer.serial}_{old_key}")
        if old_id is None:
            continue
        old = registry.async_get(old_id)
        if old.config_entry_id != entry_id:
            continue
        unique_id = f"{printer.serial}_{new_key}"
        if registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None:
            continue
        new_id = f"sensor.h3c_{printer.serial.lower()}_{new_key}"
        if registry.async_get(new_id) is not None:
            # Keep a conflicting entity's ID; still migrate the unique ID so
            # setup reuses this registry entry instead of creating a duplicate.
            registry.async_update_entity(old_id, new_unique_id=unique_id)
        else:
            registry.async_update_entity(old_id, new_unique_id=unique_id, new_entity_id=new_id)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BambuLab sensor based on a config entry."""

    if entry.data.get(ENTRY_TYPE) == ENTRY_TYPE_MAKERWORLD:
        coordinator = hass.data[MAKERWORLD_DATA][entry.entry_id]
        for sensor in MAKERWORLD_SENSORS:
            async_add_entities([BambuLabMakerWorldSensor(coordinator, sensor)])
        return

    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Panda devices are on the network in their own right, so their
    # entities don't wait for the printer to report in.
    async_add_entities(panda_entities.platform_entities("sensor", coordinator))

    if not coordinator.get_model().has_full_printer_data:
        return

    _migrate_h3c_storage_entities(er.async_get(hass), entry.entry_id, coordinator.get_model().info)

    if coordinator.get_model().air_purifier.ready:
        for sensor in AIR_PURIFIER_SENSORS:
            async_add_entities([BambuLabAirPurifierSensor(coordinator, sensor)])

    for sensor in VIRTUAL_TRAY_SENSORS:
        if sensor.exists_fn(coordinator):
            if coordinator.get_model().supports_feature(Features.DUAL_NOZZLES):
                async_add_entities([BambuLabVirtualTraySensor(coordinator, sensor, 1, "")])  # Left
                async_add_entities([BambuLabVirtualTraySensor(coordinator, sensor, 0, "2")]) # Right
            else:
                async_add_entities([BambuLabVirtualTraySensor(coordinator, sensor, 0, "")])

    for sensor in AMS_SENSORS:
        for index in coordinator.get_model().ams.data.keys():
            ams_instance = coordinator.get_model().ams.data[index]
            # push_status can arrive before complete get_version metadata and create
            # a placeholder AMS with no serial. Device/entity identity depends on the
            # real AMS serial, so wait for version metadata instead of registering a
            # transient placeholder that HA cannot later reconcile cleanly.
            if ams_instance is None or not ams_instance.serial:
                continue
            if sensor.exists_fn(coordinator, index):
                async_add_entities([BambuLabAMSSensor(coordinator, sensor, index)])

    if coordinator.get_model().supports_feature(Features.HOTEND_RACK):
        for sensor in HOTEND_RACK_SENSORS:
            if sensor.exists_fn(coordinator):
                async_add_entities([BambuLabHotendRackSensor(coordinator, sensor)])
        for sensor in HOTEND_RACK_HOTEND_SENSORS:
            if sensor.exists_fn(coordinator):
                async_add_entities([BambuLabHotendSensor(coordinator, sensor)])

    for sensor in PRINTER_SENSORS:
        if sensor.exists_fn(coordinator):
            sensor_class = BambuLabRestoreSensor if sensor.is_restoring else BambuLabSensor
            async_add_entities([sensor_class(coordinator, sensor)])

    if coordinator.filament_inventory is not None:
        for sensor in FILAMENT_INVENTORY_SENSORS:
            async_add_entities([BambuLabFilamentInventorySensor(coordinator.filament_inventory, sensor)])


class BambuLabAirPurifierSensor(AirPurifierEntity, SensorEntity):
    """A measurement belonging to the attached air purifier."""

    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._purifier_serial}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.value_fn(self)


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
        key = description.key
        if printer.device_type == Printers.H3C and key in H3C_FAN_ENTITY_KEYS:
            key = H3C_FAN_ENTITY_KEYS[key]
            self._attr_translation_key = key
        self._attr_unique_id = f"{printer.serial}_{key}"
        if printer.device_type == Printers.X2D and description.key in X2D_TRANSLATION_KEYS:
            self._attr_translation_key = X2D_TRANSLATION_KEYS[description.key]
        if description.options_fn is not None:
            self._attr_options = description.options_fn(coordinator)

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
    """A BambuLabSensor that restores the print start time on restart.

    The printer never reports when a print started, so the integration records
    it when it sees the print begin. That is lost if Home Assistant restarts
    mid-print (and Bambu Cloud only backfills it for some jobs). We persist the
    start time together with an identity for the print it belongs to, and only
    restore it if the printer is still on that same print.
    """

    def __init__(self, coordinator, description):
        super().__init__(coordinator, description)
        self._restored_start_time = None
        self._restored_job_key = None

    @staticmethod
    def _job_key(job) -> str | None:
        """Identify the current print, or None if the printer hasn't told us yet."""
        if not job.gcode_file and not job.subtask_name:
            return None
        return "|".join((str(job.task_id or ""), job.gcode_file or "", job.subtask_name or ""))

    @property
    def extra_restore_state_data(self) -> RestoredExtraData | None:
        """Persist the live start time and the print it belongs to."""
        job = self.coordinator.get_model().print_job
        job_key = self._job_key(job)
        if job.start_time is None or job_key is None:
            return None
        return RestoredExtraData({
            "start_time": dt_util.as_utc(job.start_time).isoformat(),
            "job_key": job_key,
        })

    async def async_added_to_hass(self) -> None:
        """Load any start time saved before the last restart."""
        await super().async_added_to_hass()
        extra_data = await self.async_get_last_extra_data()
        if extra_data is None:
            return
        data = extra_data.as_dict()
        start_time = dt_util.parse_datetime(str(data.get("start_time", "")))
        if start_time is None or start_time.tzinfo is None or not data.get("job_key"):
            LOGGER.debug(f"Ignoring unusable restored start time data: {data}")
            return
        self._restored_start_time = dt_util.as_utc(start_time)
        self._restored_job_key = data["job_key"]
        LOGGER.debug(f"Restored start time {self._restored_start_time} for print '{self._restored_job_key}'")

    def _restore_start_time(self, job) -> datetime | None:
        """Return the saved start time if the printer is still on the same print."""
        if self._restored_start_time is None:
            return None
        job_key = self._job_key(job)
        if job_key is None:
            # Printer hasn't reported the current job yet; try again on the next update.
            return None
        if job_key != self._restored_job_key or self._restored_start_time > dt_util.utcnow():
            LOGGER.debug(f"Discarding restored start time; current print is '{job_key}'")
            self._restored_start_time = None
            self._restored_job_key = None
            return None
        # Hand it back to pybambu so usage hours are also counted for this print.
        job.start_time = self._restored_start_time
        LOGGER.debug(f"Injected restored start time into pybambu: {job.start_time}")
        return job.start_time

    def _start_time_value_fn(self) -> datetime | None:
        """Live start time, falling back to the one saved before a restart."""
        job = self.coordinator.get_model().print_job
        if job.start_time is not None:
            return dt_util.as_utc(job.start_time)
        return self._restore_start_time(job)


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


class BambuLabHotendRackSensor(HotendRackEntity, SensorEntity):
    """Sensor for Hotend Rack system-level data."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabHotendRackSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        printer = coordinator.get_model().info
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_HotendRack_{description.key}"

    @property
    def extra_state_attributes(self) -> dict:
        return self.entity_description.extra_attributes(self)

    @property
    def native_value(self) -> datetime | StateType:
        return self.entity_description.value_fn(self)

    @property
    def available(self) -> bool:
        return self.entity_description.available_fn(self)


class BambuLabHotendSensor(HotendRackEntity, SensorEntity):
    """Sensor for an individual hotend in the Hotend Rack."""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabHotendRackSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        printer = coordinator.get_model().info
        self._attr_unique_id = f"{printer.device_type}_{printer.serial}_HotendRack_{description.key}"

    @property
    def extra_state_attributes(self) -> dict:
        return self.entity_description.extra_attributes(self)

    @property
    def native_value(self) -> datetime | StateType:
        return self.entity_description.value_fn(self)

    @property
    def available(self) -> bool:
        return self.entity_description.available_fn(self)


class BambuLabMakerWorldSensor(MakerWorldEntity, SensorEntity):
    """A MakerWorld creator stat for the linked Bambu Lab account."""

    def __init__(
            self,
            coordinator: MakerWorldDataUpdateCoordinator,
            description: BambuLabMakerWorldSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id_prefix}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.profile is None:
            return None
        return self.entity_description.value_fn(self)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.profile is not None

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        if self.profile is None:
            return {}
        return self.entity_description.extra_attributes(self)


class BambuLabFilamentInventorySensor(FilamentInventoryEntity, SensorEntity):
    """Account-level filament inventory, polled from the Bambu cloud."""

    def __init__(
            self,
            coordinator: BambuFilamentCoordinator,
            description: BambuLabSensorEntityDescription
    ) -> None:
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        printer = coordinator.printer_coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict:
        return self.entity_description.extra_attributes(self)

    @property
    def native_value(self) -> datetime | StateType:
        return self.entity_description.value_fn(self)
