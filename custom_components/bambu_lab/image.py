"""Image platform."""
from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity
from .definitions import P1P_IMAGE_SENSOR, BambuLabSensorEntityDescription

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""

    LOGGER.debug("IMAGE::async_setup_entry")
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if P1P_IMAGE_SENSOR.exists_fn(coordinator):
        P1PCamera = P1PImage(hass, coordinator, P1P_IMAGE_SENSOR)
        async_add_entities([P1PCamera])
        coordinator.P1PCamera = P1PCamera


class P1PImage(ImageEntity, BambuLabEntity):
    """Representation of an image entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BambuDataUpdateCoordinator,
        description: BambuLabSensorEntityDescription
    ) -> None:
        """Initialize the image entity."""
        super().__init__(hass=hass)
        super(BambuLabEntity, self).__init__(coordinator=coordinator)
        self._attr_content_type = "image/jpeg"
        self._image_filename = None
        self.entity_description = description
        printer = self.coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_{description.key}"

    def image(self) -> bytes | None:
        """Return bytes of image."""

        LOGGER.debug("P1PImage::async_image")
        return self.coordinator.get_model().p1p_camera.get_jpeg()

    def jpeg_updated(self):
        self._attr_image_last_updated = dt_util.utcnow()
