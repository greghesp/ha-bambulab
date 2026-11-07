# SPDX-License-Identifier: AGPL-3.0-only
"""Signing repairs reuse the same validation and rotation flow as options."""
from homeassistant.components.repairs import RepairsFlow

from .const import DOMAIN
from .signing_flow import SigningFlowMixin


class SigningRepairFlow(SigningFlowMixin, RepairsFlow):
    def __init__(self, entry):
        self._config_entry = entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_signed_fans()


async def async_create_fix_flow(hass, issue_id, data):
    entry = hass.config_entries.async_get_entry((data or {}).get("entry_id", ""))
    if (entry is None or entry.domain != DOMAIN
            or issue_id != f"signing_{entry.entry_id}"):
        return None
    return SigningRepairFlow(entry)
