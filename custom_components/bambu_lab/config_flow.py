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
from homeassistant.helpers import device_registry
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
    SelectOptionDict(value="X1E", label="X1E"),
]
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
    email: str = ""

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
        fields[vol.Required('printer_mode')] = MODE_SELECTOR

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
                self._bambu_cloud = BambuCloud("", "", "")

                await self.hass.async_add_executor_job(
                    self._bambu_cloud.login,
                    user_input['username'],
                    user_input['password'])

                self.email = user_input['username']
                return await self.async_step_Bambu_Choose_Device(None)

            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")

            errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('username')] = EMAIL_SELECTOR
        fields[vol.Required('password')] = PASSWORD_SELECTOR

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
            self._bambu_cloud.get_device_list)

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input.get('local_mqtt', "") == False)):
            success = True
            for device in device_list:
                if device['dev_id'] == user_input['serial']:
                    device_type = self._bambu_cloud.get_device_type_from_device_product_name(device['dev_product_name'])
                    if user_input.get('host', "") != "":
                        LOGGER.debug("Config Flow: Testing local mqtt connection")
                        bambu = BambuClient(device_type=device_type,
                                            serial=device['dev_id'],
                                            host=user_input['host'],
                                            local_mqtt=True,
                                            email="",
                                            username="",
                                            auth_token="",
                                            access_code=device['dev_access_code'])
                        success = await bambu.try_connection()
                        if not success:
                            errors['base'] = "cannot_connect"

                    if success:
                        LOGGER.debug(f"Config Flow: Writing entry: '{device['name']}'")
                        data = {
                                "device_type": device_type,
                                "serial": device['dev_id']
                            }
                        options = {
                                "email": self.email,
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
            dev_reg = device_registry.async_get(self.hass)
            hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, device['dev_id'])})
            if hadevice is None:
                printer_list.append(SelectOptionDict(value = device['dev_id'], label = f"{device['name']}: {device['dev_id']}"))

        printer_selector = SelectSelector(
            SelectSelectorConfig(
                options=printer_list,
                mode=SelectSelectorMode.LIST)
        )

        LOGGER.debug(f"Printer count = {printer_list.count}")
        if len(printer_list) == 0:
            errors['base'] = "no_printers"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        if len(printer_list) != 0:
            fields[vol.Required('serial')] = printer_selector
            fields[vol.Optional('host')] = TEXT_SELECTOR
            fields[vol.Optional('local_mqtt')] = BOOLEAN_SELECTOR

        return self.async_show_form(
            step_id="Bambu_Choose_Device",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True
        )

    async def async_step_Lan(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            LOGGER.debug("Config Flow: Testing local mqtt connection")
            bambu = BambuClient(device_type="unknown",
                                serial=user_input['serial'],
                                host=user_input['host'],
                                local_mqtt=True,
                                email="",
                                username="",
                                auth_token="",
                                access_code=user_input['access_code'])
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Config Flow: Writing entry")
                data = {
                        "device_type": bambu.get_device().info.device_type,
                        "serial": user_input['serial']
                }
                options = {
                        "email": "",
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
        fields[vol.Required('serial')] = TEXT_SELECTOR
        fields[vol.Required('host')] = TEXT_SELECTOR
        fields[vol.Required('access_code')] = PASSWORD_SELECTOR

        return self.async_show_form(
            step_id="Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True,
        )

    async def async_step_ssdp(
            self, discovery_info: ssdp.SsdpServiceInfo
    ) -> FlowResult:
        """Handle ssdp discovery flow."""

        LOGGER.debug("async_step_ssdp");
        return await self.async_step_user()


class BambuOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Bambu options."""

    email: str = ""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize MQTT options flow."""
        self.config_entry = config_entry
        self.email = self.config_entry.options.get('email', '')

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
        fields[vol.Required('printer_mode')] = MODE_SELECTOR

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

        self._bambu_cloud = BambuCloud("", "", "")

        credentialsGood = False
        if user_input is None:
            if self.config_entry.options.get('email', '') != '' and self.config_entry.options.get('username', '') != '' and self.config_entry.options.get('auth_token', '') != '':
                credentialsGood = await self.hass.async_add_executor_job(
                    self._bambu_cloud.test_authentication,
                    self.config_entry.options['email'],
                    self.config_entry.options['username'],
                    self.config_entry.options['auth_token'])

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    self._bambu_cloud.login,
                    user_input['username'],
                    user_input['password'])
                
                self.email = user_input['username']

                return await self.async_step_Bambu_Choose_Device(None)

            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")

            errors['base'] = "cannot_connect"
        elif credentialsGood:
            self.email = self.config_entry.options['email']
            return await self.async_step_Bambu_Choose_Device(None)

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('username', default=self.email)] = EMAIL_SELECTOR
        fields[vol.Required('password')] = PASSWORD_SELECTOR

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
            self._bambu_cloud.get_device_list)

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input['local_mqtt'] == False)):
            for device in device_list:
                if device['dev_id'] == user_input['serial']:

                    success = True
                    if user_input.get('host', "") != "":
                        LOGGER.debug("Options Flow: Testing local mqtt connection")
                        bambu = BambuClient(device_type=self.config_entry.data['device_type'],
                                            serial=self.config_entry.data['serial'],
                                            host=user_input['host'],
                                            local_mqtt=True,
                                            email="",
                                            username="",
                                            auth_token="",
                                            access_code=device['dev_access_code'])
                        success = await bambu.try_connection()
                        if not success:
                            errors['base'] = "cannot_connect"
                
                    if success:
                        LOGGER.debug(f"Options Flow: Writing entry: '{device['name']}'")
                        data = {
                                "device_type": self.config_entry.data['device_type'],
                                "serial": self.config_entry.data['serial']
                        }
                        options = {
                                "email": self.email,
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
        fields[vol.Required('serial', default=self.config_entry.options.get('serial', ''))] = printer_selector
        fields[vol.Optional('host', default=self.config_entry.options.get('host', ''))] = TEXT_SELECTOR
        fields[vol.Optional('local_mqtt', default=self.config_entry.options.get('local_mqtt', True))] = BOOLEAN_SELECTOR

        return self.async_show_form(
            step_id="Bambu_Choose_Device",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True,
        )
    
    async def async_step_Lan(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            LOGGER.debug("Options Flow: Testing local mqtt Connection")
            bambu = BambuClient(device_type=self.config_entry.data['device_type'],
                                serial=self.config_entry.data['serial'],
                                host=user_input['host'],
                                local_mqtt=True,
                                email="",
                                username="",
                                auth_token="",
                                access_code=user_input['access_code'])
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Options Flow: Writing entry")
                data = {
                        "device_type": self.config_entry.data['device_type'],
                        "serial": self.config_entry.data['serial']
                }
                options = {
                        "email": self.config_entry.options.get('email', ''),
                        "username": self.config_entry.options.get('username', ''),
                        "name": self.config_entry.options.get('name', ''),
                        "host": user_input['host'],
                        "local_mqtt": True,
                        "auth_token": self.config_entry.options.get('auth_token', ''),
                        "access_code": user_input['access_code']
                }

                title = self.config_entry.data['serial']
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
        fields[vol.Required('host', default=self.config_entry.options.get('host', ''))] = TEXT_SELECTOR
        fields[vol.Required('access_code', default=self.config_entry.options.get('access_code', ''))] = PASSWORD_SELECTOR

        return self.async_show_form(
            step_id="Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True,
        )
