"""Config flow to configure Bambu Lab."""
from __future__ import annotations

import voluptuous as vol
import queue
from typing import Any
from collections import OrderedDict

from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.components import ssdp
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER
from .pybambu import BambuClient

BOOLEAN_SELECTOR = BooleanSelector()
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
SUPPORTED_PRINTERS = [
    SelectOptionDict(value="P1P", label="P1P"),
    SelectOptionDict(value="X1", label="X1"),
    SelectOptionDict(value="X1C", label="X1C"),
]
PRINTER_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=SUPPORTED_PRINTERS,
        mode=SelectSelectorMode.LIST,
    )
)
SUPPORTED_MODES = [
    SelectOptionDict(value="Bambu", label="Bambu Cloud"),
    SelectOptionDict(value="Lan", label="Lan Mode"),
]
MODE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=SUPPORTED_MODES,
        mode=SelectSelectorMode.LIST,
    )
)

class BambuLabFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Bambu Lab config flow. The MQTT step is inherited from the parent class."""

    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            if (user_input["printer_mode"] == "Bambu"):
                return await self.async_step_Bambu(user_input)
            if (user_input["printer_mode"] == "Lan"):
                return await self.async_step_Lan(user_input)
        
        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("device_type")] = PRINTER_SELECTOR
        fields[vol.Required("printer_mode")] = MODE_SELECTOR
        fields[vol.Required("serial")] = TEXT_SELECTOR

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )
    
    async def async_step_Bambu(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            authToken = "TODO"
            bambu = BambuClient(device_type = user_input["device_type"], serial = user_input["serial"], host = "us.mqtt.bambulab.com", access_code = authToken)
            success = await bambu.try_connection()

            if success:
                device = bambu.get_device()
                return self.async_create_entry(
                    title=user_input["serial"],
                    data={
                        "device_type": user_input["device_type"],
                        "serial": user_input["serial"],
                        "host": "us.mqtt.bambulab.com",
                        "access_code": authToken
                    }
                )
            
            errors["base"] = "cannot_connect"
        
        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("username")] = TEXT_SELECTOR
        fields[vol.Required("password")] = PASSWORD_SELECTOR

        return self.async_show_form(
            step_id="Bambu",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )

    async def async_step_Lan(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            LOGGER.debug("Config Flow: Trying Lan Mode Connection")
            bambu = BambuClient(device_type = user_input["device_type"], serial = user_input["serial"], host = user_input["host"], access_code = user_input["access_code"])
            success = await bambu.try_connection()

            if success:
                device = bambu.get_device()
                return self.async_create_entry(
                    title=user_input["serial"],
                    data={
                        "device_type": user_input["device_type"],
                        "serial": user_input["serial"],
                        "host": user_input["host"],
                        "access_code": user_input["access_code"],
                        "authToken": "",
                    }
                )
            
            errors["base"] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("host")] = TEXT_SELECTOR
        fields[vol.Required("access_code")] = PASSWORD_SELECTOR

        return self.async_show_form(
            step_id="Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )
    
    async def async_step_done(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()

        return self.async_show_form(
            step_id="Done",
            data_schema=vol.Schema(fields),
            errors=errors or {}
        )   
    
    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> FlowResult:
        """Handle ssdp discovery flow."""

        LOGGER.debug("async_step_ssdp");
        return await self.async_step_user()
