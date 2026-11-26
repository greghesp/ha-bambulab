"""Fan overrides must reflect commands actually accepted for publication."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from pybambu.const import FansEnum
from pybambu.models import Fans


CONTROLLABLE = (
    FansEnum.PART_COOLING,
    FansEnum.AUXILIARY,
    FansEnum.CHAMBER,
    FansEnum.SECONDARY_AUXILIARY,
)


@pytest.mark.parametrize("fan", CONTROLLABLE)
def test_successful_publish_sets_override(fan):
    client = MagicMock()
    client.publish.return_value = True
    fans = Fans(client)

    assert fans.set_fan_speed(fan, 20) is True
    assert fans.get_fan_speed(fan) == 20
    client.publish.assert_called_once()
    client.callback.assert_called_once_with("event_printer_data_update")


@pytest.mark.parametrize("fan", CONTROLLABLE)
def test_failed_publish_preserves_previous_override(fan):
    client = MagicMock()
    client.publish.return_value = True
    fans = Fans(client)
    fans.set_fan_speed(fan, 20)
    client.reset_mock()
    client.publish.return_value = False

    assert fans.set_fan_speed(fan, 80) is False
    assert fans.get_fan_speed(fan) == 20
    client.callback.assert_not_called()


def test_part_cooling_returns_to_printer_telemetry_after_override_expires():
    client = MagicMock()
    client.publish.return_value = True
    fans = Fans(client)
    fans.print_update({"cooling_fan_speed": "0"})
    fans.set_fan_speed(FansEnum.PART_COOLING, 20)
    assert fans.get_fan_speed(FansEnum.PART_COOLING) == 20

    fans._cooling_fan_speed_override_time = datetime.now() - timedelta(seconds=6)
    fans.print_update({"cooling_fan_speed": "0"})
    assert fans.get_fan_speed(FansEnum.PART_COOLING) == 0


# airduct modes as reported by a P2S with the left auxiliary fan fitted.
# The printer keeps that fan (part 160) off in heating mode.
P2S_AIRDUCT = {
    "modeCur": 0,
    "modeList": [
        {"ctrl": [16, 32, 160, 48], "modeId": 0, "off": []},
        {"ctrl": [16, 32, 48], "modeId": 1, "off": [160]},
    ],
    "parts": [
        {"func": 0, "id": 16, "range": 6553600, "state": 100},
        {"func": 6, "id": 32, "range": 6553600, "state": 90},
        {"func": 5, "id": 160, "range": 6553600, "state": 100},
    ],
}


def p2s_fans(mode):
    client = MagicMock()
    client.publish.return_value = True
    fans = Fans(client)
    fans.print_update({"device": {"airduct": {**P2S_AIRDUCT, "modeCur": mode}}})
    return fans, client


def test_secondary_aux_fan_recovers_when_the_printer_ignores_the_command():
    fans, client = p2s_fans(mode=0)

    assert fans.set_fan_speed(FansEnum.SECONDARY_AUXILIARY, 0) is True
    assert client.publish.call_args[0][0]["print"]["param"] == "M106 P10 S0\n"
    assert fans.get_fan_speed(FansEnum.SECONDARY_AUXILIARY) == 0

    fans._secondary_aux_fan_speed_override_time = datetime.now() - timedelta(seconds=6)
    fans.print_update({})
    assert fans.get_fan_speed(FansEnum.SECONDARY_AUXILIARY) == 100


def test_secondary_aux_fan_is_not_turned_on_when_the_airduct_mode_locks_it_off():
    fans, client = p2s_fans(mode=1)

    assert fans.secondary_aux_fan_locked_off is True
    assert fans.set_fan_speed(FansEnum.SECONDARY_AUXILIARY, 50) is False
    client.publish.assert_not_called()
    assert fans._secondary_aux_fan_speed_override_time is None


def test_secondary_aux_fan_can_be_turned_off_when_locked_off():
    fans, client = p2s_fans(mode=1)

    assert fans.set_fan_speed(FansEnum.SECONDARY_AUXILIARY, 0) is True
    client.publish.assert_called_once()


def test_secondary_aux_fan_unlocks_when_the_airduct_mode_changes():
    fans, _ = p2s_fans(mode=1)

    fans.print_update({"device": {"airduct": {"modeCur": 0}}})

    assert fans.secondary_aux_fan_locked_off is False
    assert fans.set_fan_speed(FansEnum.SECONDARY_AUXILIARY, 50) is True


@pytest.mark.parametrize("fan", (FansEnum.PART_COOLING, FansEnum.AUXILIARY, FansEnum.CHAMBER))
def test_other_fans_are_unaffected_by_the_secondary_aux_lock(fan):
    fans, client = p2s_fans(mode=1)

    assert fans.set_fan_speed(fan, 50) is True
    client.publish.assert_called_once()


def test_secondary_aux_fan_is_controllable_without_airduct_data():
    client = MagicMock()
    client.publish.return_value = True

    assert Fans(client).secondary_aux_fan_locked_off is False
