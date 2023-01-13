from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator


class BambuLabEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base Bambu entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Bambu  device."""

        # TODO: Populate with device name and serial
        return DeviceInfo(
            identifiers={
                (DOMAIN, "123123")
            },
            name="Change",
            model="X1C",
            manufacturer="Bambu Lab",
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
        )