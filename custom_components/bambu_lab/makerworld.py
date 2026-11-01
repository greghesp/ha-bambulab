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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER, LOGGERFORHA
from .pybambu.makerworld import MakerWorldProfile, as_int

# These are slow moving vanity numbers and the endpoint is undocumented, so poll
# gently. On failure the interval backs off up to MAX_SCAN_INTERVAL so a blocked
# or broken endpoint isn't hammered every quarter hour.
SCAN_INTERVAL = timedelta(minutes=15)
MAX_SCAN_INTERVAL = timedelta(hours=2)


def account_key(entry: ConfigEntry) -> str:
    """The cloud account a config entry is bound to, or '' for LAN only setups.

    The cloud login stores the account as its mqtt username, 'u_<uid>'."""
    options = entry.options
    if not options.get('auth_token', ''):
        return ""
    return options.get('username', '') or ""


def owns_makerworld_entities(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Whether this config entry is the one that publishes the account's sensors.

    MakerWorld stats belong to the account, not to a printer, so with several
    printers on one account only one entry may create them. Picking the lowest
    entry id keeps that choice stable across restarts without extra state. If
    that entry is later removed, the next one adopts the entities - the unique
    ids are keyed off the account, not the entry."""
    key = account_key(entry)
    if not key:
        return False
    peers = sorted(
        other.entry_id
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.disabled_by is None and account_key(other) == key
    )
    return bool(peers) and peers[0] == entry.entry_id


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
            identifiers={(DOMAIN, f"makerworld_{self._account_key}")},
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
) -> MakerWorldDataUpdateCoordinator | None:
    """Build the coordinator, or None when this entry shouldn't have one."""
    if not owns_makerworld_entities(hass, entry):
        return None
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
