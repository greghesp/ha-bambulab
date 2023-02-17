"""Config flow to configure Bambu Lab."""
from __future__ import annotations

import voluptuous as vol
import queue
from typing import Any
from homeassistant.const import CONF_HOST, CONF_MAC

from homeassistant.components import ssdp
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
            LOGGER.debug("Config Flow: Trying Connection")
            bambu = BambuClient(user_input["host"], user_input["serial"], user_input["access_code"], user_input.get("tls", False), "Unknown")
            success = await bambu.try_connection()

            if success:
                device = bambu.get_device()
                return self.async_create_entry(
                    title=user_input["serial"],
                    data={
                        "host": user_input["host"],
                        "access_code": user_input["access_code"],
                        "serial": user_input["serial"],
                        "tls": user_input.get("tls", False),
                        "device_type": device.info.device_type
                    }
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("host"): str, vol.Required("access_code"): str, vol.Required("serial"): str, vol.Optional("tls"): bool}),
            errors=errors or {},
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> FlowResult:
        """Handle ssdp discovery flow."""

        LOGGER.debug("async_step_ssdp");
        return await self.async_step_user()
