"""Optional checks that concurrent service calls each get their own result (#2217).

Run in a Home Assistant Python environment; they skip when it is absent. No MQTT
connection is made.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.core import Event
from custom_components.bambu_lab import async_call_service
from custom_components.bambu_lab.const import (
    DOMAIN,
    SERVICE_CALL_EVENT,
    SERVICE_CALL_FUTURES,
    SERVICE_CALL_ID,
)
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator


def _coordinator(hass, result_for):
    """A coordinator that answers every call aimed at it with result_for(data)."""
    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._hass = hass
    coordinator._is_service_call_for_me = lambda data: True
    coordinator._run_service_call = result_for
    return coordinator


class _Bus:
    """Delivers fired events to the coordinator on the next loop iteration, like HA's bus."""

    def __init__(self):
        self.coordinator = None

    def fire(self, event_type, data):
        assert event_type == SERVICE_CALL_EVENT
        asyncio.get_running_loop().create_task(
            self.coordinator._handle_service_call_event(Event(event_type, dict(data)))
        )


def test_concurrent_calls_each_get_their_own_result():
    async def run():
        hass = SimpleNamespace(data={DOMAIN: {}}, bus=_Bus())
        hass.bus.coordinator = _coordinator(hass, lambda data: {"entity": data["entity_id"]})

        results = await asyncio.gather(
            *(
                async_call_service(hass, "get_filament_data", {"entity_id": f"sensor.tray_{i}"})
                for i in range(5)
            )
        )
        return hass, results

    hass, results = asyncio.run(run())

    assert results == [{"entity": f"sensor.tray_{i}"} for i in range(5)]
    assert hass.data[DOMAIN][SERVICE_CALL_FUTURES] == {}


def test_event_resolves_only_the_future_of_its_own_call():
    async def run():
        loop = asyncio.get_running_loop()
        mine, other = loop.create_future(), loop.create_future()
        hass = SimpleNamespace(data={DOMAIN: {SERVICE_CALL_FUTURES: {"a": mine, "b": other}}})
        coordinator = _coordinator(hass, lambda data: {"ok": True})
        await coordinator._handle_service_call_event(
            Event(SERVICE_CALL_EVENT, {"service": "get_filament_data", SERVICE_CALL_ID: "a"})
        )
        return mine, other

    mine, other = asyncio.run(run())

    assert mine.result() == {"ok": True}
    assert not other.done()


def test_timed_out_call_is_removed_and_returns_none():
    async def run():
        hass = SimpleNamespace(data={DOMAIN: {}}, bus=MagicMock())
        result = await async_call_service(hass, "get_filament_data", {"entity_id": "x"}, timeout=0.01)
        return hass, result

    hass, result = asyncio.run(run())

    assert result is None
    assert hass.data[DOMAIN][SERVICE_CALL_FUTURES] == {}
