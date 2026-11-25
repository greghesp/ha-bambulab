"""Optional checks for the clear_file_cache service (#1585).

Run in a Home Assistant Python environment; they skip when it is absent. No MQTT
connection is made.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.core import Event
from custom_components.bambu_lab.const import (
    DOMAIN,
    SERVICE_CALL_EVENT,
    SERVICE_CALL_FUTURES,
    SERVICE_CALL_ID,
)
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator


def test_cache_directory_uses_config_serial_not_reported_model_serial(tmp_path):
    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._entry = SimpleNamespace(data={"serial": "configured-serial"})
    coordinator._hass = SimpleNamespace(
        config=SimpleNamespace(
            media_dirs={"local": str(tmp_path / "media")},
            config_dir=str(tmp_path / "config"),
        )
    )
    coordinator.get_model = lambda: SimpleNamespace(
        info=SimpleNamespace(serial="reported-serial")
    )

    cache_dir = coordinator.get_file_cache_directory()

    assert cache_dir == str(tmp_path / "media" / "ha-bambulab" / "configured-serial")


def _coordinator():
    print_job = SimpleNamespace(
        async_clear_print_history_files=AsyncMock(),
        async_clear_timelapse_files=AsyncMock(),
    )
    model = SimpleNamespace(print_job=print_job, print_fun=SimpleNamespace(mqtt_signature_required=True))
    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._is_service_call_for_me = lambda data: True
    coordinator.get_model = lambda: model
    coordinator._run_service_call = MagicMock(side_effect=AssertionError("must not use the MQTT path"))
    coordinator.delete_cached_file = AsyncMock(return_value={"success": True})
    return coordinator, print_job


def _call(coordinator, data, service="clear_file_cache"):
    async def run():
        future = asyncio.get_running_loop().create_future()
        coordinator._hass = SimpleNamespace(data={DOMAIN: {SERVICE_CALL_FUTURES: {"id": future}}})
        await coordinator._handle_service_call_event(
            Event(
                SERVICE_CALL_EVENT, {"service": service, SERVICE_CALL_ID: "id", **data}
            )
        )
        return future.result()

    return asyncio.run(run())


@pytest.mark.parametrize(
    ("file_type", "prints_cleared", "timelapses_cleared"),
    [(None, True, True), ("all", True, True), ("prints", True, False), ("timelapse", False, True)],
)
def test_clears_the_requested_cache(file_type, prints_cleared, timelapses_cleared):
    coordinator, print_job = _coordinator()
    data = {} if file_type is None else {"file_type": file_type}

    # The printer requires signed MQTT here, which blocks control actions but not a local cleanup.
    assert _call(coordinator, data) is True

    assert print_job.async_clear_print_history_files.await_count == int(prints_cleared)
    assert print_job.async_clear_timelapse_files.await_count == int(timelapses_cleared)


def test_rejects_an_unknown_file_type():
    coordinator, print_job = _coordinator()

    assert _call(coordinator, {"file_type": "everything"}) is False

    print_job.async_clear_print_history_files.assert_not_awaited()
    print_job.async_clear_timelapse_files.assert_not_awaited()


def test_delete_cached_file_service_uses_local_delete_path():
    coordinator, print_job = _coordinator()
    path = "timelapse/video.mp4"

    assert _call(coordinator, {"path": path}, service="delete_cached_file") is True

    coordinator.delete_cached_file.assert_awaited_once_with(path)
    print_job.async_clear_print_history_files.assert_not_awaited()
    print_job.async_clear_timelapse_files.assert_not_awaited()


def test_delete_cached_file_service_requires_a_path():
    coordinator, _ = _coordinator()

    assert _call(coordinator, {}, service="delete_cached_file") is False

    coordinator.delete_cached_file.assert_not_awaited()
