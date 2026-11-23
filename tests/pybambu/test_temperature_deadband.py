"""Idle temperature noise must not flood Home Assistant with state changes (#2228)."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from pybambu.models import Temperature, IDLE_TEMP_REFRESH


def make_temperature() -> Temperature:
    client = MagicMock()
    client._device.supports_feature.return_value = False
    return Temperature(client)


def idle_payload(nozzle, bed=22, chamber=22):
    return {
        "nozzle_temper": nozzle,
        "nozzle_target_temper": 0,
        "bed_temper": bed,
        "bed_target_temper": 0,
        "chamber_temper": chamber,
    }


def test_first_reading_is_always_reported():
    temp = make_temperature()

    assert temp.print_update(idle_payload(24)) is True
    assert temp.nozzle_temps[0] == 24


def test_idle_one_degree_jitter_is_suppressed():
    temp = make_temperature()
    temp.print_update(idle_payload(24, bed=22, chamber=23))

    for nozzle, bed, chamber in [(25, 23, 24), (24, 22, 23), (23, 21, 22), (24, 22, 23)]:
        assert temp.print_update(idle_payload(nozzle, bed, chamber)) is False

    assert temp.nozzle_temps[0] == 24
    assert temp.bed_temp == 22
    assert temp.chamber_temp == 23


def test_idle_change_of_two_degrees_is_reported():
    temp = make_temperature()
    temp.print_update(idle_payload(24))

    assert temp.print_update(idle_payload(26)) is True
    assert temp.nozzle_temps[0] == 26


def test_idle_small_drift_is_reported_after_refresh_interval():
    temp = make_temperature()
    temp.print_update(idle_payload(24))
    temp._temp_reported_at["nozzle_0"] = datetime.now() - IDLE_TEMP_REFRESH - timedelta(seconds=1)

    assert temp.print_update(idle_payload(25)) is True
    assert temp.nozzle_temps[0] == 25


def test_full_resolution_while_heating():
    temp = make_temperature()
    temp.print_update(idle_payload(24))

    heating = {**idle_payload(25), "nozzle_target_temper": 220}
    assert temp.print_update(heating) is True
    assert temp.nozzle_temps[0] == 25
    assert temp.target_nozzle_temps[0] == 220

    heating = {**idle_payload(26, bed=23), "bed_target_temper": 60}
    assert temp.print_update(heating) is True
    assert temp.bed_temp == 23


def test_packed_device_payload_is_also_debounced():
    temp = make_temperature()
    temp.print_update({"device": {"extruder": {"info": [{"id": 0, "temp": 24}]},
                                  "ctc": {"info": {"temp": 23}}}})

    changed = temp.print_update({"device": {"extruder": {"info": [{"id": 0, "temp": 25}]},
                                            "ctc": {"info": {"temp": 22}}}})

    assert changed is False
    assert temp.nozzle_temps[0] == 24
    assert temp.chamber_temp == 23
