"""Optional checks for the external AMS heater controller and its entities.

Like test_fan_entity.py, these need Home Assistant installed and skip without it.
They make no real service call or MQTT connection.
"""
import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.bambu_lab.ams_heater_controller import AmsHeaterController, async_setup_ams_heaters
from custom_components.bambu_lab.number import AMS_HEATER_NUMBERS, AmsHeaterNumber

PLUG = "switch.sunlu_plug"
SERIAL = "AMS0001"


def make_controller(humidity=50, temperature=35, plug_state="off", on_since_hours=0.0, online=True):
    ams = SimpleNamespace(serial=SERIAL, humidity=humidity, temperature=temperature)
    coordinator = MagicMock()
    model = coordinator.get_model.return_value
    model.ams.data = {0: ams}
    model.supports_feature.return_value = True
    model.info.online = online

    hass = MagicMock()
    state = SimpleNamespace(
        state=plug_state,
        last_changed=dt_util.utcnow() - timedelta(hours=on_since_hours),
    )
    hass.states.get.side_effect = lambda entity_id: state if entity_id == PLUG else None
    hass.services.async_call = AsyncMock()

    controller = AmsHeaterController(hass, coordinator, SERIAL, PLUG)
    controller._running = True  # as after async_start(), without real HA timers
    return controller, hass, state


def service_calls(hass):
    return [(c.args[0], c.args[1], c.args[2]) for c in hass.services.async_call.await_args_list]


def run(coro):
    return asyncio.run(coro)


def test_drying_off_never_touches_plug():
    controller, hass, _ = make_controller(humidity=80)
    run(controller.async_evaluate())
    hass.services.async_call.assert_not_awaited()


def test_turning_drying_mode_off_switches_heater_off():
    controller, hass, state = make_controller(humidity=55)
    run(controller.async_update_settings(drying_enabled=True))
    state.state = "on"
    run(controller.async_update_settings(drying_enabled=False))
    assert service_calls(hass)[-1] == ("switch", "turn_off", {"entity_id": PLUG})


def test_humid_ams_turns_plug_on():
    controller, hass, _ = make_controller(humidity=55)
    run(controller.async_update_settings(drying_enabled=True))
    assert service_calls(hass) == [("switch", "turn_on", {"entity_id": PLUG})]
    assert controller.last_reason == "humid"


def test_plug_already_in_desired_state_is_left_alone():
    controller, hass, _ = make_controller(humidity=55, plug_state="on")
    run(controller.async_update_settings(drying_enabled=True))
    hass.services.async_call.assert_not_awaited()


def test_same_command_is_not_resent_while_plug_catches_up():
    controller, hass, _ = make_controller(humidity=55)
    run(controller.async_update_settings(drying_enabled=True))
    run(controller.async_evaluate())
    assert len(service_calls(hass)) == 1


def test_dry_ams_turns_plug_off():
    controller, hass, _ = make_controller(humidity=20, plug_state="on")
    run(controller.async_update_settings(drying_enabled=True))
    assert service_calls(hass) == [("switch", "turn_off", {"entity_id": PLUG})]


def test_unknown_ams_turns_plug_off():
    controller, hass, _ = make_controller(humidity=55, plug_state="on")
    controller.coordinator.get_model.return_value.ams.data = {}
    run(controller.async_update_settings(drying_enabled=True))
    assert controller.last_reason == "no_humidity"
    assert service_calls(hass) == [("switch", "turn_off", {"entity_id": PLUG})]


def test_unavailable_plug_is_not_called():
    controller, hass, state = make_controller(humidity=55)
    state.state = "unavailable"
    run(controller.async_update_settings(drying_enabled=True))
    hass.services.async_call.assert_not_awaited()


def test_max_runtime_locks_out_until_drying_mode_is_reenabled():
    controller, hass, state = make_controller(humidity=55, plug_state="on", on_since_hours=13)
    run(controller.async_update_settings(drying_enabled=True))
    assert controller.locked_out
    assert service_calls(hass) == [("switch", "turn_off", {"entity_id": PLUG})]

    # Plug reports off, AMS still humid: stays off.
    state.state = "off"
    controller._last_command_time = None
    run(controller.async_evaluate())
    assert len(service_calls(hass)) == 1

    run(controller.async_update_settings(drying_enabled=True))
    assert not controller.locked_out
    assert service_calls(hass)[-1] == ("switch", "turn_on", {"entity_id": PLUG})


def test_setup_skips_blank_entries():
    hass = MagicMock()
    entry = MagicMock()
    entry.options = {"ams_heaters": {SERIAL: PLUG, "AMS0002": "", "": "switch.x"}}
    controllers = async_setup_ams_heaters(hass, entry, MagicMock())
    assert list(controllers) == [SERIAL]


def _number(controller, key):
    description = next(d for d in AMS_HEATER_NUMBERS if d.key == key)
    entity = AmsHeaterNumber(MagicMock(), controller, 0, description)
    entity.async_write_ha_state = MagicMock()
    return entity


def test_turn_on_threshold_must_stay_above_turn_off_threshold():
    controller, _, _ = make_controller()
    with pytest.raises(ServiceValidationError):
        run(_number(controller, "ams_heater_humidity_on").async_set_native_value(20))
    with pytest.raises(ServiceValidationError):
        run(_number(controller, "ams_heater_humidity_off").async_set_native_value(45))


def test_number_updates_controller_setting():
    controller, _, _ = make_controller()
    run(_number(controller, "ams_heater_max_temperature").async_set_native_value(55))
    assert controller.settings.max_temperature == 55


def test_stop_switches_heater_off_while_drying():
    controller, hass, state = make_controller(humidity=55, plug_state="on")
    run(controller.async_update_settings(drying_enabled=True))
    hass.async_create_task.side_effect = lambda coro: run(coro)
    controller.async_stop()
    assert service_calls(hass)[-1] == ("switch", "turn_off", {"entity_id": PLUG})


def test_stop_leaves_manually_controlled_plug_alone():
    controller, hass, _ = make_controller(humidity=55, plug_state="on")
    hass.async_create_task.side_effect = lambda coro: run(coro)
    controller.async_stop()
    hass.services.async_call.assert_not_awaited()


def test_stopped_controller_does_not_evaluate():
    controller, hass, _ = make_controller(humidity=55)
    run(controller.async_update_settings(drying_enabled=True))
    hass.services.async_call.reset_mock()
    controller._running = False
    controller._last_command_time = None
    run(controller.async_evaluate())
    hass.services.async_call.assert_not_awaited()
