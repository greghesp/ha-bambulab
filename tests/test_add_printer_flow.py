"""Optional add-printer flow checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant, so these
tests skip when it is absent.

The cloud's device list has three distinct outcomes the flow has to keep apart:
printers, an empty list (nothing bound to the account) and a failed request.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import config_flow
from custom_components.bambu_lab.config_flow import BambuLabFlowHandler
from custom_components.bambu_lab.const import ENTRY_TYPE, ENTRY_TYPE_MAKERWORLD

PRINTER = {
    "dev_id": "SERIAL1",
    "name": "X1C",
    "dev_product_name": "X1 Carbon",
    "dev_access_code": "12345678",
}


class FakeCloud:
    """Answers the device list for whichever token was last set on it."""

    device_lists: dict = {}

    def __init__(self, region, email, username, auth_token):
        self.username = username
        self.auth_token = auth_token

    def test_authentication(self, region, email, username, auth_token):
        self.username = username
        self.auth_token = auth_token
        return self.get_device_list() is not None

    def get_device_list(self):
        return self.device_lists.get(self.auth_token)


def _entry(email, token):
    return SimpleNamespace(
        entry_id=f"entry_{token}",
        data={"serial": token},
        options={
            "region": "Europe",
            "email": email,
            "username": f"u_{token}",
            "auth_token": token,
        },
    )


def _makerworld_entry(username):
    return SimpleNamespace(
        entry_id="makerworld",
        data={ENTRY_TYPE: ENTRY_TYPE_MAKERWORLD, "username": username},
        options={},
    )


@pytest.fixture
def make_flow(monkeypatch):
    def _make(device_lists, entries=(), registered=()):
        monkeypatch.setattr(FakeCloud, "device_lists", device_lists)
        monkeypatch.setattr(config_flow, "BambuCloud", FakeCloud)
        monkeypatch.setattr(
            config_flow,
            "_async_get_printer_device",
            lambda hass, serial: MagicMock() if serial in registered else None,
        )

        async def run_in_executor(func, *args):
            return func(*args)

        flow = BambuLabFlowHandler()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = run_in_executor
        flow.hass.config_entries.async_entries.return_value = list(entries)
        return flow

    return _make


def _logged_in(flow, token):
    flow._bambu_cloud = FakeCloud("Europe", "user@example.com", "u_1", token)
    return flow


def _serials(result):
    schema = result["data_schema"].schema
    selector = next(value for key, value in schema.items() if str(key) == "serial")
    return [option["value"] for option in selector.config["options"]]


def _modes(result):
    selector = next(iter(result["data_schema"].schema.values()))
    return [option["value"] for option in selector.config["options"]]


def _choose_saved_account(flow):
    async def run():
        form = await flow.async_step_user(None)
        return form, await flow.async_step_user({"printer_mode": flow.email})

    return asyncio.run(run())


def test_account_without_printers_aborts_with_no_printers(make_flow):
    flow = _logged_in(make_flow({"token": []}), "token")

    result = asyncio.run(flow.async_step_Bambu_Choose_Device(None))

    assert result["reason"] == "no_printers"


def test_registered_printer_is_still_offered_when_it_is_the_only_one(make_flow):
    flow = _logged_in(make_flow({"token": [PRINTER]}, registered=["SERIAL1"]), "token")

    result = asyncio.run(flow.async_step_Bambu_Choose_Device(None))

    assert _serials(result) == ["SERIAL1"]


def test_failed_device_list_aborts_instead_of_crashing(make_flow):
    flow = _logged_in(make_flow({"token": None}), "token")

    result = asyncio.run(flow.async_step_Bambu_Choose_Device(None))

    assert result["reason"] == "device_list_failed"


def test_device_list_failing_after_printer_choice_aborts(make_flow):
    flow = _logged_in(make_flow({"token": None}), "token")

    result = asyncio.run(flow.async_step_Bambu_Choose_Device({"serial": "SERIAL1"}))

    assert result["reason"] == "device_list_failed"


def test_saved_account_survives_a_later_entry_with_an_expired_token(make_flow):
    flow = make_flow(
        {"good": [PRINTER], "expired": None},
        entries=[_entry("good@example.com", "good"), _entry("old@example.com", "expired")],
    )

    _, result = _choose_saved_account(flow)

    assert flow.email == "good@example.com"
    assert flow._bambu_cloud.auth_token == "good"
    assert _serials(result) == ["SERIAL1"]


def test_saved_account_is_used_when_an_earlier_entry_has_an_expired_token(make_flow):
    flow = make_flow(
        {"good": [PRINTER], "expired": None},
        entries=[_entry("old@example.com", "expired"), _entry("good@example.com", "good")],
    )

    _, result = _choose_saved_account(flow)

    assert flow._bambu_cloud.auth_token == "good"
    assert _serials(result) == ["SERIAL1"]


def test_first_working_account_is_offered_and_every_account_reaches_makerworld(make_flow):
    flow = make_flow(
        {"one": [PRINTER], "two": []},
        entries=[_entry("one@example.com", "one"), _entry("two@example.com", "two")],
    )

    form, result = _choose_saved_account(flow)

    assert "one@example.com" in _modes(form)
    assert flow._bambu_cloud.auth_token == "one"
    assert set(flow._makerworld_credentials) == {"u_one", "u_two"}
    assert _serials(result) == ["SERIAL1"]


def test_account_already_set_up_for_makerworld_is_not_offered_again(make_flow):
    flow = make_flow(
        {"one": [PRINTER]},
        entries=[_makerworld_entry("u_one"), _entry("one@example.com", "one")],
    )

    form, _ = _choose_saved_account(flow)

    assert flow._makerworld_credentials == {}
    assert "makerworld" not in _modes(form)
    assert flow._bambu_cloud.auth_token == "one"


def test_no_working_saved_account_offers_only_login_and_lan(make_flow):
    flow = make_flow({"expired": None}, entries=[_entry("old@example.com", "expired")])

    form = asyncio.run(flow.async_step_user(None))

    assert _modes(form) == ["bambu", "lan"]
