"""Camera feeds go unavailable when the printer is offline (issue #455).

Without this, the chamber camera keeps serving the last frame it received,
which looks like a live feed of a printer that is actually offline."""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab.camera import BambuLabImageCamera, BambuLabRtspCamera
from custom_components.bambu_lab.image import CHAMBER_IMAGE_SENSOR, ChamberImage


@pytest.fixture
def coordinator():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    model = coordinator.get_model()
    model.info.online = True
    model.info.serial = "PRINTER"
    model.info.ip_address = "192.168.1.50"
    model.camera.rtsp_url = "rtsps://192.168.1.50:322/streaming/live/1"
    return coordinator


@pytest.fixture
def config_entry():
    entry = MagicMock()
    entry.data = {"serial": "PRINTER"}
    entry.options = {"access_code": "12345678"}
    return entry


def test_image_camera_unavailable_when_printer_offline(coordinator, config_entry):
    camera = BambuLabImageCamera(coordinator, config_entry)
    assert camera.available
    assert camera.is_streaming

    coordinator.get_model().info.online = False

    assert not camera.available
    assert not camera.is_streaming


def test_rtsp_camera_unavailable_when_printer_offline(coordinator, config_entry):
    camera = BambuLabRtspCamera(coordinator, config_entry)
    assert camera.available

    coordinator.get_model().info.online = False

    assert not camera.available
    assert not camera.is_streaming


def test_chamber_image_unavailable_when_printer_offline(coordinator):
    image = ChamberImage(MagicMock(), coordinator, CHAMBER_IMAGE_SENSOR)
    assert image.available

    coordinator.get_model().info.online = False

    assert not image.available


def test_cameras_recover_when_printer_comes_back_online(coordinator, config_entry):
    camera = BambuLabImageCamera(coordinator, config_entry)
    image = ChamberImage(MagicMock(), coordinator, CHAMBER_IMAGE_SENSOR)
    coordinator.get_model().info.online = False
    assert not camera.available and not image.available

    coordinator.get_model().info.online = True

    assert camera.available and image.available
