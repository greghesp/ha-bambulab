"""Base entity for BIQU Panda devices linked to a printer."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity


class PandaEntity(Entity):
    """Pushed by the linked Panda device's client; unavailable while it is unreachable.

    Subclasses set `kind` (a key of panda_devices.PANDA_KINDS) and the
    `unique_id_prefix` used in unique IDs.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    kind: str = ""
    unique_id_prefix: str = ""

    def __init__(self, coordinator, key: str) -> None:
        self.coordinator = coordinator
        self.client = coordinator.panda_devices[self.kind]
        self._attr_unique_id = f"{coordinator.config_entry.data['serial']}_{self.unique_id_prefix}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.get_panda_device(self.kind)

    @property
    def available(self) -> bool:
        return self.client.connected

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.client.async_add_listener(self.async_write_ha_state))
