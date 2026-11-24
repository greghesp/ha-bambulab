"""The tray sensors expose the filament's color name (#2027)."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.bambu_lab.definitions import (
    AMS_SENSORS,
    PRINTER_SENSORS,
    VIRTUAL_TRAY_SENSORS,
)
from custom_components.bambu_lab.pybambu.models import AMSTray, ExternalSpool

FIXTURE = Path(__file__).parent / "pybambu" / "2AMS1-1AMS2-1AMSHT.json"


def _rfid_trays(node):
    if isinstance(node, dict):
        if node.get("tray_id_name") and "tray_color" in node:
            yield node
        node = list(node.values())
    if isinstance(node, list):
        for child in node:
            yield from _rfid_trays(child)


def _sensor(sensors, key):
    return next(sensor for sensor in sensors if sensor.key == key)


@pytest.fixture
def client():
    client = MagicMock()
    client.slicer_settings.custom_filaments = {}
    return client


@pytest.fixture
def entity():
    coordinator = MagicMock()
    return SimpleNamespace(coordinator=coordinator, index=0)


def _load_caramel(tray):
    captured = next(
        t for t in _rfid_trays(json.loads(FIXTURE.read_text(encoding="utf-8")))
        if t["tray_id_name"] == "A01-N3"
    )
    data = {"id": "0", "state": 11, **{k: v for k, v in captured.items() if k != "state"}}
    tray.print_update({"vt_tray": data} if isinstance(tray, ExternalSpool) else data)


def test_ams_tray_sensor(client, entity):
    tray = AMSTray(client)
    model = entity.coordinator.get_model.return_value
    model.ams.data = {0: SimpleNamespace(tray=[tray])}
    sensor = _sensor(AMS_SENSORS, "tray_1")

    assert sensor.extra_attributes(entity)["color_name"] is None
    _load_caramel(tray)
    assert sensor.extra_attributes(entity)["color_name"] == "Caramel"


def test_active_tray_sensor(client, entity):
    tray = AMSTray(client)
    _load_caramel(tray)
    entity.coordinator.get_model.return_value.ams.active_tray = tray

    attributes = _sensor(PRINTER_SENSORS, "active_tray").extra_attributes(entity)

    assert attributes["color_name"] == "Caramel"


def test_external_spool_sensor(client, entity):
    spool = ExternalSpool(client, 0)
    _load_caramel(spool)
    entity.coordinator.get_model.return_value.external_spool = [spool]

    attributes = _sensor(VIRTUAL_TRAY_SENSORS, "external_spool").extra_attributes(entity)

    assert attributes["color_name"] == "Caramel"
