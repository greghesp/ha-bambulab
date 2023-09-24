from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo, event_trigger
from homeassistant.helpers.typing import ConfigType

from . import trigger
from .const import DOMAIN, LOGGER


TRIGGER_TYPES = { "something_happened " }
TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


# async def async_validate_trigger_config(
#     hass: HomeAssistant, config: ConfigType
# ) -> ConfigType:
#     """Validate config."""
#     config = TRIGGER_SCHEMA(config)

#     if config[CONF_TYPE] == TURN_ON_PLATFORM_TYPE:
#         device_id = config[CONF_DEVICE_ID]
#         try:
#             device = async_get_device_entry_by_device_id(hass, device_id)
#             if DOMAIN in hass.data:
#                 async_get_client_by_device_entry(hass, device)
#         except ValueError as err:
#             raise InvalidDeviceAutomationConfig(err) from err

#     return config


async def async_get_triggers(hass, device_id):
    """Return a list of triggers."""
    LOGGER.debug("!!!!!!!!!!!!!!!!!!!! device_trigger::async_get_triggers")

    device_registry = device_registry.async_get(hass)
    device = device_registry.async_get(device_id)

    triggers = []

    # Determine which triggers are supported by this device_id ...

    triggers.append({
        # Required fields of TRIGGER_BASE_SCHEMA
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device_id,
        # Required fields of TRIGGER_SCHEMA
        CONF_TYPE: "something_happened",
    })

    return triggers


async def async_attach_trigger(hass, config, action, trigger_info):
    """Attach a trigger."""
    LOGGER.debug("!!!!!!!!!!!!!!!!!!!! device_trigger::async_attach_trigger")

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: "mydomain_event",
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )