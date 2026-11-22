"""Every action must let the user pick its target (#1041).

normalize_service_target rejects calls without a device_id or entity_id, so an action
whose services.yaml entry declares neither cannot be used from the Home Assistant UI.
"""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SERVICES_YAML = Path(__file__).parent.parent / "custom_components" / "bambu_lab" / "services.yaml"


def _services():
    return yaml.safe_load(SERVICES_YAML.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(_services()))
def test_service_declares_a_target_field(name):
    fields = _services()[name].get("fields") or {}
    targets = {"device_id", "entity_id"} & set(fields)
    assert targets, f"{name} has no device_id or entity_id field"
    assert any(fields[t].get("required") for t in targets), f"{name} target is not required"
