"""Optional checks for the BIQU Panda device clients and entities.

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

from custom_components.bambu_lab import panda_pwr_client, panda_ws_client
from custom_components.bambu_lab.panda_breath import MODE_ALWAYS_ON, MODE_AUTO, PandaBreathState, apply_message
from custom_components.bambu_lab.panda_breath_entities import (
    PANDA_BREATH_NUMBERS,
    PandaBreathDryingSwitch,
    PandaBreathModeSelect,
    PandaBreathNumber,
)
from custom_components.bambu_lab.panda_devices import PANDA_BREATH, PANDA_PWR, PANDA_STATUS
from custom_components.bambu_lab.panda_entities import platform_entities
from custom_components.bambu_lab.panda_pwr import PandaPwrState
from custom_components.bambu_lab.panda_pwr_client import PandaPwrClient
from custom_components.bambu_lab.panda_status import PandaStatusState, apply_status_message
from custom_components.bambu_lab.panda_ws_client import PandaWebSocketClient


def PandaBreathClient(hass, host):
    return PandaWebSocketClient(hass, host, PandaBreathState(), apply_message, "Panda Breath")


def run(coro):
    return asyncio.run(coro)


def connected_client():
    client = PandaBreathClient(MagicMock(), "192.168.1.50")
    client._ws = MagicMock(closed=False)
    client._ws.send_json = AsyncMock()
    return client


def sent(client):
    return [c.args[0] for c in client._ws.send_json.await_args_list]


def coordinator_for(client, kind=PANDA_BREATH, **others):
    return SimpleNamespace(
        panda_devices={kind: client, **others}, config_entry=SimpleNamespace(data={"serial": "PRINTER1"})
    )


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
    coordinator = coordinator_for(client)
    ids = {e.unique_id for e in platform_entities("sensor", coordinator) + platform_entities("number", coordinator)}
    assert "PRINTER1_panda_breath_chamber_temperature" in ids
    assert len(ids) == 8
    unlinked = SimpleNamespace(panda_devices={}, config_entry=SimpleNamespace(data={"serial": "X"}))
    assert platform_entities("sensor", unlinked) == [] and platform_entities("number", unlinked) == []


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
            with patch.object(panda_ws_client, "async_get_clientsession", return_value=session):
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
            with patch.object(panda_ws_client, "async_get_clientsession", return_value=session):
                return await panda_ws_client.async_test_connection(MagicMock(), "127.0.0.1:1")

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


# --- Panda PWR ---------------------------------------------------------------

def pwr_client(state=PandaPwrState(power_on=True, usb_on=False, voltage=230.0, power=95.5, energy=1.2)):
    return SimpleNamespace(
        state=state, connected=True, async_send=AsyncMock(),
        async_add_listener=MagicMock(), host="10.0.0.9", firmware_version="V1.0.2",
    )


def test_pwr_entities_read_state_and_send_commands():
    client = pwr_client()
    coordinator = coordinator_for(client, PANDA_PWR)
    sensors = {e.entity_description.key: e for e in platform_entities("sensor", coordinator)}
    assert sensors["voltage"].native_value == 230.0
    assert sensors["power"].native_value == 95.5
    assert sensors["energy"].native_value == 1.2
    assert sensors["current"].native_value is None
    assert sensors["power"].unique_id == "PRINTER1_panda_pwr_power"

    switches = {e.entity_description.key: e for e in platform_entities("switch", coordinator)}
    assert switches["power"].is_on is True
    assert switches["usb"].is_on is False
    run(switches["power"].async_turn_off())
    client.async_send.assert_awaited_with("power=0", {"power_on": False})
    run(switches["usb"].async_turn_on())
    client.async_send.assert_awaited_with("usb=1", {"usb_on": True})
    assert platform_entities("select", coordinator) == []


def test_pwr_client_against_fake_device():
    async def scenario():
        received = []

        async def ele(request):
            return web.json_response({"power_state": "0" if received else "1", "usb_state": 1,
                                      "voltage": "231.0", "current": "0.4", "power": "92", "ele": "2.5"})

        async def state(request):
            return web.json_response({"fw_version": "V1.0.3 x", "ap_ssid": "PandaPWR_1", "ap_password": "pw"})

        async def set_(request):
            received.append(await request.text())
            return web.Response(text="ok")

        app = web.Application()
        app.router.add_get("/update_ele_data", ele)
        app.router.add_get("/get_state", state)
        app.router.add_post("/set", set_)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with aiohttp.ClientSession() as session:
                with patch.object(panda_pwr_client, "async_get_clientsession", return_value=session):
                    client = PandaPwrClient(MagicMock(), f"127.0.0.1:{port}")
                    await client.async_refresh(fetch_info=True)
                    assert client.connected
                    assert client.state.power_on is True and client.state.voltage == 231.0
                    assert client.firmware_version == "V1.0.3"
                    await client.async_send("power=0", {"power_on": False})
                    assert received == ["power=0"]
                    assert client.state.power_on is False

                    assert await panda_pwr_client.async_test_pwr_connection(MagicMock(), f"127.0.0.1:{port}")
                    assert not await panda_pwr_client.async_test_pwr_connection(MagicMock(), "127.0.0.1:1")
        finally:
            await runner.cleanup()

    run(scenario())


def test_pwr_client_marks_unreachable_device_unavailable():
    async def scenario():
        async with aiohttp.ClientSession() as session:
            with patch.object(panda_pwr_client, "async_get_clientsession", return_value=session):
                client = PandaPwrClient(MagicMock(), "127.0.0.1:1")
                client._connected = True
                await client.async_refresh()
                return client.connected

    assert run(scenario()) is False


# --- Panda Status ------------------------------------------------------------

def status_client():
    client = PandaWebSocketClient(MagicMock(), "10.0.0.8", PandaStatusState(), apply_status_message, "Panda Status")
    client._ws = MagicMock(closed=False)
    client._ws.send_json = AsyncMock()
    return client


def test_status_entities():
    client = status_client()
    client.handle_text('{"settings": {"current_mode": 0, "list2": [{}, {"brightness": 0}]}, "printer": {"state": "idle"}}')
    coordinator = coordinator_for(client, PANDA_STATUS)
    light = platform_entities("switch", coordinator)[0]
    effect = platform_entities("select", coordinator)[0]
    printer = platform_entities("sensor", coordinator)[0]
    assert light.is_on is False
    assert effect.current_option == "music"
    assert printer.native_value == "idle"
    assert light.unique_id == "PRINTER1_panda_status_idle_light"

    run(light.async_turn_on())
    run(effect.async_select_option("h2d"))
    assert sent(client) == [{"settings": {"rgb_info_brightness": "100"}}, {"settings": {"rgb_info_mode": 1}}]
    assert light.is_on is True and effect.current_option == "h2d"
    with pytest.raises(ServiceValidationError):
        run(effect.async_select_option("disco"))


def test_all_three_devices_together():
    coordinator = coordinator_for(
        connected_client(), PANDA_BREATH, **{PANDA_PWR: pwr_client(), PANDA_STATUS: status_client()}
    )
    assert {e.unique_id for e in platform_entities("switch", coordinator)} == {
        "PRINTER1_panda_breath_power", "PRINTER1_panda_breath_drying",
        "PRINTER1_panda_pwr_power", "PRINTER1_panda_pwr_usb", "PRINTER1_panda_status_idle_light",
    }


def _fake_pwr_app(ele_payload, state_status=200):
    async def ele(request):
        return web.json_response(ele_payload())

    async def state(request):
        if state_status != 200:
            return web.Response(status=state_status)
        return web.json_response({"fw_version": "V1.0.3"})

    async def set_(request):
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/update_ele_data", ele)
    app.router.add_get("/get_state", state)
    app.router.add_post("/set", set_)
    return app


async def _serve(app):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    return runner, site._server.sockets[0].getsockname()[1]


def test_pwr_missing_device_info_does_not_mark_device_down():
    async def scenario():
        runner, port = await _serve(_fake_pwr_app(lambda: {"power_state": 1}, state_status=404))
        try:
            async with aiohttp.ClientSession() as session:
                with patch.object(panda_pwr_client, "async_get_clientsession", return_value=session):
                    client = PandaPwrClient(MagicMock(), f"127.0.0.1:{port}")
                    await client.async_refresh(fetch_info=True)
                    return client.connected, client.state.power_on, client.firmware_version
        finally:
            await runner.cleanup()

    assert run(scenario()) == (True, True, None)


def test_pwr_poll_started_before_a_command_is_discarded():
    async def scenario():
        release = asyncio.Event()

        async def slow_ele(request):
            await release.wait()
            return web.json_response({"power_state": 1})

        started = asyncio.Event()

        async def ele(request):
            started.set()
            return await slow_ele(request)

        async def set_(request):
            return web.Response(text="ok")

        app = web.Application()
        app.router.add_get("/update_ele_data", ele)
        app.router.add_post("/set", set_)
        runner, port = await _serve(app)
        try:
            async with aiohttp.ClientSession() as session:
                with patch.object(panda_pwr_client, "async_get_clientsession", return_value=session), \
                        patch.object(panda_pwr_client, "async_call_later", return_value=MagicMock()):
                    client = PandaPwrClient(MagicMock(), f"127.0.0.1:{port}")
                    poll = asyncio.create_task(client.async_refresh())
                    await asyncio.wait_for(started.wait(), 2)  # the poll is in flight
                    await client.async_send("power=0", {"power_on": False})
                    release.set()
                    await poll
                    return client.state.power_on, client.connected
        finally:
            await runner.cleanup()

    assert run(scenario()) == (False, True)


def test_pwr_send_after_unlink_is_refused():
    client = PandaPwrClient(MagicMock(), "127.0.0.1:1")
    run(client.async_stop())
    with pytest.raises(HomeAssistantError, match="no longer linked"):
        run(client.async_send("power=1", {"power_on": True}))
