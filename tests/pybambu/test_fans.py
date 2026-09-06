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
    client.get_device().print_fun.mqtt_signature_required = False
    client.publish.return_value = True
    fans = Fans(client)

    assert fans.set_fan_speed(fan, 20) is True
    assert fans.get_fan_speed(fan) == 20
    client.publish.assert_called_once()
    client.callback.assert_called_once_with("event_printer_data_update")


@pytest.mark.parametrize("fan", CONTROLLABLE)
def test_failed_publish_preserves_previous_override(fan):
    client = MagicMock()
    client.get_device().print_fun.mqtt_signature_required = False
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
    client.get_device().print_fun.mqtt_signature_required = False
    client.publish.return_value = True
    fans = Fans(client)
    fans.print_update({"cooling_fan_speed": "0"})
    fans.set_fan_speed(FansEnum.PART_COOLING, 20)
    assert fans.get_fan_speed(FansEnum.PART_COOLING) == 20

    fans._cooling_fan_speed_override_time = datetime.now() - timedelta(seconds=6)
    fans.print_update({"cooling_fan_speed": "0"})
    assert fans.get_fan_speed(FansEnum.PART_COOLING) == 0
