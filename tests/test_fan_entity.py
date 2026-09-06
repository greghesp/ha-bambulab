"""Optional entity checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant. These tests
skip when it is absent and make no service call or MQTT connection.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import HomeAssistantError
from custom_components.bambu_lab.fan import BambuLabFan, FANS
from custom_components.bambu_lab.pybambu.const import FansEnum


@pytest.fixture
def fan():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.get_model().fans.set_fan_speed.return_value = True
    return BambuLabFan(coordinator, FANS[2], SimpleNamespace(data={"serial": "TESTSERIAL"}))


@pytest.mark.parametrize("percentage", [0, 20, 100])
def test_turn_on_preserves_percentage(fan, percentage):
    fan.turn_on(percentage=percentage)
    fan.coordinator.get_model().fans.set_fan_speed.assert_called_once_with(FansEnum.CHAMBER, percentage)


def test_turn_on_without_percentage_defaults_to_full_speed(fan):
    fan.turn_on()
    fan.coordinator.get_model().fans.set_fan_speed.assert_called_once_with(FansEnum.CHAMBER, 100)


def test_failed_publish_raises_service_error(fan):
    fan.coordinator.get_model().fans.set_fan_speed.return_value = False
    with pytest.raises(HomeAssistantError, match="could not be published"):
        fan.set_percentage(20)


def test_turn_off_requests_zero(fan):
    fan.turn_off()
    fan.coordinator.get_model().fans.set_fan_speed.assert_called_once_with(FansEnum.CHAMBER, 0)
