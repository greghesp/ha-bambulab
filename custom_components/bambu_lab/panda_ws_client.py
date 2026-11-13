"""Reconnecting WebSocket client shared by BIQU Panda devices (Panda Breath, Panda Status).

Both serve unauthenticated JSON at ws://<host>/ws and push fields piecemeal; each
device supplies its own immutable state type and apply function.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER
from .panda_breath import parse_message

CONNECT_TIMEOUT = 10
HEARTBEAT_SECONDS = 30
RECONNECT_MIN_SECONDS = 5
RECONNECT_MAX_SECONDS = 60


def websocket_url(host: str) -> str:
    return f"ws://{host.strip()}/ws"


async def async_test_connection(hass: HomeAssistant, host: str) -> bool:
    """Return True if a Panda device WebSocket answers at this host."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            ws = await session.ws_connect(
                websocket_url(host), timeout=aiohttp.ClientWSTimeout(ws_close=CONNECT_TIMEOUT)
            )
            await ws.close()
        return True
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        LOGGER.debug("Panda device at %s not reachable: %s", host, err)
        return False


class PandaWebSocketClient:
    """Keeps a WebSocket open to one Panda device and tracks its state."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        initial_state: Any,
        apply_fn: Callable[[Any, dict[str, Any]], Any],
        name: str,
    ) -> None:
        self.hass = hass
        self.host = host.strip()
        self.name = name
        self._apply = apply_fn
        self._state = initial_state
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._listeners: list[Callable[[], None]] = []

    @property
    def state(self) -> Any:
        return self._state

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

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
        if self._task is None:
            self._task = entry.async_create_background_task(
                self.hass, self._async_run(), f"{self.name}_{self.host}"
            )

    async def async_stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
        ws, self._ws = self._ws, None
        if ws is not None and not ws.closed:
            await ws.close()

    async def _async_run(self) -> None:
        delay = RECONNECT_MIN_SECONDS
        session = async_get_clientsession(self.hass)
        while True:
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    ws = await session.ws_connect(
                        websocket_url(self.host),
                        timeout=aiohttp.ClientWSTimeout(ws_close=CONNECT_TIMEOUT),
                        heartbeat=HEARTBEAT_SECONDS,
                    )
                async with ws:
                    self._ws = ws
                    delay = RECONNECT_MIN_SECONDS
                    LOGGER.debug("%s %s connected", self.name, self.host)
                    self._notify()
                    await self._async_receive(ws)
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                LOGGER.debug("%s %s connection failed: %s", self.name, self.host, err)
            except Exception:  # noqa: BLE001 - never let one bad frame end the reconnect loop
                LOGGER.exception("%s %s: unexpected error, reconnecting", self.name, self.host)
            finally:
                self._ws = None
                self._notify()
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_SECONDS)

    async def _async_receive(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                self.handle_text(msg.data)
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                break

    @callback
    def handle_text(self, raw: str) -> None:
        message = parse_message(raw)
        if message is None:
            LOGGER.debug("%s %s: ignoring non-JSON frame", self.name, self.host)
            return
        new_state = self._apply(self._state, message)
        if new_state != self._state:
            self._state = new_state
            self._notify()

    async def async_send(self, messages: list[dict[str, Any]]) -> None:
        """Send commands and apply them to the local state (the device does not echo them)."""
        ws = self._ws
        if ws is None or ws.closed:
            raise HomeAssistantError(f"{self.name} at {self.host} is not connected")
        try:
            for message in messages:
                await ws.send_json(message)
        except (aiohttp.ClientError, ConnectionResetError, asyncio.TimeoutError) as err:
            raise HomeAssistantError(f"Could not send to {self.name} at {self.host}: {err}") from err
        new_state = self._state
        for message in messages:
            new_state = self._apply(new_state, message)
        self._state = new_state
        self._notify()
