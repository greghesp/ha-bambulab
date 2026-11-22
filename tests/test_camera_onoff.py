"""Chamber camera power switch.

P1/A1 printers push the chamber image over their own socket instead of serving
it on demand, and the integration opens that socket as soon as the printer
connects - it keeps running whether or not anyone is watching. These tests
cover the on/off switch that stops and restarts it.

Optional entity checks: run in a Home Assistant Python environment.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.camera import CameraEntityFeature

from custom_components.bambu_lab.camera import BambuLabImageCamera

FRAME = b"\xff\xd8frame"


class _Executor:
    """Stand-in for HomeAssistant that runs the job inline and awaits like HA."""

    async def async_add_executor_job(self, job, *args):
        return job(*args)


def make_camera(enabled: bool = True) -> tuple[BambuLabImageCamera, MagicMock]:
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.client.camera_enabled = enabled
    coordinator.get_model().chamber_image.get_image.return_value = FRAME
    camera = BambuLabImageCamera(
        coordinator, SimpleNamespace(data={"serial": "TESTSERIAL"})
    )
    camera.hass = _Executor()
    camera.async_write_ha_state = MagicMock()
    return camera, coordinator


def test_camera_advertises_on_off():
    camera, _ = make_camera()
    assert camera.supported_features & CameraEntityFeature.ON_OFF


def test_enabled_camera_serves_the_latest_frame():
    camera, _ = make_camera(enabled=True)
    assert camera.camera_image() == FRAME
    assert camera.is_streaming


def test_disabled_camera_does_not_serve_a_stale_frame():
    camera, _ = make_camera(enabled=False)
    assert camera.camera_image() is None
    assert not camera.is_streaming


def test_turn_off_stops_the_chamber_image_thread():
    camera, coordinator = make_camera(enabled=True)
    asyncio.run(camera.async_turn_off())
    coordinator.client.set_camera_enabled.assert_called_once_with(False)
    camera.async_write_ha_state.assert_called_once()


def test_turn_on_starts_the_chamber_image_thread():
    camera, coordinator = make_camera(enabled=False)
    asyncio.run(camera.async_turn_on())
    coordinator.client.set_camera_enabled.assert_called_once_with(True)
    camera.async_write_ha_state.assert_called_once()
