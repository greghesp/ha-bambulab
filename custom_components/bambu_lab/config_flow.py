from __future__ import annotations

import logging
import voluptuous as vol

from typing import Any
from collections import OrderedDict

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
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
    CodeRequiredError,
    CodeExpiredError,
    CodeIncorrectError,
    TfaCodeRequiredError
)

CONFIG_VERSION = 2

BOOLEAN_SELECTOR = BooleanSelector()
NUMBER_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.NUMBER))
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
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


class BambuLabFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = CONFIG_VERSION
    _bambu_cloud: None
    region: str = ""
    email: str = ""
    serial: str = ""
    authentication_type: str = None
    _show_existing: bool
    _logging_level: None

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
    ) -> BambuOptionsFlowHandler:
        return BambuOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        # Set logging level to DEBUG during the configuration flow
        LOGGER.warning("Setting logging level to DEBUG")
        self.__logging_level = LOGGER.getEffectiveLevel()
        LOGGER.setLevel(logging.DEBUG)

        self._bambu_cloud = BambuCloud("", "", "", "")
        self._show_existing = False

    def __del__(self) -> None:
        # This isn't as immediate as I'd like it takes garbage collection but it'll kick in after a bit.
        LOGGER.warning("Restoring logging level")
        LOGGER.setLevel(self.__logging_level)

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is not None:
            if user_input['printer_mode'] == "lan":
                self._bambu_cloud = BambuCloud("", "", "", "")
                return await self.async_step_Lan(None)
            if user_input['printer_mode'] == "bambu":
                self._bambu_cloud = BambuCloud("", "", "", "")
                return await self.async_step_Bambu(None)
            if user_input['printer_mode'] != '':
                return await self.async_step_Bambu_Choose_Device(None)

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
                        break

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()

        default_option = ''
        if self.email != '':
            default_option = self.email
            modes = [
                SelectOptionDict(value="bambu", label=""),
                SelectOptionDict(value=self.email, label=self.email),
                SelectOptionDict(value="lan", label="")
            ]
        else:
            default_option = "bambu"
            modes = [
                SelectOptionDict(value="bambu", label=""),
                SelectOptionDict(value="lan", label="")
            ]
        selector = SelectSelector(
            SelectSelectorConfig(
                options=modes,
                translation_key="configuration_type",
                mode=SelectSelectorMode.LIST,
            )
        )
        fields[vol.Required('printer_mode', default=default_option)] = selector

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
        default_region = self.region
        default_email = self.email

        if user_input is not None:
            try:
                if user_input.get('newCode', False):
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.request_new_code)

                elif self.authentication_type == 'verifyCode':
                    if user_input.get('verifyCode', '') != '':
                        await self.hass.async_add_executor_job(
                            self._bambu_cloud.login_with_verification_code,
                            user_input['verifyCode'])
                        return await self.async_step_Bambu_Choose_Device(None)
                    else:
                        errors['base'] = "code_needed"

                elif self.authentication_type == 'tfaCode':
                    if user_input.get('tfaCode', '') != '':
                        await self.hass.async_add_executor_job(
                            self._bambu_cloud.login_with_2fa_code,
                            user_input['tfaCode'])
                        return await self.async_step_Bambu_Choose_Device(None)
                    else:
                        errors['base'] = "code_needed"

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
            except CodeExpiredError:
                errors['base'] = 'code_expired'
                # Fall through to form generation to ask for verification code
            except CodeIncorrectError:
                errors['base'] = 'code_incorrect'
                # Fall through to form generation to ask for verification code
            except CodeRequiredError:
                self.authentication_type = 'verifyCode'
                errors['base'] = 'verifyCode'
                # Fall through to form generation to ask for verification code
            except TfaCodeRequiredError:
                self.authentication_type = 'tfaCode'
                errors['base'] = 'tfaCode'
                # Fall through to form generation to ask for verification code
            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")
                errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        if self.authentication_type is None:
            default_region = default_region if user_input is None else user_input.get('region', '')
            fields[vol.Required("region", default=default_region)] = REGION_SELECTOR
            default_email = default_email if user_input is None else user_input.get('email', '')
            fields[vol.Required('email', default=default_email)] = TEXT_SELECTOR
            default_password = '' if user_input is None else user_input.get('password', '')
            fields[vol.Required('password', default=default_password)] = PASSWORD_SELECTOR
        elif self.authentication_type == 'verifyCode':
            fields[vol.Optional('newCode')] = BOOLEAN_SELECTOR
            fields[vol.Optional('verifyCode', default='')] = TEXT_SELECTOR
        elif self.authentication_type == 'tfaCode':
            fields[vol.Optional('newCode')] = BOOLEAN_SELECTOR
            fields[vol.Optional('tfaCode', default='')] = TEXT_SELECTOR

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
                LOGGER.debug(f"Printer {device['dev_id']} already registered with HA.")
                if self._show_existing:
                    printer_list.append(SelectOptionDict(value = device['dev_id'], label = f"{device['name']}: {device['dev_id']} (already registered)"))

        printer_selector = SelectSelector(
            SelectSelectorConfig(
                options=printer_list,
                mode=SelectSelectorMode.LIST)
        )

        LOGGER.debug(f"Printer count = {len(printer_list)}")
        if len(printer_list) == 0:
            if self._show_existing:
                return self.async_abort(reason='no_printers')

            LOGGER.debug("No unregistered printers found. Re-showing with full list.")
            self._show_existing = True
            return await self.async_step_Bambu_Choose_Device(None)

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

        device_type = self._bambu_cloud.get_device_type_from_device_product_name(device['dev_product_name'])
        default_host = ""
        if user_input is None:
            LOGGER.debug("Config Flow async_step_Bambu_Lan: Testing cloud mqtt to get printer IP address")
            config = {
                "region": self.region,
                "email": self.email,
                "username": self._bambu_cloud.username,
                "host": "",
                "local_mqtt": False,
                "auth_token": self._bambu_cloud.auth_token,
                'device_type': device_type,
                'serial': device['dev_id'],
            }
            bambu = BambuClient(config)
            success = await bambu.try_connection()
            default_host = bambu.get_device().info.ip_address if success else ""

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input.get('local_mqtt', False) == False)):
            success = True
            if user_input.get('host', "") != "":
                LOGGER.debug(f"Config Flow async_step_Bambu_Lan: Testing local mqtt to '{user_input.get('host', '')}'")
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
                if self._show_existing:
                    # Check to see if this device is already registered and delete it if so.
                    dev_reg = device_registry.async_get(self.hass)
                    hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, device['dev_id'])})
                    if hadevice is not None:
                        for config_entry in hadevice.config_entries:
                            LOGGER.debug(f"Removing existing config_entry: {config_entry}")
                            try:
                                # Remove the config entry
                                await self.hass.config_entries.async_remove(config_entry)
                                LOGGER.debug("Successfully removed config entry.")
                            except Exception as e:
                                LOGGER.error("Failed to remove config entry: %s", e)

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
                        "print_cache_count": max(-1, int(user_input['print_cache_count'])),
                        "timelapse_cache_count": max(-1, int(user_input['timelapse_cache_count'])),
                        "usage_hours": float(user_input['usage_hours']),
                        "disable_ssl_verify": user_input['advanced']['disable_ssl_verify'],
                        "enable_firmware_update": user_input['advanced']['enable_firmware_update'],
                        "force_ip": (user_input['host'] != bambu.get_device().info.ip_address),
                }

                title = device['dev_id']
                return self.async_create_entry(
                    title=title,
                    data=data,
                    options=options
                )

        default_host = default_host if user_input is None else user_input['host']
        default_access_code = device['dev_access_code'] if user_input is None else user_input['access_code']
        default_print_cache_count = "100" if user_input is None else user_input['print_cache_count']
        default_timelapse_cache_count = "1" if user_input is None else user_input['timelapse_cache_count']
        default_usage_hours = "0" if user_input is None else user_input['usage_hours']
        default_disable_ssl_verify = False if user_input is None else user_input.get('advanced', {}).get('disable_ssl_verify', '')
        default_enable_firmware_update = False if user_input is None else user_input.get('advanced', {}).get('enable_firmware_update', '')

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Optional('local_mqtt', default = False)] = BOOLEAN_SELECTOR
        fields[vol.Optional('host', default=default_host)] = TEXT_SELECTOR
        fields[vol.Optional('access_code', default = default_access_code)] = TEXT_SELECTOR
        fields[vol.Optional('print_cache_count', default=default_print_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('timelapse_cache_count', default=default_timelapse_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR
        fields[vol.Required('advanced')] = section(
            vol.Schema({
                vol.Required('disable_ssl_verify', default=default_disable_ssl_verify): BOOLEAN_SELECTOR,
                vol.Required('enable_firmware_update', default=default_enable_firmware_update): BOOLEAN_SELECTOR,
            }),
            {'collapsed': True},
        )
        
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

            LOGGER.debug(f"Config Flow async_step_Lan: Testing local mqtt to '{user_input.get('host','')}'")
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
                        "print_cache_count": max(-1, int(user_input['print_cache_count'])),
                        "timelapse_cache_count": max(-1, int(user_input['timelapse_cache_count'])),
                        "usage_hours": float(user_input['usage_hours']),
                        "disable_ssl_verify": user_input['advanced']['disable_ssl_verify'],
                        "enable_firmware_update": user_input['advanced']['enable_firmware_update'],
                        "force_ip": (user_input['host'] != bambu.get_device().info.ip_address),
                }

                title = user_input['serial']
                return self.async_create_entry(
                    title=title,
                    data=data,
                    options=options
                )

            errors['base'] = "cannot_connect_local_all"

        default_host = '' if user_input is None else user_input.get('host', '')
        default_serial = '' if user_input is None else user_input.get('serial', '')
        default_access_code = '' if user_input is None else user_input.get('access_code', '')
        default_print_cache_count = "100" if user_input is None else user_input['print_cache_count']
        default_timelapse_cache_count = "1" if user_input is None else user_input['timelapse_cache_count']
        default_usage_hours = "0" if user_input is None else user_input['usage_hours']
        default_disable_ssl_verify = False if user_input is None else user_input.get('advanced', {}).get('disable_ssl_verify', '')
        default_enable_firmware_update = False if user_input is None else user_input.get('advanced', {}).get('enable_firmware_update', '')

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('host', default = default_host)] = TEXT_SELECTOR
        fields[vol.Required('serial', default = default_serial)] = TEXT_SELECTOR
        fields[vol.Required('access_code', default = default_access_code)] = TEXT_SELECTOR
        fields[vol.Optional('print_cache_count', default=default_print_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('timelapse_cache_count', default=default_timelapse_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR
        fields[vol.Required('advanced')] = section(
            vol.Schema({
                vol.Required('disable_ssl_verify', default=default_disable_ssl_verify): BOOLEAN_SELECTOR,
                vol.Required('enable_firmware_update', default=default_enable_firmware_update): BOOLEAN_SELECTOR,
            }),
            {'collapsed': True},
        )

        return self.async_show_form(
            step_id="Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True,
        )

    async def async_step_ssdp(
            self, discovery_info: ssdp.SsdpServiceInfo
    ) -> FlowResult:
        LOGGER.debug("async_step_ssdp");
        return await self.async_step_user()


class BambuOptionsFlowHandler(config_entries.OptionsFlow):

    region: str = ""
    email: str = ""
    authentication_type: str = None
    _logging_level: None

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # Set logging level to DEBUG during the configuration flow
        LOGGER.warning("Setting logging level to DEBUG")
        self.__logging_level = LOGGER.getEffectiveLevel()
        LOGGER.setLevel(logging.DEBUG)

        self.config_entry = config_entry
        self.region = self.config_entry.options.get('region', '')
        self.email = self.config_entry.options.get('email', '')

        self._bambu_cloud = BambuCloud("", "", "", "")

        LOGGER.debug(self.config_entry)

    def __del__(self) -> None:
        # This isn't as immediate as I'd like it takes garbage collection but it'll kick in after a bit.
        LOGGER.warning("Restoring logging level")
        LOGGER.setLevel(self.__logging_level)

    async def async_step_init(self, user_input: None = None) -> FlowResult:
        errors = {}

        if user_input is not None:
            if user_input['printer_mode'] == "lan":
                self._bambu_cloud = BambuCloud("", "", "", "")
                return await self.async_step_Lan(None)
            elif user_input['printer_mode'] == "bambu":
                self._bambu_cloud = BambuCloud("", "", "", "")
                return await self.async_step_Bambu(None)
            elif user_input['printer_mode'] != "":
                return await self.async_step_Bambu_Lan(None)

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
                        break

        # Build form
        default_option = ''
        if self.email != '':
            default_option = self.email if self.config_entry.options['auth_token'] != "" else 'lan'
            modes = [
                SelectOptionDict(value="bambu", label=""),
                SelectOptionDict(value=self.email, label=self.email),
                SelectOptionDict(value="lan", label="")
            ]
        else:
            default_option = 'bambu' if self.config_entry.options['auth_token'] != "" else 'lan'
            modes = [
                SelectOptionDict(value="bambu", label=""),
                SelectOptionDict(value="lan", label="")
            ]

        selector = SelectSelector(
            SelectSelectorConfig(
                options=modes,
                translation_key="configuration_type",
                mode=SelectSelectorMode.LIST,
            )
        )
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required('printer_mode', default=default_option)] = selector

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
                if user_input.get('newCode', False):
                    await self.hass.async_add_executor_job(
                        self._bambu_cloud.request_new_code)

                elif self.authentication_type == 'verifyCode':
                    if user_input.get('verifyCode', '') != '':
                        await self.hass.async_add_executor_job(
                            self._bambu_cloud.login_with_verification_code,
                            user_input['verifyCode'])
                        return await self.async_step_Bambu_Lan(None)
                    else:
                        errors['base'] = "code_needed"

                elif self.authentication_type == 'tfaCode':
                    if user_input.get('tfaCode', '') != '':
                        await self.hass.async_add_executor_job(
                            self._bambu_cloud.login_with_2fa_code,
                            user_input['tfaCode'])
                        return await self.async_step_Bambu_Lan(None)
                    else:
                        errors['base'] = "code_needed"

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
            except CloudflareError:
                return self.async_abort(reason='cloudflare')
            except CurlUnavailableError:
                return self.async_abort(reason='curl_unavailable')
            except CodeExpiredError:
                errors['base'] = "code_expired"
                # Fall through to form generation to ask for verification code
            except CodeIncorrectError:
                errors['base'] = "code_incorrect"
                # Fall through to form generation to ask for verification code
            except CodeRequiredError:
                self.authentication_type = 'verifyCode'
                errors['base'] = 'verifyCode'
                # Fall through to form generation to ask for verification code
            except TfaCodeRequiredError:
                self.authentication_type = 'tfaCode'
                errors['base'] = 'tfaCode'
                # Fall through to form generation to ask for verification code
            except Exception as e:
                LOGGER.error(f"Failed to connect with error code {e.args}")
                errors['base'] = "cannot_connect"

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        if self.authentication_type is None:
            default_region = self.config_entry.options.get('region', '') if user_input is None else user_input.get('region', '')
            fields[vol.Required("region", default=default_region)] = REGION_SELECTOR
            default_email = self.config_entry.options.get('email','') if user_input is None else user_input.get('email', '')
            fields[vol.Required('email', default=default_email)] = TEXT_SELECTOR
            default_password = '' if user_input is None else user_input.get('password', '')
            fields[vol.Required('password', default=default_password)] = PASSWORD_SELECTOR
        elif self.authentication_type == 'verifyCode':
            fields[vol.Optional('newCode')] = BOOLEAN_SELECTOR
            fields[vol.Optional('verifyCode', default='')] = TEXT_SELECTOR
        elif self.authentication_type == 'tfaCode':
            fields[vol.Optional('newCode')] = BOOLEAN_SELECTOR
            fields[vol.Optional('tfaCode', default='')] = TEXT_SELECTOR

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

        default_host = ""
        if user_input is None:
            LOGGER.debug("Options Flow async_step_Bambu_Lan: Testing cloud mqtt to get printer IP address")
            config = {
                "region": self.region,
                "email": self.email,
                "username": self._bambu_cloud.username,
                "host": "",
                "local_mqtt": False,
                "auth_token": self._bambu_cloud.auth_token,
                'device_type': self.config_entry.data['device_type'],
                'serial': self.config_entry.data['serial'],
            }
            bambu = BambuClient(config)
            success = await bambu.try_connection()
            default_host = bambu.get_device().info.ip_address if success else ""

        if (user_input is not None) and ((user_input.get('host', "") != "") or (user_input['local_mqtt'] == False)):
            for device in device_list:
                if device['dev_id'] == user_input['serial']:

                    success = True
                    if user_input.get('host', "") != "":
                        LOGGER.debug(f"Options Flow async_step_Bambu_Lan: Testing local mqtt to '{user_input.get('host', '')}'")
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
                        options = dict(self.config_entry.options)
                        options["region"] = self.region
                        options["email"] = self.email
                        options["username"] = self._bambu_cloud.username
                        options["name"] = device['name']
                        options["host"] = user_input['host']
                        options["local_mqtt"] = user_input.get('local_mqtt', False)
                        options["auth_token"] = self._bambu_cloud.auth_token
                        options["access_code"] = user_input['access_code']
                        options["usage_hours"] = float(user_input['usage_hours'])
                        options["disable_ssl_verify"] = user_input['advanced']['disable_ssl_verify']
                        options["enable_firmware_update"] = user_input['advanced']['enable_firmware_update']
                        options["print_cache_count"] = max(-1, int(user_input['print_cache_count']))
                        options["timelapse_cache_count"] = max(-1, int(user_input['timelapse_cache_count']))
                        options["force_ip"] = user_input['host'] != bambu.get_device().info.ip_address
                        
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

        if user_input is not None:
            default_host = user_input['host']
        default_serial = self.config_entry.data['serial']
        default_local_mqtt = self.config_entry.options.get('local_mqtt', False)
        default_access_code = self.config_entry.options.get('access_code', access_code)
        default_print_cache_count = self.config_entry.options.get('print_cache_count', 100) if user_input is None else user_input['print_cache_count']
        default_timelapse_cache_count = self.config_entry.options.get('timelapse_cache_count', 1) if user_input is None else user_input['timelapse_cache_count']
        default_usage_hours = str(self.config_entry.options.get('usage_hours', 0)) if user_input is None else user_input['usage_hours']
        default_disable_ssl_verify = self.config_entry.options.get('disable_ssl_verify', False) if user_input is None else user_input.get('advanced', {}).get('disable_ssl_verify', self.config_entry.options.get('disable_ssl_verify', ''))
        default_enable_firmware_update = self.config_entry.options.get('enable_firmware_update', False) if user_input is None else user_input.get('advanced', {}).get('enable_firmware_update', self.config_entry.options.get('enable_firmware_update', ''))

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Optional('host', default=default_host)] = TEXT_SELECTOR
        fields[vol.Required('serial', default=default_serial)] = printer_selector
        fields[vol.Optional('local_mqtt', default=default_local_mqtt)] = BOOLEAN_SELECTOR
        fields[vol.Optional('access_code', default=default_access_code)] = TEXT_SELECTOR
        fields[vol.Optional('print_cache_count', default=default_print_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('timelapse_cache_count', default=default_timelapse_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR
        fields[vol.Required('advanced')] = section(
            vol.Schema({
                vol.Required('disable_ssl_verify', default=default_disable_ssl_verify): BOOLEAN_SELECTOR,
                vol.Required('enable_firmware_update', default=default_enable_firmware_update): BOOLEAN_SELECTOR,
            }),
            {'collapsed': True},
        )

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
            LOGGER.debug(f"Options Flow async_step_Lan: Testing local mqtt to '{user_input.get('host', '')}'")
            config = {
                'access_code': user_input['access_code'],
                'device_type': self.config_entry.data['device_type'],
                'host': user_input['host'],
                'local_mqtt': True,
                'serial': self.config_entry.data['serial'],
                'disable_ssl_verify': user_input['advanced']['disable_ssl_verify'],
            }
            bambu = BambuClient(config)
            success = await bambu.try_connection()

            if success:
                LOGGER.debug("Options Flow: Writing entry")
                data = dict(self.config_entry.data)
                options = dict(self.config_entry.options)
                options["region"] = self.config_entry.options.get('region', '')
                options["email"] = ''
                options["username"] = ''
                options["name"] = self.config_entry.options.get('name', '')
                options["host"] = user_input['host']
                options["local_mqtt"] = True
                options["auth_token"] = ''
                options["access_code"] = user_input['access_code']
                options["print_cache_count"] = max(-1, int(user_input['print_cache_count']))
                options["timelapse_cache_count"] = max(-1, int(user_input['timelapse_cache_count']))
                options["usage_hours"] = float(user_input['usage_hours'])
                options["disable_ssl_verify"] = user_input['advanced']['disable_ssl_verify']
                options["enable_firmware_update"] = user_input['advanced']['enable_firmware_update']
                options["force_ip"] = (user_input['host'] != bambu.get_device().info.ip_address)

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
        default_print_cache_count = self.config_entry.options.get('print_cache_count', 100) if user_input is None else user_input['print_cache_count']
        default_timelapse_cache_count = self.config_entry.options.get('timelapse_cache_count', 1) if user_input is None else user_input['timelapse_cache_count']
        default_usage_hours = str(self.config_entry.options.get('usage_hours', 0)) if user_input is None else user_input['usage_hours']
        default_disable_ssl_verify = self.config_entry.options.get('disable_ssl_verify', False) if user_input is None else user_input.get('advanced', {}).get('disable_ssl_verify', self.config_entry.options.get('disable_ssl_verify', ''))
        default_enable_firmware_update = self.config_entry.options.get('enable_firmware_update', False) if user_input is None else user_input.get('advanced', {}).get('enable_firmware_update', self.config_entry.options.get('enable_firmware_update', ''))

        fields[vol.Required('host', default=default_host)] = TEXT_SELECTOR
        fields[vol.Required('access_code', default=default_access_code)] = TEXT_SELECTOR
        fields[vol.Optional('print_cache_count', default=default_print_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('timelapse_cache_count', default=default_timelapse_cache_count)] = NUMBER_SELECTOR
        fields[vol.Optional('usage_hours', default=default_usage_hours)] = NUMBER_SELECTOR
        fields[vol.Required('advanced')] = section(
            vol.Schema({
                vol.Required('disable_ssl_verify', default=default_disable_ssl_verify): BOOLEAN_SELECTOR,
                vol.Required('enable_firmware_update', default=default_enable_firmware_update): BOOLEAN_SELECTOR,
            }),
            {'collapsed': True},
        )

        return self.async_show_form(
            step_id="Lan",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=True,
        )
