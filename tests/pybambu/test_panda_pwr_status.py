"""Tests for the BIQU Panda PWR and Panda Status protocol helpers.

Both modules have no Home Assistant imports, so they run in the lightweight suite.
"""
import pytest

from panda_pwr import PandaPwrState, build_power, build_usb, parse_device_info, parse_ele_data
from panda_status import (
    EFFECT_MODES,
    PandaStatusState,
    apply_status_message,
    build_effect_mode,
    build_idle_light,
)

# --- Panda PWR ---------------------------------------------------------------


def test_parse_ele_data_converts_text_numbers():
    state = parse_ele_data({
        "power_state": "1", "usb_state": 0, "voltage": "230.4", "current": "0.52",
        "power": 119.8, "ele": "3.25",
    })
    assert state == PandaPwrState(
        power_on=True, usb_on=False, voltage=230.4, current=0.52, power=119.8, energy=3.25,
    )


def test_parse_ele_data_tolerates_missing_and_bad_values():
    state = parse_ele_data({"power_state": "x", "voltage": "NaN", "ele": None})
    assert state == PandaPwrState()


@pytest.mark.parametrize("raw", [None, [], "text", 3])
def test_parse_ele_data_rejects_non_objects(raw):
    with pytest.raises(ValueError):
        parse_ele_data(raw)


def test_parse_device_info_trims_firmware_and_never_keeps_secrets():
    info = parse_device_info({"fw_version": "V1.0.2 build 20250101", "ap_ssid": "PandaPWR_A1B2", "ap_password": "secret"})
    assert info == {"firmware_version": "V1.0.2", "ap_ssid": "PandaPWR_A1B2"}
    assert parse_device_info("junk") == {}


def test_pwr_commands():
    assert build_power(True) == "power=1"
    assert build_power(False) == "power=0"
    assert build_usb(True) == "usb=1"
    assert build_usb(False) == "usb=0"


# --- Panda Status ------------------------------------------------------------

EMPTY = PandaStatusState()


def test_status_reads_idle_light_effect_and_printer():
    state = apply_status_message(EMPTY, {
        "settings": {"current_mode": 1, "list2": [{"brightness": 50}, {"brightness": 80}]},
        "printer": {"state": "printing", "sn": "01P00A000000000", "name": "P1S"},
    })
    assert state.idle_light_on is True
    assert state.effect_mode == "h2d"
    assert state.printer_state == "printing"
    assert state.bound_printer_serial == "01P00A000000000"


def test_status_idle_light_off_and_unknown_mode():
    state = apply_status_message(EMPTY, {"settings": {"current_mode": 7, "list2": [{}, {"brightness": 0}]}})
    assert state.idle_light_on is False
    assert state.effect_mode is None


def test_status_ignores_malformed_messages():
    assert apply_status_message(EMPTY, {"settings": {"list2": "nope"}}) == EMPTY
    assert apply_status_message(EMPTY, {"settings": "nope", "printer": 5}) == EMPTY
    assert apply_status_message(EMPTY, {"settings": {"list2": [{"brightness": 10}]}}) == EMPTY


def test_status_commands_and_optimistic_apply():
    assert build_idle_light(True) == [{"settings": {"rgb_info_brightness": "100"}}]
    assert build_idle_light(False) == [{"settings": {"rgb_info_brightness": "0"}}]
    assert build_effect_mode("music") == [{"settings": {"rgb_info_mode": 0}}]
    with pytest.raises(ValueError):
        build_effect_mode("disco")

    state = EMPTY
    for message in build_idle_light(True) + build_effect_mode("h2d"):
        state = apply_status_message(state, message)
    assert state.idle_light_on is True
    assert state.effect_mode == "h2d"
    assert set(EFFECT_MODES.values()) == {"music", "h2d"}
