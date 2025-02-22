"""Image platform."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, Options
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity
from .definitions import BambuLabSensorEntityDescription
from .pybambu.const import Features

CHAMBER_IMAGE_SENSOR = BambuLabSensorEntityDescription(
        key="p1p_camera",
        translation_key="p1p_camera",
        value_fn=lambda self: self.coordinator.get_model().get_camera_image(),
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CAMERA_IMAGE) and coordinator.get_option_enabled(Options.IMAGECAMERA),
    )

COVER_IMAGE_SENSOR = BambuLabSensorEntityDescription(
        key="cover_image",
        translation_key="cover_image",
        value_fn=lambda self: self.coordinator.get_model().print_job.get_cover_image(),
        exists_fn=lambda coordinator: coordinator.get_model().info.has_bambu_cloud_connection or coordinator.get_option_enabled(Options.FTP)
    )

PICK_IMAGE_SENSOR = BambuLabSensorEntityDescription(
        key="pick_image",
        translation_key="pick_image",
        value_fn=lambda self: self.coordinator.get_model().print_job.get_pick_image(),
        exists_fn=lambda coordinator: coordinator.get_option_enabled(Options.FTP)
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""

    LOGGER.debug("IMAGE::async_setup_entry")
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if COVER_IMAGE_SENSOR.exists_fn(coordinator):
        cover_image = CoverImage(hass, coordinator, COVER_IMAGE_SENSOR)
        async_add_entities([cover_image])

    if PICK_IMAGE_SENSOR.exists_fn(coordinator):
        pick_image = PickImage(hass, coordinator, PICK_IMAGE_SENSOR)
        async_add_entities([pick_image])

    if CHAMBER_IMAGE_SENSOR.exists_fn(coordinator):
        chamber_image = ChamberImage(hass, coordinator, CHAMBER_IMAGE_SENSOR)
        async_add_entities([chamber_image])


class CoverImage(ImageEntity, BambuLabEntity):
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
        return self.coordinator.get_model().cover_image.get_image()

    @property
    def image_last_updated(self) -> datetime | None:
        """The time when the image was last updated."""
        return self.coordinator.get_model().cover_image.get_last_update_time()

    @property
    def available(self) -> bool:
        return self.coordinator.get_model().cover_image.get_last_update_time() != None
    
class ChamberImage(ImageEntity, BambuLabEntity):
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
        return self.coordinator.get_model().chamber_image.get_image()
    
    @property
    def image_last_updated(self) -> datetime | None:
        """The time when the image was last updated."""
        return self.coordinator.get_model().chamber_image.get_last_update_time()
    
    @property
    def available(self) -> bool:
        return self.coordinator.get_model().chamber_image.available and self.coordinator.get_option_enabled(Options.CAMERA)


class PickImage(ImageEntity, BambuLabEntity):
    """Representation of an object pick image entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BambuDataUpdateCoordinator,
        description: BambuLabSensorEntityDescription
    ) -> None:
        """Initialize the image entity."""
        super().__init__(hass=hass)
        super(BambuLabEntity, self).__init__(coordinator=coordinator)
        self._attr_content_type = "image/png"
        self._image_filename = None
        self.entity_description = description
        printer = self.coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_{description.key}"

    def image(self) -> bytes | None:
        """Return bytes of image."""
        return self.coordinator.get_model().pick_image.get_image()

    @property
    def image_last_updated(self) -> datetime | None:
        """The time when the image was last updated."""
        return self.coordinator.get_model().pick_image.get_last_update_time()

    @property
    def available(self) -> bool:
        return self.image() is not None
