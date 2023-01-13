from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator


class BambuLabEntity(CoordinatorEntity[BambuDataUpdateCoordinator]):
    """Defines a base WLED entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this WLED device."""

        LOGGER.debug(f"device info {self}")
        return DeviceInfo(
            identifiers={
                (DOMAIN, "123123")
            },
            name="Change",
            manufacturer="Bambu Lab",
        )
