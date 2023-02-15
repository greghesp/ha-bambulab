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

        # TODO: Populate with device name and serial
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
        """Return device information about this AMS device."""

        return DeviceInfo(
            identifiers={
                (DOMAIN, "AMS123")
            },
            name="AMS 1",
            model="AMS",
            manufacturer="Bambu Lab",
            hw_version=self.coordinator.data.ams.version,
        )
