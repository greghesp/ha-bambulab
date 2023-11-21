"""Config flow to configure Bambu Lab."""
from __future__ import annotations

import base64
import json
import queue
import requests
import voluptuous as vol

from typing import Any
from collections import OrderedDict

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.components import ssdp
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
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
    SelectOptionDict(value="A1Mini", label="A1 Mini"),
    SelectOptionDict(value="P1P", label="P1P"),
    SelectOptionDict(value="P1S", label="P1S"),
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
    SelectOptionDict(value="Lan", label="Local MQTT Connection"),
    SelectOptionDict(value="Bambu", label="Bambu Cloud MQTT Connection"),
]
MODE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=SUPPORTED_MODES,
        mode=SelectSelectorMode.LIST,
    )
)


def get_authentication_token(username: str, password: str) -> dict:
    LOGGER.debug("Config Flow: Getting accessToken from Bambu Cloud")
    url = 'https://api.bambulab.com/v1/user-service/user/login'
    data = {'account': username, 'password': password}
    response = requests.post(url, json=data, timeout=10)
    if not response.ok:
        LOGGER.debug(f"Received error: {response.status_code}")
        raise ValueError(response.status_code)
    LOGGER.debug(f"Success: {response.json()}")
    return response.json()


def get_username_from_authentication_token(authToken: str) -> str:
    # User name is in 2nd portion of the auth token (delimited with periods)
    b64_string = authToken.split(".")[1]
    # String must be multiples of 4 chars in length. For decode pad with = character
    b64_string += "=" * ((4 - len(b64_string) % 4) % 4)
    jsonAuthToken = json.loads(base64.b64decode(b64_string))
    # Gives json payload with "username":"u_<digits>" within it
    return jsonAuthToken['username']


class BambuLabFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Bambu Lab config flow."""

    VERSION = 1
    config_data: dict[str, Any] = {}
    cloud_supported: bool = True

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
    ) -> BambuOptionsFlowHandler:
        """Get the options flow for this handler."""
        return BambuOptionsFlowHandler(config_entry)

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self.config_data = user_input
            if not self.cloud_supported or (user_input["printer_mode"] == "Lan"):
                return await self.async_step_Lan(None)
            if self.cloud_supported and (user_input["printer_mode"] == "Bambu"):
                return await self.async_step_Bambu(None)

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("device_type")] = PRINTER_SELECTOR
        fields[vol.Required("serial")] = TEXT_SELECTOR
        if self.cloud_supported:
            fields[vol.Required("printer_mode")] = MODE_SELECTOR

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
            gotToken = False
            try:
                result = await self.hass.async_add_executor_job(
                    get_authentication_token,
                    user_input['username'],
                    user_input['password'],
                )
                gotToken = True
            except Exception as e:
                LOGGER.warn(f"Failed to retrieve auth token with error code {e.args}")

            if gotToken:
                authToken = result['accessToken']
                username = get_username_from_authentication_token(authToken)

                bambu = BambuClient(device_type=self.config_data["device_type"],
                                    serial=self.config_data["serial"],
                                    host="us.mqtt.bambulab.com",
                                    username=username,
                                    access_code=authToken)
                success = await bambu.try_connection()

                if success:
                    LOGGER.debug("Config Flow: Writing entry")
                    return self.async_create_entry(
                        title=self.config_data["serial"],
                        data={
                            "device_type": self.config_data["device_type"],
                            "serial": self.config_data["serial"],
                            "host": "us.mqtt.bambulab.com",
                            "username": username,
                            "access_code": authToken,
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
            bambu = BambuClient(device_type=self.config_data["device_type"],
                                serial=self.config_data["serial"],
                                host=user_input["host"],
                                username="bblp",
                                access_code=user_input["access_code"])
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Config Flow: Writing entry")
                return self.async_create_entry(
                    title=self.config_data["serial"],
                    data={
                        "device_type": self.config_data["device_type"],
                        "serial": self.config_data["serial"],
                        "host": user_input["host"],
                        "username": "bblp",
                        "access_code": user_input["access_code"],
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

    async def async_step_ssdp(
            self, discovery_info: ssdp.SsdpServiceInfo
    ) -> FlowResult:
        """Handle ssdp discovery flow."""

        LOGGER.debug("async_step_ssdp");
        return await self.async_step_user()


class BambuOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Bambu options."""
    cloud_supported: bool = True

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize MQTT options flow."""
        self.config_entry = config_entry
        self.config_data: dict[str, Any] = {}

        LOGGER.debug(self.config_entry)

    async def async_step_init(self, user_input: None = None) -> FlowResult:
        """Manage the MQTT options."""
        errors = {}

        if user_input is not None:
            self.config_data = user_input
            self.config_data['device_type'] = self.config_entry.data['device_type']
            self.config_data['serial'] = self.config_entry.data['serial']
            if not self.cloud_supported or (user_input["printer_mode"] == "Lan"):
                return await self.async_step_Lan(None)
            if self.cloud_supported and (user_input["printer_mode"] == "Bambu"):
                return await self.async_step_Bambu(None)

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        if self.cloud_supported:
            fields[vol.Required("printer_mode")] = MODE_SELECTOR

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )

    async def async_step_Bambu(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            gotToken = False
            try:
                result = await self.hass.async_add_executor_job(
                    get_authentication_token,
                    user_input['username'],
                    user_input['password'],
                )
                gotToken = True
            except Exception as e:
                LOGGER.warn(f"Failed to retrieve auth token with error code {e.args}")

            if gotToken:
                authToken = result['accessToken']
                username = get_username_from_authentication_token(authToken)

                bambu = BambuClient(device_type=self.config_data["device_type"],
                                    serial=self.config_data["serial"],
                                    host="us.mqtt.bambulab.com",
                                    username=username,
                                    access_code=authToken)
                success = await bambu.try_connection()

                if success:
                    LOGGER.debug("Config Flow: Writing new entry")
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        title=self.config_data["serial"],
                        data={
                            "device_type": self.config_data["device_type"],
                            "serial": self.config_data["serial"],
                            "host": "us.mqtt.bambulab.com",
                            "username": username,
                            "access_code": authToken,
                        }
                    )
                    await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                    return self.async_create_entry(title="", data={})

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
            bambu = BambuClient(device_type=self.config_data["device_type"],
                                serial=self.config_data["serial"],
                                host=user_input["host"],
                                username="bblp",
                                access_code=user_input["access_code"])
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Config Flow: Writing new entry")
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=self.config_data["serial"],
                    data={
                        "device_type": self.config_data["device_type"],
                        "serial": self.config_data["serial"],
                        "host": user_input["host"],
                        "username": "bblp",
                        "access_code": user_input["access_code"],
                    }
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

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
