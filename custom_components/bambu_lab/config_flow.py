"""Config flow to configure Bambu Lab."""
from __future__ import annotations

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
from .pybambu.bambu_cloud import (
    CloudflareError,
    CurlUnavailableError,
    EmailCodeRequiredError,
    EmailCodeExpiredError,
    EmailCodeIncorrectError,
    TfaCodeRequiredError
)

CONFIG_VERSION = 2

BOOLEAN_SELECTOR = BooleanSelector()
NUMBER_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.NUMBER))
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
EMAIL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
REGION_LIST = [
    SelectOptionDict(value="AsiaPacific", label="Asia Pacific"),
    SelectOptionDict(value="China", label="China"),
    SelectOptionDict(value="Europe", label="Europe"),
    SelectOptionDict(value="NorthAmerica", label="North America"),
    SelectOptionDict(value="Other", label="Other"),
]
REGION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=REGION_LIST,
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
    region: str = ""
    email: str = ""
    serial: str = ""

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

        self._bambu_cloud = BambuCloud("", "", "", "")

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
        default_region = ''
        default_email = ''

        if user_input is None:
            # Iterate over all existing entries and try any existing credentials to see if they work
            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            LOGGER.debug(f"Found {len(config_entries)} existing config entries for the integration.")
            for config_entry in config_entries:
                if config_entry.options.get('region', '') != '' and config_entry.options.get('email', '') != '' and config_entry.options.get('username', '') != '' and config_entry.options.get('auth_token', '') != '':
                    LOGGER.debug(f"Testing credentials from existing entry id: {config_entry.entry_id}")
                    default_region = config_entry.options['region']
                    default_email = config_entry.options['email']
                    username = config_entry.options['username']
                    auth_token = config_entry.options['auth_token']
                    if await self.hass.async_add_executor_job(self._bambu_cloud.test_authentication,
                                                              default_region,
                                                              default_email,
                                                              username,
                                                              auth_token):
                        LOGGER.debug("Found working credentials.")
                        self.region = default_region
                        self.email = default_email
                        self.bambu_cloud = BambuCloud(
                            default_region,
                            default_email,
                            username,
                            auth_token
                        )
                        return await self.async_step_Bambu_Choose_Device(None)

        authentication_type = None
        if user_input is not None:
            try:
                if user_input.get('verifyCode', None) is not None:
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.login_with_verification_code,
                        user_input['verifyCode'])
                elif user_input.get('tfaCode', None) is not None:
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.login_with_2fa_code,
                        user_input['tfaCode'])
                else:
                    self.region = user_input['region']
                    self.email = user_input['email']
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.login,
                        user_input['region'],
                        user_input['email'],
                        user_input['password'])
                return await self.async_step_Bambu_Choose_Device(None)

            # Handle possible failure cases
            except CloudflareError:
                return self.async_abort(reason='cloudflare')
            except CurlUnavailableError:
                return self.async_abort(reason='curl_unavailable')
            except EmailCodeRequiredError:
                authentication_type = 'verifyCode'
                errors['base'] = 'verifyCode'
                # Fall through to form generation to ask for verification code
            except EmailCodeExpiredError:
                authentication_type = 'verifyCode'
                errors['base'] = 'code_expired'
                # Fall through to form generation to ask for verification code
            except EmailCodeIncorrectError:
                authentication_type = 'verifyCode'
                errors['base'] = 'code_incorrect'
                # Fall through to form generation to ask for verification code
            except TfaCodeRequiredError:
                authentication_type = 'tfaCode'
                errors['base'] = 'tfaCode'
                # Fall through to form generation to ask for verification code
            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")
                errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        default_region = default_region if user_input is None else user_input.get('region', '')
        fields[vol.Required("region", default=default_region)] = REGION_SELECTOR
        default_email = default_email if user_input is None else user_input.get('email', '')
        fields[vol.Required('email', default=default_email)] = EMAIL_SELECTOR
        default_password = '' if user_input is None else user_input.get('password', '')
        fields[vol.Required('password', default=default_password)] = PASSWORD_SELECTOR
        if authentication_type == 'verifyCode':
            fields[vol.Required('verifyCode', default='')] = TEXT_SELECTOR
        if authentication_type == 'tfaCode':
            fields[vol.Required('tfaCode', default='')] = TEXT_SELECTOR

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

        if user_input is not None:
            self.serial = user_input['serial']
            return await self.async_step_Bambu_Lan(None)
            
        device_list = await self.hass.async_add_executor_job(
            self._bambu_cloud.get_device_list)
            
        printer_list = []
        for device in device_list:
            dev_reg = device_registry.async_get(self.hass)
            hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, device['dev_id'])})
            if hadevice is None:
                LOGGER.debug(f"Printer {device['dev_id']} found.")
                printer_list.append(SelectOptionDict(value = device['dev_id'], label = f"{device['name']}: {device['dev_id']}"))
            else:
                LOGGER.debug(f"Printer {device['dev_id']} already registered with HA. Ignoring it.")

        printer_selector = SelectSelector(
            SelectSelectorConfig(
                options=printer_list,
                mode=SelectSelectorMode.LIST)
        )

        LOGGER.debug(f"Printer count = {len(printer_list)}")
        if len(printer_list) == 0:
            return self.async_abort(reason='no_printers')

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('serial')] = printer_selector

        return self.async_show_form(
            step_id="Bambu_Choose_Device",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False
        )

    async def async_step_Bambu_Lan(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        LOGGER.debug("async_step_Bambu_Lan")

        device_list = await self.hass.async_add_executor_job(
            self._bambu_cloud.get_device_list)

        for device in device_list:
            if device['dev_id'] == self.serial:
                break

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input.get('local_mqtt', False) == False)):
            success = True
            device_type = self._bambu_cloud.get_device_type_from_device_product_name(device['dev_product_name'])
            if user_input.get('host', "") != "":
                LOGGER.debug("Config Flow: Testing local mqtt connection")
                config = {
                    'access_code': user_input['access_code'],
                    'device_type': device_type,
                    'host': user_input['host'],
                    'local_mqtt': True,
                    'region': self.region,
                    'serial': device['dev_id'],
                }
                bambu = BambuClient(config)
                success = await bambu.try_connection()
                if not success:
                    errors['base'] = "cannot_connect_local_all"

            if success:
                LOGGER.debug(f"Config Flow: Writing entry: '{device['name']}'")
                data = {
                        "device_type": device_type,
                        "serial": device['dev_id']
                }
                options = {
                        "region": self.region,
                        "email": self.email,
                        "username": self._bambu_cloud.username,
                        "name": device['name'],
                        "host": user_input.get('host', ""),
                        "local_mqtt": user_input.get('local_mqtt', False),
                        "auth_token": self._bambu_cloud.auth_token,
                        "access_code": user_input['access_code'],
                        "usage_hours": float(user_input['usage_hours'])
                }
                title = device['dev_id']
                return self.async_create_entry(
                    title=title,
                    data=data,
                    options=options
                )
            
        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Optional('local_mqtt', default = False)] = BOOLEAN_SELECTOR
        default_host = "" if user_input is None else user_input['host']
        fields[vol.Optional('host', default=default_host)] = TEXT_SELECTOR
        default_access_code = device['dev_access_code'] if user_input is None else user_input['access_code']
        fields[vol.Optional('access_code', default = default_access_code)] = TEXT_SELECTOR
        default_usage_hours = "0" if user_input is None else user_input['usage_hours']
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR

        return self.async_show_form(
            step_id="Bambu_Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True
        )

    async def async_step_Lan(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            # Serial must be upper case to work
            user_input['serial'] = user_input['serial'].upper()

            LOGGER.debug("Config Flow: Testing local mqtt connection")
            config = {
                'access_code': user_input['access_code'],
                'serial': user_input['serial'],
                'host': user_input['host'],
                'local_mqtt': True,
            }
            bambu = BambuClient(config)
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Config Flow: Writing entry")
                data = {
                        "device_type": bambu.get_device().info.device_type,
                        "serial": user_input['serial']
                }
                options = {
                        "region": "",
                        "email": "",
                        "username": "",
                        "name": "",
                        "host": user_input['host'],
                        "local_mqtt": True,
                        "auth_token": "",
                        "access_code": user_input['access_code'],
                        "usage_hours": float(user_input['usage_hours'])
                }

                title = user_input['serial']
                return self.async_create_entry(
                    title=title,
                    data=data,
                    options=options
                )

            errors['base'] = "cannot_connect_local_all"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('host', default = '' if user_input is None else user_input.get('host', ''))] = TEXT_SELECTOR
        fields[vol.Required('serial', default = '' if user_input is None else user_input.get('serial', ''))] = TEXT_SELECTOR
        fields[vol.Required('access_code', default = '' if user_input is None else user_input.get('access_code', ''))] = TEXT_SELECTOR
        default_usage_hours = "0" if user_input is None else user_input['usage_hours']
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR

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

    region: str = ""
    email: str = ""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize MQTT options flow."""
        self.config_entry = config_entry
        self.region = self.config_entry.options.get('region', '')
        self.email = self.config_entry.options.get('email', '')

        self._bambu_cloud = BambuCloud("", "", "", "")

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
        fields[vol.Required('printer_mode', default='Bambu' if self.config_entry.options['auth_token'] != "" else 'Lan')] = MODE_SELECTOR

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

        if user_input is None:
            # Iterate over all existing entries and try any existing credentials to see if they work
            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            LOGGER.debug(f"Found {len(config_entries)} existing config entries for the integration.")
            for config_entry in config_entries:
                if config_entry.options.get('region', '') != '' and config_entry.options.get('email', '') != '' and config_entry.options.get('username', '') != '' and config_entry.options.get('auth_token', '') != '':
                    LOGGER.debug(f"Testing credentials from existing entry id: {config_entry.entry_id}")
                    region = config_entry.options['region']
                    email = config_entry.options['email']
                    username = config_entry.options['username']
                    auth_token = config_entry.options['auth_token']
                    if await self.hass.async_add_executor_job(self._bambu_cloud.test_authentication,
                                                              region,
                                                              email,
                                                              username,
                                                              auth_token):
                        LOGGER.debug("Found working credentials.")
                        self.region = region
                        self.email = email
                        self.bambu_cloud = BambuCloud(
                            region,
                            email,
                            username,
                            auth_token
                        )
                        return await self.async_step_Bambu_Lan(None)
                    
        authentication_type = None
        if user_input is not None:
            try:
                if user_input.get('verifyCode', None) is not None:
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.login_with_verification_code,
                        user_input['verifyCode'])
                    return await self.async_step_Bambu_Lan(None)

                elif user_input.get('tfaCode', None) is not None:
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.login_with_2fa_code,
                        user_input['tfaCode'])
                    return await self.async_step_Bambu_Lan(None)

                else:
                    self.region = user_input['region']
                    self.email = user_input['email']
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.login,
                        user_input['region'],
                        user_input['email'],
                        user_input['password'])
                    return await self.async_step_Bambu_Lan(None)

            # Handle possible failure cases
            except EmailCodeExpiredError:
                authentication_type = 'verifyCode'
                errors['base'] = "code_expired"
                # Fall through to form generation to ask for verification code
            except EmailCodeIncorrectError:
                authentication_type = 'verifyCode'
                errors['base'] = "code_incorrect"
                # Fall through to form generation to ask for verification code
            except CloudflareError:
                return self.async_abort(reason='cloudflare')
            except CurlUnavailableError:
                return self.async_abort(reason='curl_unavailable')
            except EmailCodeRequiredError:
                authentication_type = 'verifyCode'
                errors['base'] = 'verifyCode'
                # Fall through to form generation to ask for verification code
            except EmailCodeExpiredError:
                authentication_type = 'verifyCode'
                errors['base'] = 'code_expired'
                # Fall through to form generation to ask for verification code
            except EmailCodeIncorrectError:
                authentication_type = 'verifyCode'
                errors['base'] = 'code_incorrect'
                # Fall through to form generation to ask for verification code
            except TfaCodeRequiredError:
                authentication_type = 'tfaCode'
                errors['base'] = 'tfaCode'
                # Fall through to form generation to ask for verification code
            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")
                errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        default_region = self.config_entry.options.get('region', '') if user_input is None else user_input.get('region', '')
        fields[vol.Required("region", default=default_region)] = REGION_SELECTOR
        default_email = self.config_entry.options.get('email','') if user_input is None else user_input.get('email', '')
        fields[vol.Required('email', default=default_email)] = EMAIL_SELECTOR
        default_password = '' if user_input is None else user_input.get('password', '')
        fields[vol.Required('password', default=default_password)] = PASSWORD_SELECTOR
        if authentication_type == 'verifyCode':
            fields[vol.Required('verifyCode', default='')] = TEXT_SELECTOR
        if authentication_type == 'tfaCode':
            fields[vol.Required('tfaCode', default='')] = TEXT_SELECTOR

        return self.async_show_form(
            step_id="Bambu",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )

    async def async_step_Bambu_Lan(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        LOGGER.debug("async_step_Bambu_Lan")

        device_list = await self.hass.async_add_executor_job(
            self._bambu_cloud.get_device_list)

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input['local_mqtt'] == False)):
            for device in device_list:
                if device['dev_id'] == user_input['serial']:

                    success = True
                    if user_input.get('host', "") != "":
                        LOGGER.debug(f"Options Flow: Testing local mqtt connection to {user_input.get('host')}")
                        config = {
                            'access_code': user_input['access_code'],
                            'device_type': self.config_entry.data['device_type'],
                            'host': user_input['host'],
                            'local_mqtt': True,
                            'serial': self.config_entry.data['serial'],
                        }
                        bambu = BambuClient(config)
                        success = await bambu.try_connection()
                        if not success:
                            errors['base'] = "cannot_connect_local_ip"
                
                    if success:
                        LOGGER.debug(f"Options Flow: Writing entry: '{device['name']}'")
                        data = dict(self.config_entry.data)
                        options = {
                            "region": self.region,
                            "email": self.email,
                            "username": self._bambu_cloud.username,
                            "name": device['name'],
                            "host": user_input['host'],
                            "local_mqtt": user_input.get('local_mqtt', False),
                            "auth_token": self._bambu_cloud.auth_token,
                            "access_code": user_input['access_code'],
                            "usage_hours": float(user_input['usage_hours'])
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
        access_code = ''
        for device in device_list:
            if device['dev_id'] == self.config_entry.data['serial']:
                printer_list.append(SelectOptionDict(value = device['dev_id'], label = f"{device['name']}: {device['dev_id']}"))
                access_code = device['dev_access_code']

        printer_selector = SelectSelector(
            SelectSelectorConfig(
                options=printer_list,
                mode=SelectSelectorMode.LIST)
        )

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('serial', default=self.config_entry.data['serial'])] = printer_selector
        default_host = self.config_entry.options.get('host', '') if user_input is None else user_input['host']
        fields[vol.Optional('host', default=default_host)] = TEXT_SELECTOR
        fields[vol.Optional('access_code', default=self.config_entry.options.get('access_code', access_code))] = TEXT_SELECTOR
        fields[vol.Optional('local_mqtt', default=self.config_entry.options.get('local_mqtt', True))] = BOOLEAN_SELECTOR
        default_usage_hours = str(self.config_entry.options.get('usage_hours', 0)) if user_input is None else user_input['usage_hours']
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR

        return self.async_show_form(
            step_id="Bambu_Lan",
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
            config = {
                'access_code': user_input['access_code'],
                'device_type': self.config_entry.data['device_type'],
                'host': user_input['host'],
                'local_mqtt': True,
                'serial': self.config_entry.data['serial'],
            }
            bambu = BambuClient(config)
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Options Flow: Writing entry")
                data = dict(self.config_entry.data)
                options = {
                    "region": self.config_entry.options.get('region', ''),
                    "email": self.config_entry.options.get('email', ''),
                    "username": self.config_entry.options.get('username', ''),
                    "name": self.config_entry.options.get('name', ''),
                    "host": user_input['host'],
                    "local_mqtt": True,
                    "auth_token": self.config_entry.options.get('auth_token', ''),
                    "access_code": user_input['access_code'],
                    "usage_hours": float(user_input['usage_hours'])
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

            errors['base'] = "cannot_connect_local_all"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        default_host = self.config_entry.options.get('host', '') if user_input is None else user_input.get('host', self.config_entry.options.get('host', ''))
        default_access_code = self.config_entry.options.get('access_code', '') if user_input is None else user_input.get('access_code', self.config_entry.options.get('access_code', ''))
        fields[vol.Required('host', default=default_host)] = TEXT_SELECTOR
        fields[vol.Required('access_code', default=default_access_code)] = TEXT_SELECTOR
        default_usage_hours = str(self.config_entry.options.get('usage_hours', 0)) if user_input is None else user_input['usage_hours']
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR

        return self.async_show_form(
            step_id="Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True,
        )
