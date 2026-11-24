"""Optional reconfigure flow checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant, so these
tests skip when it is absent.

Reconfiguring offers the saved account even when its login has expired, so the
cloud refusing the device list is a normal outcome there.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import config_flow
from custom_components.bambu_lab.config_flow import BambuOptionsFlowHandler

PRINTER = {"dev_id": "SERIAL1", "name": "X1C", "dev_access_code": "12345678"}
USER_INPUT = {
    "host": "",
    "skip_local_mqtt": True,
    "access_code": "12345678",
    "print_cache_count": "100",
    "timelapse_cache_count": "1",
    "usage_hours": "0",
    "advanced": {"disable_ssl_verify": False, "enable_firmware_update": False},
}


@pytest.fixture
def make_flow(monkeypatch):
    def _make(device_list):
        cloud = MagicMock(username="u_1", auth_token="token")
        cloud.get_device_list.return_value = device_list
        cloud.test_authentication.return_value = device_list is not None
        monkeypatch.setattr(config_flow, "BambuCloud", lambda *args: cloud)

        client = MagicMock(try_connection=AsyncMock(return_value=0))
        client.get_device.return_value.info.ip_address = "192.0.2.1"
        monkeypatch.setattr(config_flow, "BambuClient", lambda config: client)

        async def run_in_executor(func, *args):
            return func(*args)

        entry = SimpleNamespace(
            entry_id="printer",
            data={"serial": "SERIAL1", "device_type": "X1C"},
            options={
                "region": "Europe",
                "email": "user@example.com",
                "username": "u_1",
                "auth_token": "token",
            },
        )
        flow = BambuOptionsFlowHandler(entry)
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = run_in_executor
        flow.hass.config_entries.async_entries.return_value = [entry]
        flow._ams_heater_choices = lambda: []
        return flow

    return _make


def test_choosing_a_saved_account_with_an_expired_login_aborts(make_flow):
    flow = make_flow(None)

    async def run():
        await flow.async_step_init(None)
        return await flow.async_step_init({"printer_mode": "user@example.com"})

    assert asyncio.run(run())["reason"] == "device_list_failed"


def test_device_list_failing_on_submit_aborts_without_saving(make_flow):
    flow = make_flow(None)

    result = asyncio.run(flow.async_step_Bambu_Lan(dict(USER_INPUT)))

    assert result["reason"] == "device_list_failed"
    flow.hass.config_entries.async_update_entry.assert_not_called()


def test_working_saved_account_reaches_the_printer_form(make_flow):
    flow = make_flow([PRINTER])

    async def run():
        await flow.async_step_init(None)
        return await flow.async_step_init({"printer_mode": "user@example.com"})

    assert asyncio.run(run())["step_id"] == "Bambu_Lan"
