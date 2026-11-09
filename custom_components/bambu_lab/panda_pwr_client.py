"""Polling HTTP client for a BIQU Panda PWR, shaped like PandaWebSocketClient.

It exposes the same state / connected / async_add_listener / async_send surface so
the Panda entities can treat every linked Panda device the same way.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import LOGGER
from .panda_pwr import PandaPwrState, parse_device_info, parse_ele_data

POLL_INTERVAL = timedelta(seconds=30)
# Give the relay a moment before re-reading after a command, so the re-poll
# doesn't put the old state back.
CONFIRM_DELAY_SECONDS = 3
REQUEST_TIMEOUT = 10
HTTP_OK = 200


def base_url(host: str) -> str:
    return f"http://{host.strip()}"


async def _async_get_json(session: aiohttp.ClientSession, host: str, path: str):
    async with asyncio.timeout(REQUEST_TIMEOUT):
        async with session.get(f"{base_url(host)}{path}") as response:
            if response.status != HTTP_OK:
                raise aiohttp.ClientResponseError(
                    response.request_info, response.history, status=response.status
                )
            return await response.json(content_type=None)


async def async_test_pwr_connection(hass: HomeAssistant, host: str) -> bool:
    """Return True if a Panda PWR answers at this host."""
    try:
        parse_ele_data(await _async_get_json(async_get_clientsession(hass), host, "/update_ele_data"))
        return True
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as err:
        LOGGER.debug("Panda PWR at %s not reachable: %s", host, err)
        return False


class PandaPwrClient:
    """Polls one Panda PWR and switches its outputs."""

    name = "Panda PWR"

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        self.hass = hass
        self.host = host.strip()
        self._state = PandaPwrState()
        self._connected = False
        self.firmware_version: str | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsub_timer: Callable[[], None] | None = None
        self._unsub_confirm: Callable[[], None] | None = None
        self._stopped = False
        # Bumped on every command; a poll that started before a command is discarded.
        self._generation = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> PandaPwrState:
        return self._state

    @property
    def connected(self) -> bool:
        return self._connected

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def async_start(self, entry) -> None:
        if self._unsub_timer is not None:
            return
        self._unsub_timer = async_track_time_interval(self.hass, self._handle_timer, POLL_INTERVAL)
        entry.async_create_background_task(self.hass, self.async_refresh(fetch_info=True), "panda_pwr_first_poll")

    async def async_stop(self) -> None:
        self._stopped = True
        for unsub in (self._unsub_timer, self._unsub_confirm):
            if unsub is not None:
                unsub()
        self._unsub_timer = None
        self._unsub_confirm = None

    @callback
    def _handle_timer(self, _now) -> None:
        self.hass.async_create_task(self.async_refresh(fetch_info=self.firmware_version is None))

    async def async_refresh(self, fetch_info: bool = False) -> None:
        if self._stopped:
            return
        generation = self._generation
        session = async_get_clientsession(self.hass)
        try:
            state = parse_ele_data(await _async_get_json(session, self.host, "/update_ele_data"))
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as err:
            if self._stopped:
                return
            if self._connected:
                LOGGER.debug("Panda PWR %s poll failed: %s", self.host, err)
            self._connected = False
            self._notify()
            return
        if fetch_info:
            await self._async_fetch_info(session)
        if self._stopped:
            return
        self._connected = True
        if generation == self._generation:
            self._state = state
        self._notify()

    async def _async_fetch_info(self, session: aiohttp.ClientSession) -> None:
        """Firmware is only for the device page; a failure here must not mark the device down."""
        try:
            info = parse_device_info(await _async_get_json(session, self.host, "/get_state"))
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as err:
            LOGGER.debug("Panda PWR %s: could not read device info: %s", self.host, err)
            return
        self.firmware_version = info.get("firmware_version") or self.firmware_version

    @callback
    def _handle_confirm(self, _now) -> None:
        self._unsub_confirm = None
        self.hass.async_create_task(self.async_refresh())

    async def async_send(self, payload: str, optimistic: dict) -> None:
        """POST a /set command, apply the expected state change, and re-poll shortly after."""
        if self._stopped:
            raise HomeAssistantError(f"Panda PWR at {self.host} is no longer linked")
        session = async_get_clientsession(self.hass)
        async with self._lock:
            self._generation += 1
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    async with session.post(f"{base_url(self.host)}/set", data=payload) as response:
                        if response.status != HTTP_OK:
                            raise HomeAssistantError(
                                f"Panda PWR at {self.host} rejected the command ({response.status})"
                            )
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                raise HomeAssistantError(f"Could not reach Panda PWR at {self.host}: {err}") from err
            self._state = replace(self._state, **optimistic)
            self._notify()
        if self._unsub_confirm is not None:
            self._unsub_confirm()
        self._unsub_confirm = async_call_later(self.hass, CONFIRM_DELAY_SECONDS, self._handle_confirm)
