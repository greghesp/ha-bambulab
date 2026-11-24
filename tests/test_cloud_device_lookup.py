"""Optional cloud printer lookup checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant, so these
tests skip when it is absent.

The account in use may not own the printer being set up, for example when
another printer's account is the saved one. Its other printers must not be used.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import config_flow
from custom_components.bambu_lab.config_flow import (
    BambuLabFlowHandler,
    BambuOptionsFlowHandler,
)


def _printer(serial, name):
    return {
        "dev_id": serial,
        "name": name,
        "dev_product_name": "X1 Carbon",
        "dev_access_code": "12345678",
    }


WANTED = _printer("WANTED", "Wanted printer")
OTHER = _printer("OTHER", "Other printer")
USER_INPUT = {
    "host": "",
    "skip_local_mqtt": True,
    "access_code": "12345678",
    "print_cache_count": "100",
    "timelapse_cache_count": "1",
    "usage_hours": "0",
    "advanced": {"disable_ssl_verify": False, "enable_firmware_update": False},
}


def _add_flow():
    flow = BambuLabFlowHandler()
    flow.serial = "WANTED"
    return flow


def _options_flow():
    entry = SimpleNamespace(
        entry_id="printer",
        data={"serial": "WANTED", "device_type": "X1C"},
        options={"region": "Europe", "email": "user@example.com", "auth_token": "token"},
    )
    return BambuOptionsFlowHandler(entry)


FLOWS = pytest.mark.parametrize("build", [_add_flow, _options_flow])


@pytest.fixture
def submit(monkeypatch):
    def _submit(build, device_list):
        monkeypatch.setattr(config_flow, "BambuCloud", MagicMock())
        client = MagicMock(try_connection=AsyncMock(return_value=0))
        client.get_device.return_value.info.ip_address = "192.0.2.1"
        monkeypatch.setattr(config_flow, "BambuClient", lambda config: client)

        async def run_in_executor(func, *args):
            return func(*args)

        flow = build()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = run_in_executor
        flow.hass.config_entries.async_reload = AsyncMock()
        flow._bambu_cloud = MagicMock(username="u_1", auth_token="token")
        flow._bambu_cloud.get_device_list.return_value = device_list
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        result = asyncio.run(flow.async_step_Bambu_Lan(dict(USER_INPUT)))
        return flow, result

    return _submit


@FLOWS
@pytest.mark.parametrize("device_list", [[OTHER], []], ids=["other_printer", "empty"])
def test_printer_missing_from_the_account_aborts(submit, build, device_list):
    flow, result = submit(build, device_list)

    assert result.get("reason") == "device_not_found"
    flow.async_create_entry.assert_not_called()
    flow.hass.config_entries.async_update_entry.assert_not_called()


@FLOWS
@pytest.mark.parametrize(
    "device_list", [[WANTED, OTHER], [OTHER, WANTED]], ids=["first", "last"]
)
def test_matching_printer_is_used_whatever_its_position(submit, build, device_list):
    flow, result = submit(build, device_list)

    assert result == {"type": "create_entry"}
    if build is _add_flow:
        assert flow.async_create_entry.call_args.kwargs["title"] == "WANTED"
    else:
        update = flow.hass.config_entries.async_update_entry.call_args.kwargs
        assert update["title"] == "WANTED"
        assert update["options"]["name"] == "Wanted printer"
