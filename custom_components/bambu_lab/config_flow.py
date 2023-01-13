"""Config flow to configure Bambu Lab."""
from __future__ import annotations

import voluptuous as vol
import queue
from collections.abc import Awaitable
from typing import Any
from homeassistant.const import CONF_HOST, CONF_MAC

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from .const import DOMAIN, LOGGER


class BambuLabFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Bambu Lab config flow. The MQTT step is inherited from the parent class."""

    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                user_input,
            )

            if can_connect:
                return self.async_create_entry(
                    title=user_input["name"],
                    data={
                        "serial": can_connect,
                        CONF_HOST: user_input[CONF_HOST],
                        "name": user_input["name"]
                    }
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str, vol.Required("name"): str}),
            errors=errors or {},
        )

    async def async_step_confirm(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup."""

        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
            )

        return await super().async_step_confirm(user_input)


def try_connection(
        user_input: dict[str, Any],
):
    """Test if we can connect to an MQTT broker."""
    # We don't import on the top because some integrations
    # should be able to optionally rely on MQTT.
    import paho.mqtt.client as mqtt  # pylint: disable=import-outside-toplevel

    client = mqtt.Client()
    serial: str
    result: queue.Queue[bool] = queue.Queue(maxsize=1)

    def on_connect(
            client_: mqtt.Client,
            userdata: None,
            flags: dict[str, Any],
            result_code: int,
            properties: mqtt.Properties | None = None,
    ) -> None:
        """Handle connection result."""

    def on_message(client, userdata, message):
        nonlocal serial
        serial = message.topic.split('/')[1]
        result.put(True)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(user_input[CONF_HOST], 1883)
    client.loop_start()
    client.subscribe("device/+/report")

    try:
        if result.get(timeout=5):
            return serial
    except queue.Empty:
        return False
    finally:
        client.disconnect()
        client.loop_stop()
