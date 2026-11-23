"""Start Time sensor survives a Home Assistant restart mid-print (issue #972)."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.helpers.restore_state import RestoredExtraData

from custom_components.bambu_lab.definitions import PRINTER_SENSORS
from custom_components.bambu_lab.sensor import BambuLabRestoreSensor, BambuLabSensor

START = datetime(2026, 11, 16, 9, 30, tzinfo=timezone.utc)
DESCRIPTION = next(sensor for sensor in PRINTER_SENSORS if sensor.key == "start_time")


def make_job(start_time=None, task_id="488489869", gcode_file="Box.3mf", subtask_name="Box"):
    return SimpleNamespace(start_time=start_time, task_id=task_id, gcode_file=gcode_file,
                           subtask_name=subtask_name, gcode_state="RUNNING")


def make_sensor(job):
    coordinator = MagicMock()
    coordinator.get_model().print_job = job
    coordinator.get_model().info.serial = "PRINTER"
    return BambuLabRestoreSensor(coordinator, DESCRIPTION)


def restart(sensor_before, job_after):
    """Simulate HA saving state, restarting, and re-adding the entity."""
    saved = sensor_before.extra_restore_state_data
    sensor = make_sensor(job_after)
    with patch.object(BambuLabSensor, "async_added_to_hass", AsyncMock()), \
         patch.object(BambuLabRestoreSensor, "async_get_last_extra_data", AsyncMock(return_value=saved)):
        asyncio.run(sensor.async_added_to_hass())
    return sensor


def test_start_time_sensor_is_restoring():
    assert DESCRIPTION.is_restoring


def test_live_start_time_is_reported():
    sensor = make_sensor(make_job(start_time=START))
    assert sensor.native_value == START


def test_start_time_restored_after_restart_on_same_print():
    job_after = make_job()
    sensor = restart(make_sensor(make_job(start_time=START)), job_after)

    assert sensor.native_value == START
    # Injected back into pybambu so usage hours are counted at print end.
    assert job_after.start_time == START


def test_start_time_not_restored_when_a_different_print_is_running():
    job_after = make_job(task_id="999", gcode_file="Other.3mf", subtask_name="Other")
    sensor = restart(make_sensor(make_job(start_time=START)), job_after)

    assert sensor.native_value is None
    assert job_after.start_time is None
    # The stale value is discarded, not applied once the printer changes job again.
    job_after.task_id, job_after.gcode_file, job_after.subtask_name = "488489869", "Box.3mf", "Box"
    assert sensor.native_value is None


def test_start_time_restored_once_printer_reports_the_job():
    job_after = make_job(task_id="", gcode_file="", subtask_name=None)
    sensor = restart(make_sensor(make_job(start_time=START)), job_after)

    assert sensor.native_value is None
    job_after.task_id, job_after.gcode_file, job_after.subtask_name = "488489869", "Box.3mf", "Box"
    assert sensor.native_value == START


def test_restore_works_in_lan_mode_without_end_time():
    """The earlier fix also required an end time and LAN mode; neither is needed."""
    job_after = make_job()
    job_after.end_time = None
    sensor = restart(make_sensor(make_job(start_time=START)), job_after)
    sensor.coordinator.get_model().info.mqtt_mode = "bambu_cloud"

    assert sensor.native_value == START


def test_future_start_time_is_rejected():
    future = datetime.now(timezone.utc) + timedelta(days=1)
    sensor = restart(make_sensor(make_job(start_time=future)), make_job())
    assert sensor.native_value is None


def test_nothing_saved_without_start_time_or_job():
    assert make_sensor(make_job()).extra_restore_state_data is None
    no_job = make_job(start_time=START, task_id="", gcode_file="", subtask_name=None)
    assert make_sensor(no_job).extra_restore_state_data is None


def test_saved_data_is_serialisable_round_trip():
    saved = make_sensor(make_job(start_time=START)).extra_restore_state_data
    assert isinstance(saved, RestoredExtraData)
    assert saved.as_dict() == {"start_time": START.isoformat(), "job_key": "488489869|Box.3mf|Box"}


@pytest.mark.parametrize("saved", [
    None,
    RestoredExtraData({}),
    RestoredExtraData({"start_time": "garbage", "job_key": "488489869|Box.3mf|Box"}),
    RestoredExtraData({"start_time": "2026-11-16T09:30:00", "job_key": "488489869|Box.3mf|Box"}),
    RestoredExtraData({"start_time": START.isoformat(), "job_key": ""}),
])
def test_unusable_saved_data_is_ignored(saved):
    sensor = make_sensor(make_job())
    with patch.object(BambuLabSensor, "async_added_to_hass", AsyncMock()), \
         patch.object(BambuLabRestoreSensor, "async_get_last_extra_data", AsyncMock(return_value=saved)):
        asyncio.run(sensor.async_added_to_hass())
    assert sensor.native_value is None
