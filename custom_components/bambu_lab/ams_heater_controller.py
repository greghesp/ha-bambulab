"""Drive an external AMS heater or dryer (e.g. SUNLU AMS Heater, EIBOS Series X) through a smart plug.

The user links a Home Assistant switch entity (the smart plug the heater is
powered from) to an AMS in the integration options. While drying mode is on,
this controller re-evaluates on every printer update and switches the plug
using the decision logic in ams_heater.py.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .ams_heater import (
    HeaterReading,
    HeaterSettings,
    REASON_MAX_RUNTIME,
    decide,
    normalize_humidity,
    normalize_temperature,
    should_clear_lockout,
)
from .const import CONF_AMS_HEATERS, LOGGER
from .pybambu.const import Features

SWITCH_DOMAIN = "switch"

# Don't repeat the same plug command while the plug has not yet reported the
# new state, so a slow or failing plug isn't flooded on every MQTT update.
COMMAND_RETRY_INTERVAL = timedelta(seconds=30)

# Re-check on a timer too, so the safety rules still run when the printer goes
# quiet (powered off, MQTT stalled) and sends no updates.
EVALUATE_INTERVAL = timedelta(seconds=60)


class AmsHeaterController:
    """Controls the smart plug powering an external heater on one AMS."""

    def __init__(self, hass: HomeAssistant, coordinator, ams_serial: str, plug_entity_id: str) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.ams_serial = ams_serial
        self.plug_entity_id = plug_entity_id
        self._settings = HeaterSettings()
        self._locked_out = False
        self._last_reason: str | None = None
        self._last_command: bool | None = None
        self._last_command_time = None
        self._unsubs: list[Callable[[], None]] = []
        self._running = False

    @property
    def settings(self) -> HeaterSettings:
        return self._settings

    @property
    def last_reason(self) -> str | None:
        return self._last_reason

    @property
    def locked_out(self) -> bool:
        return self._locked_out

    @property
    def plug_available(self) -> bool:
        state = self.hass.states.get(self.plug_entity_id)
        return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    @property
    def plug_is_on(self) -> bool:
        state = self.hass.states.get(self.plug_entity_id)
        return state is not None and state.state == STATE_ON

    @callback
    def async_start(self) -> None:
        if self._running:
            return
        self._running = True
        self._unsubs = [
            self.coordinator.async_add_listener(self._handle_coordinator_update),
            async_track_time_interval(self.hass, self._handle_timer, EVALUATE_INTERVAL),
        ]

    @callback
    def async_stop(self) -> None:
        """Stop controlling the plug, switching the heater off if drying was running.

        Runs on unload, which also happens when the plug is unlinked or changed in
        the options, so a plug that is no longer controlled is never left on.
        A reload re-creates the controller and re-evaluates from the restored state.
        """
        if not self._running:
            return
        self._running = False
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        if self._settings.drying_enabled and self.plug_available and self.plug_is_on:
            LOGGER.info("AMS heater %s: switching %s off on unload", self.ams_serial, self.plug_entity_id)
            self.hass.async_create_task(self._async_call_plug(False))

    @callback
    def async_restore_settings(self, **changes) -> None:
        """Apply restored settings without validation or re-evaluation."""
        self._settings = replace(self._settings, **changes)

    async def async_update_settings(self, **changes) -> None:
        """Apply new settings and re-evaluate the plug immediately."""
        was_drying = self._settings.drying_enabled
        if changes.get("drying_enabled"):
            # Turning drying mode on again is the user's way to clear a max-runtime lockout.
            self._locked_out = False
        self._settings = replace(self._settings, **changes)
        if was_drying and not self._settings.drying_enabled:
            # Stopping drying stops the heater; afterwards the plug is left to manual control.
            self._last_reason = None
            if self.plug_available and self.plug_is_on:
                await self.async_set_plug(False)
            return
        await self.async_evaluate()

    async def async_set_plug(self, on: bool) -> None:
        self._last_command = on
        self._last_command_time = dt_util.utcnow()
        await self._async_call_plug(on)

    async def _async_call_plug(self, on: bool) -> None:
        service = SERVICE_TURN_ON if on else SERVICE_TURN_OFF
        try:
            await self.hass.services.async_call(
                SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: self.plug_entity_id}, blocking=True
            )
        except HomeAssistantError as err:
            LOGGER.warning("AMS heater %s: could not switch %s: %s", self.ams_serial, self.plug_entity_id, err)

    def _ams_instance(self):
        for ams in self.coordinator.get_model().ams.data.values():
            if ams is not None and ams.serial == self.ams_serial:
                return ams
        return None

    def _reading(self) -> HeaterReading:
        model = self.coordinator.get_model()
        ams = self._ams_instance()
        if ams is None:
            return HeaterReading(humidity=None, temperature=None, printer_online=model.info.online)
        humidity = normalize_humidity(ams.humidity) if model.supports_feature(Features.AMS_HUMIDITY) else None
        temperature = (
            normalize_temperature(ams.temperature) if model.supports_feature(Features.AMS_TEMPERATURE) else None
        )
        return HeaterReading(humidity=humidity, temperature=temperature, printer_online=model.info.online)

    def _on_for_hours(self) -> float:
        state = self.hass.states.get(self.plug_entity_id)
        if state is None or state.state != STATE_ON:
            return 0.0
        return (dt_util.utcnow() - state.last_changed).total_seconds() / 3600

    def _recently_sent(self, on: bool) -> bool:
        if self._last_command != on or self._last_command_time is None:
            return False
        return dt_util.utcnow() - self._last_command_time < COMMAND_RETRY_INTERVAL

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _handle_timer(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate())

    async def async_evaluate(self) -> None:
        if not self._running:
            return
        reading = self._reading()
        if should_clear_lockout(self._settings, reading, self._locked_out):
            self._locked_out = False

        decision = decide(self._settings, reading, self.plug_is_on, self._on_for_hours(), self._locked_out)
        if decision is None:
            self._last_reason = None
            return
        if decision.reason == REASON_MAX_RUNTIME:
            self._locked_out = True
        self._last_reason = decision.reason

        if not self.plug_available or decision.on == self.plug_is_on or self._recently_sent(decision.on):
            return
        LOGGER.info(
            "AMS heater %s: switching %s %s (%s)",
            self.ams_serial, self.plug_entity_id, "on" if decision.on else "off", decision.reason,
        )
        await self.async_set_plug(decision.on)


@callback
def async_setup_ams_heaters(hass: HomeAssistant, entry: ConfigEntry, coordinator) -> dict[str, AmsHeaterController]:
    """Create and start a controller for each AMS that has a heater plug linked."""
    controllers: dict[str, AmsHeaterController] = {}
    for ams_serial, plug_entity_id in entry.options.get(CONF_AMS_HEATERS, {}).items():
        if not ams_serial or not plug_entity_id:
            continue
        controller = AmsHeaterController(hass, coordinator, ams_serial, plug_entity_id)
        controller.async_start()
        entry.async_on_unload(controller.async_stop)
        controllers[ams_serial] = controller
    return controllers
