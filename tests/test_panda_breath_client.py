"""Optional checks for the Panda Breath WebSocket client and entities.

Like test_fan_entity.py, these need Home Assistant installed and skip without it.
The round-trip test runs a fake Panda Breath WebSocket server on localhost.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

import aiohttp
from aiohttp import web
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.bambu_lab import panda_breath_client
from custom_components.bambu_lab.panda_breath import MODE_ALWAYS_ON, MODE_AUTO
from custom_components.bambu_lab.panda_breath_client import PandaBreathClient
from custom_components.bambu_lab.panda_breath_entities import (
    PANDA_BREATH_NUMBERS,
    PandaBreathDryingSwitch,
    PandaBreathModeSelect,
    PandaBreathNumber,
    number_entities,
    sensor_entities,
)


def run(coro):
    return asyncio.run(coro)


def connected_client():
    client = PandaBreathClient(MagicMock(), "192.168.1.50")
    client._ws = MagicMock(closed=False)
    client._ws.send_json = AsyncMock()
    return client


def sent(client):
    return [c.args[0] for c in client._ws.send_json.await_args_list]


def coordinator_for(client):
    return SimpleNamespace(panda_breath=client, config_entry=SimpleNamespace(data={"serial": "PRINTER1"}))


def test_handle_text_updates_state_and_notifies():
    client = PandaBreathClient(MagicMock(), "pb.local")
    listener = MagicMock()
    client.async_add_listener(listener)
    client.handle_text('{"settings": {"cal_warehouse_temp": 41.5}}')
    assert client.state.chamber_temperature == 41.5
    listener.assert_called_once()
    client.handle_text("garbage")
    listener.assert_called_once()


def test_remove_listener():
    client = PandaBreathClient(MagicMock(), "pb.local")
    listener = MagicMock()
    remove = client.async_add_listener(listener)
    remove()
    client.handle_text('{"settings": {"work_on": true}}')
    listener.assert_not_called()


def test_send_without_connection_raises():
    client = PandaBreathClient(MagicMock(), "pb.local")
    with pytest.raises(HomeAssistantError, match="not connected"):
        run(client.async_send([{"settings": {"work_on": True}}]))


def test_send_applies_optimistic_state():
    client = connected_client()
    run(client.async_send([{"settings": {"work_on": True, "work_mode": 2}}]))
    assert sent(client) == [{"settings": {"work_on": True, "work_mode": 2}}]
    assert client.state.power is True
    assert client.state.mode == MODE_ALWAYS_ON


def test_target_temperature_number_uses_current_mode():
    client = connected_client()
    client.handle_text(json.dumps({"settings": {"work_mode": 1}}))
    number = PandaBreathNumber(coordinator_for(client), PANDA_BREATH_NUMBERS[0])
    run(number.async_set_native_value(42))
    assert sent(client) == [{"settings": {"temp": 42, "target_temp": 42}}]
    assert client.state.mode == MODE_AUTO


def test_out_of_range_number_is_a_validation_error():
    client = connected_client()
    number = PandaBreathNumber(coordinator_for(client), PANDA_BREATH_NUMBERS[0])
    with pytest.raises(ServiceValidationError):
        run(number.async_set_native_value(90))
    assert sent(client) == []


def test_drying_switch_uses_defaults_then_reported_values():
    client = connected_client()
    switch = PandaBreathDryingSwitch(coordinator_for(client))
    run(switch.async_turn_on())
    assert sent(client)[-1]["settings"]["filament_temp"] == 50
    assert sent(client)[-1]["settings"]["filament_timer"] == 6
    assert switch.is_on is True

    client.handle_text('{"settings": {"filament_temp": 45, "filament_timer": 3}}')
    run(switch.async_turn_off())
    assert sent(client)[-1] == {"settings": {"isrunning": 0, "drying_running": False}}
    run(switch.async_turn_on())
    assert sent(client)[-1]["settings"]["filament_temp"] == 45
    assert sent(client)[-1]["settings"]["filament_timer"] == 3


def test_mode_select_and_availability():
    client = connected_client()
    select = PandaBreathModeSelect(coordinator_for(client))
    run(select.async_select_option("filament_drying"))
    assert sent(client) == [{"settings": {"work_mode": 3}}]
    assert select.available
    client._ws.closed = True
    assert not select.available


def test_unique_ids_and_no_entities_when_unlinked():
    client = connected_client()
    ids = {e.unique_id for e in sensor_entities(coordinator_for(client)) + number_entities(coordinator_for(client))}
    assert "PRINTER1_panda_breath_chamber_temperature" in ids
    assert len(ids) == 8
    unlinked = SimpleNamespace(panda_breath=None, config_entry=SimpleNamespace(data={"serial": "X"}))
    assert sensor_entities(unlinked) == [] and number_entities(unlinked) == []


def test_round_trip_against_fake_device():
    """Connect to a local fake Panda Breath, receive pushes, send a command."""

    async def scenario():
        received = []
        got_command = asyncio.Event()

        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_str('{"settings": {"fw_version": "V1.0.4"}}')
            await ws.send_str('{"settings": {"cal_warehouse_temp": 36.5, "work_on": false}}')
            async for msg in ws:
                received.append(json.loads(msg.data))
                got_command.set()
            return ws

        app = web.Application()
        app.router.add_get("/ws", ws_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]

        async with aiohttp.ClientSession() as session:
            with patch.object(panda_breath_client, "async_get_clientsession", return_value=session):
                client = PandaBreathClient(MagicMock(), f"127.0.0.1:{port}")
                task = asyncio.create_task(client._async_run())
                for _ in range(100):
                    if client.state.chamber_temperature is not None:
                        break
                    await asyncio.sleep(0.02)
                assert client.connected
                assert client.state.firmware_version == "V1.0.4"
                assert client.state.chamber_temperature == 36.5
                assert client.state.power is False

                await client.async_send([{"settings": {"work_on": True}}])
                await asyncio.wait_for(got_command.wait(), 2)
                assert received == [{"settings": {"work_on": True}}]

                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert not client.connected
        await runner.cleanup()

    run(scenario())


def test_connection_test_reports_unreachable_host():
    async def scenario():
        async with aiohttp.ClientSession() as session:
            with patch.object(panda_breath_client, "async_get_clientsession", return_value=session):
                return await panda_breath_client.async_test_connection(MagicMock(), "127.0.0.1:1")

    assert run(scenario()) is False


def _number(client, key):
    description = next(d for d in PANDA_BREATH_NUMBERS if d.key == key)
    return PandaBreathNumber(coordinator_for(client), description)


def test_drying_numbers_send_only_their_own_field():
    client = connected_client()
    run(_number(client, "drying_temperature").async_set_native_value(55))
    run(_number(client, "drying_time").async_set_native_value(3))
    assert sent(client) == [{"settings": {"filament_temp": 55}}, {"settings": {"filament_timer": 3}}]


def test_target_temperature_refused_while_drying():
    client = connected_client()
    client.handle_text('{"settings": {"work_mode": 3}}')
    with pytest.raises(ServiceValidationError, match="Auto or Always on"):
        run(_number(client, "target_temperature").async_set_native_value(45))
    assert sent(client) == []


def test_leaving_drying_mode_stops_drying_first():
    client = connected_client()
    client.handle_text('{"settings": {"work_mode": 3, "drying_running": "ON"}}')
    run(PandaBreathModeSelect(coordinator_for(client)).async_select_option("always_on"))
    assert sent(client) == [
        {"settings": {"isrunning": 0, "drying_running": False}},
        {"settings": {"work_mode": 2}},
    ]
    assert client.state.drying is False
