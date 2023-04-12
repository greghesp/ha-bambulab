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
        #LOGGER.debug("device_info() called")
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.info.serial)},
            name=f"{self.coordinator.data.info.device_type}_{self.coordinator.data.info.serial}",
            manufacturer=BRAND,
            model=self.coordinator.data.info.device_type,
            hw_version=self.coordinator.data.info.hw_ver,
            sw_version=self.coordinator.data.info.sw_ver,
        )


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
        return self.coordinator.get_virtual_tray_device()
