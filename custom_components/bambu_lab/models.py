from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, BRAND
from .coordinator import BambuDataUpdateCoordinator, BambuFilamentCoordinator


class BambuLabEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base Bambu entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Bambu  device."""
        return self.coordinator.get_printer_device()


class AMSEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base AMS entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this AMS entity."""
        return self.coordinator.get_ams_device(self.index)


class VirtualTrayEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines an External Spool entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this AMS entity."""
        return self.coordinator.get_virtual_tray_device(self.suffix)


class HotendRackEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base Hotend Rack entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Hotend Rack entity."""
        return self.coordinator.get_hotend_rack_device()


class AirPurifierEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Base entity for a purifier attached to the printer."""

    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._purifier_serial = coordinator.get_model().air_purifier.serial

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.get_air_purifier_device()

    @property
    def available(self) -> bool:
        printer = self.coordinator.get_model()
        purifier = printer.air_purifier
        return super().available and printer.info.online and purifier.ready and purifier.serial == self._purifier_serial


class FilamentInventoryEntity(CoordinatorEntity[BambuFilamentCoordinator]):
    """Defines a filament inventory entity. Subscribes to the filament
    coordinator but attaches to the printer device."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to the printer device via the printer coordinator."""
        return self.coordinator.printer_coordinator.get_printer_device()
