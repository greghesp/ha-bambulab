"""Optional cloud login form checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant, so these
tests skip when it is absent.

An account with 2FA starts in the tfaCode form. "Request a new code" sends an
email/SMS login code, which only the code login endpoint accepts, so the form
has to switch to that login.

The first form accepts a blank password, for accounts made with Google, Apple
or Facebook that have none. Those log in with a code too.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

import voluptuous as vol

from custom_components.bambu_lab.config_flow import (
    BambuLabFlowHandler,
    BambuOptionsFlowHandler,
)
from custom_components.bambu_lab.const import LOGGER
from custom_components.bambu_lab.pybambu.bambu_cloud import (
    CodeIncorrectError,
    CodeRequiredError,
    IncorrectPasswordError,
)

EN = json.loads(
    (Path(__file__).parent.parent / "custom_components/bambu_lab/translations/en.json")
    .read_text(encoding="utf-8")
)
LOGIN = {"region": "Europe", "email": "user@example.com"}
FLOWS = [BambuLabFlowHandler, BambuOptionsFlowHandler]


def _flow(cls, cloud):
    flow = object.__new__(cls)
    # __del__ restores this level; __init__ is skipped to avoid building a real client.
    setattr(flow, f"_{cls.__name__}__logging_level", LOGGER.level)

    async def run_in_executor(func, *args):
        return func(*args)

    flow.hass = MagicMock()
    flow.hass.async_add_executor_job = run_in_executor
    flow._bambu_cloud = cloud
    flow.authentication_type = "tfaCode"
    flow.region = "Europe"
    flow.email = "user@example.com"
    flow.async_step_Bambu_Lan = AsyncMock(return_value="done")
    flow.async_step_Bambu_Choose_Device = AsyncMock(return_value="done")
    return flow


def _field_names(result):
    return {str(marker) for marker in result["data_schema"].schema}


@pytest.mark.parametrize("cls", FLOWS)
def test_new_code_switches_tfa_form_to_code_login(cls):
    flow = _flow(cls, MagicMock())

    result = asyncio.run(flow.async_step_Bambu({"newCode": True}))

    flow._bambu_cloud.request_new_code.assert_called_once()
    assert flow.authentication_type == "verifyCode"
    assert "verifyCode" in _field_names(result)
    assert "tfaCode" not in _field_names(result)


@pytest.mark.parametrize("cls", FLOWS)
def test_requested_code_goes_to_code_login(cls):
    flow = _flow(cls, MagicMock())

    asyncio.run(flow.async_step_Bambu({"newCode": True}))
    asyncio.run(flow.async_step_Bambu({"verifyCode": "123456"}))

    flow._bambu_cloud.login_with_verification_code.assert_called_once_with("123456")
    flow._bambu_cloud.login_with_2fa_code.assert_not_called()


@pytest.mark.parametrize("cls", FLOWS)
def test_failed_code_request_stays_in_tfa_form(cls):
    cloud = MagicMock()
    cloud.request_new_code.side_effect = PermissionError(500, "server error")
    flow = _flow(cls, cloud)

    asyncio.run(flow.async_step_Bambu({"newCode": True}))

    assert flow.authentication_type == "tfaCode"


@pytest.mark.parametrize("cls", FLOWS)
def test_wrong_tfa_code_is_shown_as_incorrect_code(cls):
    cloud = MagicMock()
    cloud.login_with_2fa_code.side_effect = CodeIncorrectError()
    flow = _flow(cls, cloud)

    result = asyncio.run(flow.async_step_Bambu({"tfaCode": "000000"}))

    assert result["errors"] == {"base": "code_incorrect"}
    assert flow.authentication_type == "tfaCode"


def _first_form(cls, cloud):
    flow = _flow(cls, cloud)
    flow.authentication_type = None
    flow._config_entry = MagicMock(options=dict(LOGIN))
    return flow


@pytest.mark.parametrize("cls", FLOWS)
def test_first_form_can_be_submitted_without_a_password(cls):
    flow = _first_form(cls, MagicMock())

    result = asyncio.run(flow.async_step_Bambu(None))

    # Home Assistant's frontend refuses to submit an empty required field.
    password = next(marker for marker in result["data_schema"].schema if str(marker) == "password")
    assert isinstance(password, vol.Optional)


@pytest.mark.parametrize("cls", FLOWS)
@pytest.mark.parametrize("user_input", [LOGIN, {**LOGIN, "password": ""}], ids=["absent", "empty"])
def test_blank_password_asks_for_the_code(cls, user_input):
    cloud = MagicMock()
    cloud.login.side_effect = CodeRequiredError()
    flow = _first_form(cls, cloud)

    result = asyncio.run(flow.async_step_Bambu(user_input))

    cloud.login.assert_called_once_with("Europe", "user@example.com", "")
    assert result["errors"] == {"base": "verifyCode"}
    assert "verifyCode" in _field_names(result)


@pytest.mark.parametrize("cls", FLOWS)
def test_incorrect_password_is_shown_as_such(cls):
    cloud = MagicMock()
    cloud.login.side_effect = IncorrectPasswordError()
    flow = _first_form(cls, cloud)

    result = asyncio.run(flow.async_step_Bambu({**LOGIN, "password": "wrong"}))

    assert result["errors"] == {"base": "incorrect_password"}
    assert "password" in _field_names(result)


@pytest.mark.parametrize("cls", FLOWS)
def test_clearing_a_rejected_password_does_not_submit_it_again(cls):
    cloud = MagicMock()
    cloud.login.side_effect = IncorrectPasswordError()
    flow = _first_form(cls, cloud)
    result = asyncio.run(flow.async_step_Bambu({**LOGIN, "password": "wrong"}))

    # The frontend leaves a cleared optional field out of what it submits.
    assert result["data_schema"](dict(LOGIN)).get("password", "") == ""


@pytest.mark.parametrize("section", ["config", "options"])
def test_blank_password_is_explained_on_the_password_field(section):
    # Not in the step description, which the code form shows too.
    assert "password" in EN[section]["step"]["Bambu"]["data_description"]


@pytest.mark.parametrize("section", ["config", "options"])
def test_incorrect_password_has_a_message(section):
    assert "incorrect_password" in EN[section]["error"]
