"""Optional checks for the Live view camera select: run in a Home Assistant Python environment.

They skip when Home Assistant is absent. No MQTT connection is made; the printer model is
mocked.
"""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import select as select_module
from custom_components.bambu_lab.const import DOMAIN
from custom_components.bambu_lab.pybambu.models import Camera

EN = json.loads(
    (Path(__file__).resolve().parents[1] / "custom_components" / "bambu_lab" / "translations" / "en.json")
    .read_text(encoding="utf-8")
)


def _setup(ipcam: dict, signature_required: bool = False):
    """Run the select platform setup against a mocked printer and return the entities added."""
    client = MagicMock()
    client._enable_camera = False
    camera = Camera(client)
    camera.print_update({"ipcam": ipcam})

    model = MagicMock()
    model.has_full_printer_data = True
    model.print_fun.mqtt_signature_required = signature_required
    model.supports_feature.return_value = False
    model.info.serial = "SERIAL"
    model.camera = camera

    coordinator = MagicMock()
    coordinator.get_model.return_value = model
    hass = SimpleNamespace(data={DOMAIN: {"entry": coordinator}})
    entry = SimpleNamespace(entry_id="entry")

    added = []
    asyncio.run(select_module.async_setup_entry(hass, entry, lambda entities: added.extend(entities)))
    return added, client


def _liveview_selects(entities):
    return [e for e in entities if isinstance(e, select_module.BambuLabLiveviewCameraSelect)]


def test_printer_with_birdseye_camera_gets_the_select():
    entities, client = _setup({"current_liveview": 4, "support_liveview_cams": [4, 5]})
    [select] = _liveview_selects(entities)

    assert select.unique_id == "SERIAL_LiveviewCamera"
    assert select.options == ["main", "birdseye"]
    assert select.current_option == "main"

    asyncio.run(select.async_select_option("birdseye"))
    assert client.publish.call_args.args[0]["camera"]["camera_id"] == 5


def test_select_is_unavailable_while_live_view_is_off_or_unreported():
    entities, _ = _setup({"current_liveview": 4, "support_liveview_cams": [4, 5]})
    [select] = _liveview_selects(entities)
    camera = select.coordinator.get_model().camera
    select.coordinator.last_update_success = True
    assert select.available

    camera.print_update({"ipcam": {"rtsp_url": "disable"}})
    assert not select.available

    camera.print_update({"ipcam": {"rtsp_url": "rtsps://192.0.2.10:322/streaming/live/1", "current_liveview": 7}})
    assert not select.available


def test_printer_without_birdseye_camera_gets_no_select():
    entities, _ = _setup({"rtsp_url": "rtsps://192.0.2.10:322/streaming/live/1"})
    assert _liveview_selects(entities) == []

    entities, _ = _setup({"current_liveview": 4, "support_liveview_cams": [4]})
    assert _liveview_selects(entities) == []


def test_no_select_while_control_is_blocked_by_signature_requirement():
    entities, _ = _setup({"current_liveview": 4, "support_liveview_cams": [4, 5]}, signature_required=True)
    assert _liveview_selects(entities) == []


def test_select_strings_exist():
    strings = EN["entity"]["select"]["liveview_camera"]
    assert strings["name"]
    assert set(strings["state"]) == {"main", "birdseye"}
