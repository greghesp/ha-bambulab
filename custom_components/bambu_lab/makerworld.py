"""MakerWorld creator stats for a cloud connected Bambu Lab account.

MakerWorld profiles hang off the same account the cloud connection already
authenticates against, so the stats shown on a creator's profile page can be
polled without a second login. The profile endpoint is public data keyed off
the account's numeric uid - see BambuCloud.get_makerworld_profile().
"""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, ENTRY_TYPE, ENTRY_TYPE_MAKERWORLD, LOGGER, LOGGERFORHA
from .pybambu.makerworld import MakerWorldProfile, as_int

# These are slow moving vanity numbers and the endpoint is undocumented, so poll
# gently. On failure the interval backs off up to MAX_SCAN_INTERVAL so a blocked
# or broken endpoint isn't hammered every quarter hour.
SCAN_INTERVAL = timedelta(hours=4)
MAX_SCAN_INTERVAL = timedelta(hours=24)


def account_key(entry: ConfigEntry) -> str:
    """Return the account identifier stored on this MakerWorld entry."""
    options = entry.data
    if options.get(ENTRY_TYPE) != ENTRY_TYPE_MAKERWORLD:
        return ""
    if not options.get('auth_token', ''):
        return ""
    return options.get('username', '') or ""


def remove_legacy_makerworld_device(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the former printer-owned MakerWorld device during upgrade."""
    devices = device_registry.async_get(hass)
    entities = entity_registry.async_get(hass)
    for device in device_registry.async_entries_for_config_entry(devices, entry.entry_id):
        if device.manufacturer != "MakerWorld" or device.model != "Creator profile":
            continue

        for entity in tuple(entities.entities.values()):
            if entity.config_entry_id == entry.entry_id and entity.device_id == device.id:
                entities.async_remove(entity.entity_id)
        devices.async_remove_device(device.id)


class MakerWorldDataUpdateCoordinator(DataUpdateCoordinator[MakerWorldProfile]):
    """Polls the MakerWorld creator profile for the linked account."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, bambu_cloud) -> None:
        self._entry = entry
        self._cloud = bambu_cloud
        self._account_key = account_key(entry)
        self._uid: str | None = None
        # As with the printer coordinator, use the HA facing logger so routine
        # updates don't fill the log.
        super().__init__(
            hass,
            LOGGERFORHA,
            name=f"{DOMAIN}_makerworld",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> MakerWorldProfile:
        try:
            return await self._fetch()
        except UpdateFailed:
            self._back_off()
            raise
        except Exception as e:
            self._back_off()
            raise UpdateFailed(f"MakerWorld profile update failed: {e}") from e

    async def _fetch(self) -> MakerWorldProfile:
        if self._uid is None:
            # Only needed for the public profile fallback - the authenticated
            # endpoint knows which account is asking.
            self._uid = await self.hass.async_add_executor_job(self._cloud.get_uid)

        data = await self.hass.async_add_executor_job(
            self._cloud.get_makerworld_profile, self._uid
        )
        if not data:
            raise UpdateFailed("No response from the MakerWorld profile endpoint")
        if not as_int(data.get('uid')):
            # A deleted or unknown uid answers 200 with an all zero profile rather
            # than a 404, so treat a missing uid as no profile instead of
            # publishing a wall of zeroes.
            raise UpdateFailed(f"No MakerWorld profile for uid {self._uid}")

        # Points and boost tokens are account private and need the auth token,
        # unlike the profile above. They are fetched best effort: if the token
        # isn't accepted for them, those sensors go unavailable while the
        # profile ones carry on.
        points = await self.hass.async_add_executor_job(self._cloud.get_makerworld_points)
        boosts = await self.hass.async_add_executor_job(self._cloud.get_makerworld_boosts)

        profile = MakerWorldProfile.from_json(data, points, boosts)
        LOGGER.debug(
            f"MakerWorld profile updated: level={profile.level} "
            f"downloads={profile.total_downloads} prints={profile.total_prints} "
            f"points={profile.points} boost_tokens={profile.boost_tokens} "
            f"boosts_received={profile.boosts_received}"
        )
        # A good response ends any back off.
        self.update_interval = SCAN_INTERVAL
        return profile

    def _back_off(self) -> None:
        interval = (self.update_interval or SCAN_INTERVAL) * 2
        self.update_interval = min(interval, MAX_SCAN_INTERVAL)
        LOGGER.debug(f"MakerWorld polling backed off to {self.update_interval}")

    @property
    def device_info(self) -> DeviceInfo:
        profile = self.data
        name = "MakerWorld"
        if profile is not None and profile.name:
            name = f"MakerWorld ({profile.name})"
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"makerworld_account_{self._account_key}")},
            name=name,
            manufacturer="MakerWorld",
            model="Creator profile",
        )
        if profile is not None and profile.profile_url:
            device_info["configuration_url"] = profile.profile_url
        return device_info

    @property
    def unique_id_prefix(self) -> str:
        return f"makerworld_{self._account_key}"


def create_makerworld_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, bambu_cloud
) -> MakerWorldDataUpdateCoordinator:
    """Build the coordinator for a standalone MakerWorld entry."""
    return MakerWorldDataUpdateCoordinator(hass, entry, bambu_cloud)


class MakerWorldEntity(CoordinatorEntity[MakerWorldDataUpdateCoordinator]):
    """Base entity for the account level MakerWorld sensors."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    @property
    def profile(self) -> MakerWorldProfile | None:
        return self.coordinator.data
