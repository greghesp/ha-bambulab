from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, BRAND
from .coordinator import BambuDataUpdateCoordinator


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


class FireExtinguisherEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base Fire Extinguisher entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Fire Extinguisher entity."""
        return self.coordinator.get_fire_extinguisher_device()


class ToolModuleEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base Tool Module entity (laser, rotary, cutter)."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Tool Module entity."""
        return self.coordinator.get_tool_module_device(self.module_serial)


class HotendRackEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base Hotend Rack entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Hotend Rack entity."""
        return self.coordinator.get_hotend_rack_device()
