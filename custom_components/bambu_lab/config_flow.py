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
from homeassistant.components import ssdp
from homeassistant.core import callback
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
from .pybambu import BambuClient, BambuCloud

CONFIG_VERSION = 2

BOOLEAN_SELECTOR = BooleanSelector()
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
EMAIL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
SUPPORTED_PRINTERS = [
    SelectOptionDict(value="A1", label="A1"),
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
    SelectOptionDict(value="Bambu", label="Bambu Cloud Configuration"),
    SelectOptionDict(value="Lan", label="Lan Mode Configuration")
]
MODE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=SUPPORTED_MODES,
        mode=SelectSelectorMode.LIST,
    )
)


class BambuLabFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Bambu Lab config flow."""

    VERSION = CONFIG_VERSION
    _bambu_cloud: None

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
            if user_input['printer_mode'] == "Lan":
                return await self.async_step_Lan(None)
            if user_input['printer_mode'] == "Bambu":
                return await self.async_step_Bambu(None)

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
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
            try:
                self._bambu_cloud = BambuCloud()

                await self.hass.async_add_executor_job(
                    self._bambu_cloud.Login,
                    user_input['username'],
                    user_input['password'])

                return await self.async_step_Bambu_Choose_Device(None)

            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")

            errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("username")] = EMAIL_SELECTOR
        fields[vol.Required("password")] = PASSWORD_SELECTOR

        return self.async_show_form(
            step_id="Bambu",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )

    async def async_step_Bambu_Choose_Device(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        LOGGER.debug("async_step_Bambu_Choose_Device")

        device_list = await self.hass.async_add_executor_job(
            self._bambu_cloud.GetDeviceList)

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input['local_mqtt'] == False)):
            for device in device_list:
                if device['dev_id'] == user_input['serial']:
                    LOGGER.debug(f"Config Flow: Writing entry: '{device['name']}'")
                    data = {
                            "device_type": self._bambu_cloud.GetDeviceTypeFromDeviceProductName(device['dev_product_name']),
                            "serial": device['dev_id']
                        }
                    options = {
                            "username": self._bambu_cloud.username,
                            "name": device['name'],
                            "host": user_input['host'],
                            "local_mqtt": user_input.get('local_mqtt', False),
                            "auth_token": self._bambu_cloud.auth_token,
                            "access_code": device['dev_access_code']
                    }
                    title = device['dev_id']
                    return self.async_create_entry(
                        title=title,
                        data=data,
                        options=options
                    )
            
        printer_list = []
        for device in device_list:
            printer_list.append(SelectOptionDict(value = device['dev_id'], label = f"{device['name']}: {device['dev_id']}"))

        printer_selector = SelectSelector(
            SelectSelectorConfig(
                options=printer_list,
                mode=SelectSelectorMode.LIST)
        )

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('serial')] = printer_selector
        fields[vol.Optional("host")] = TEXT_SELECTOR
        fields[vol.Optional("local_mqtt")] = BOOLEAN_SELECTOR

        return self.async_show_form(
            step_id="Bambu_Choose_Device",
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
            bambu = BambuClient(device_type=user_input['device_type'],
                                serial=user_input['serial'],
                                host=user_input['host'],
                                local_mqtt=True,
                                username="",
                                auth_token="",
                                access_code=user_input['access_code'])
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Config Flow: Writing entry")
                data = {
                        "device_type": user_input['device_type'],
                        "serial": user_input['serial']
                }
                options = {
                        "username": "",
                        "name": "",
                        "host": user_input['host'],
                        "local_mqtt": True,
                        "auth_token": "",
                        "access_code": user_input['access_code']
                }

                title = user_input['serial']
                return self.async_create_entry(
                    title=title,
                    data=data,
                    options=options
                )

            errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("device_type")] = PRINTER_SELECTOR
        fields[vol.Required("serial")] = TEXT_SELECTOR
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

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize MQTT options flow."""
        self.config_entry = config_entry

        LOGGER.debug(self.config_entry)

    async def async_step_init(self, user_input: None = None) -> FlowResult:
        """Manage the MQTT options."""
        errors = {}

        if user_input is not None:
            if user_input['printer_mode'] == "Lan":
                return await self.async_step_Lan(None)
            if user_input['printer_mode'] == "Bambu":
                return await self.async_step_Bambu(None)

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
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
            try:
                self._bambu_cloud = BambuCloud()

                await self.hass.async_add_executor_job(
                    self._bambu_cloud.Login,
                    user_input['username'],
                    user_input['password'])

                return await self.async_step_Bambu_Choose_Device(None)

            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")

            errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("username")] = EMAIL_SELECTOR
        fields[vol.Required("password")] = PASSWORD_SELECTOR

        return self.async_show_form(
            step_id="Bambu",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )

    async def async_step_Bambu_Choose_Device(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        LOGGER.debug("async_step_Bambu_Choose_Device")

        device_list = await self.hass.async_add_executor_job(
            self._bambu_cloud.GetDeviceList)

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input['local_mqtt'] == False)):
            for device in device_list:
                if device['dev_id'] == user_input['serial']:
                    LOGGER.debug(f"Options Flow: Writing entry: '{device['name']}'")
                    data = {
                            "device_type": self._bambu_cloud.GetDeviceTypeFromDeviceProductName(device['dev_product_name']),
                            "serial": device['dev_id']
                    }
                    options = {
                            "username": self._bambu_cloud.username,
                            "name": device['name'],
                            "host": user_input['host'],
                            "local_mqtt": user_input.get('local_mqtt', False),
                            "auth_token": self._bambu_cloud.auth_token,
                            "access_code": device['dev_access_code']
                    }
                    title = device['dev_id']
                    self.hass.config_entries.async_update_entry(
                        entry=self.config_entry,
                        title=title,
                        data=data,
                        options=options
                    )
                    await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                    return self.async_create_entry(title="", data=None)

        printer_list = []
        for device in device_list:
            if device['dev_id'] == self.config_entry.data['serial']:
                printer_list.append(SelectOptionDict(value = device['dev_id'], label = f"{device['name']}: {device['dev_id']}"))

        printer_selector = SelectSelector(
            SelectSelectorConfig(
                options=printer_list,
                mode=SelectSelectorMode.LIST)
        )

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('serial')] = printer_selector
        fields[vol.Optional("host")] = TEXT_SELECTOR
        fields[vol.Optional("local_mqtt")] = BOOLEAN_SELECTOR

        return self.async_show_form(
            step_id="Bambu_Choose_Device",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )
    
    async def async_step_Lan(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            LOGGER.debug("Options Flow: Trying Lan Mode Connection")
            bambu = BambuClient(device_type=user_input['device_type'],
                                serial=user_input['serial'],
                                host=user_input['host'],
                                local_mqtt=True,
                                username="",
                                auth_token="",
                                access_code=user_input['access_code'])
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Options Flow: Writing entry")
                data = {
                        "device_type": user_input['device_type'],
                        "serial": user_input['serial']
                }
                options = {
                        "username": "",
                        "name": "",
                        "host": user_input['host'],
                        "local_mqtt": True,
                        "auth_token": "",
                        "access_code": user_input['access_code']
                }

                title = user_input['serial']
                self.hass.config_entries.async_update_entry(
                    entry=self.config_entry,
                    title=title,
                    data=data,
                    options=options
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data=None)

            errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("device_type")] = PRINTER_SELECTOR
        fields[vol.Required("serial")] = TEXT_SELECTOR
        fields[vol.Required("host")] = TEXT_SELECTOR
        fields[vol.Required("access_code")] = PASSWORD_SELECTOR

        return self.async_show_form(
            step_id="Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )
