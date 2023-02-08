"""Config flow to configure Bambu Lab."""
from __future__ import annotations

import voluptuous as vol
import queue
from typing import Any
from homeassistant.const import CONF_HOST, CONF_MAC

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from .const import DOMAIN, LOGGER
from .pybambu import BambuClient


class BambuLabFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Bambu Lab config flow. The MQTT step is inherited from the parent class."""

    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            bambu = BambuClient(user_input[CONF_HOST])
            LOGGER.debug("Config Flow: Trying Connection")
            serial = user_input["serial"]
            serial_number = await bambu.try_connection(serial)

            if serial_number:
                return self.async_create_entry(
                    title=user_input["name"],
                    data={
                        "serial": serial_number,
                        CONF_HOST: user_input[CONF_HOST],
                        "name": user_input["name"]
                    }
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str, vol.Required("name"): str, vol.Optional("serial"): str}),
            errors=errors or {},
        )
