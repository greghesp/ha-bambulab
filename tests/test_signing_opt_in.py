"""Exercise the real coordinator consent boundary without network or hardware."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
pytest.importorskip("homeassistant")
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator

@pytest.mark.parametrize("consent", [None, False, "true", 1, True])
def test_only_explicit_boolean_consent_loads_bundle(consent):
    async def check():
        entry = SimpleNamespace(entry_id="test", data={"serial": "TEST", "device_type": "X1C"}, options={"enable_signed_fans": consent}, title="test")
        hass = MagicMock()
        hass.config.language = "en"
        hass.config.path.return_value = "/private/bundle"
        with patch("custom_components.bambu_lab.coordinator.BambuClient") as client, patch.object(BambuDataUpdateCoordinator, "get_file_cache_directory", return_value="/cache"), patch("custom_components.bambu_lab.coordinator.DataUpdateCoordinator.__init__", autospec=True, side_effect=lambda self, hass, *args, **kwargs: setattr(self, "hass", hass)):
            BambuDataUpdateCoordinator(hass, entry=entry)
        assert client.call_args.args[0]["signing_path"] == ("/private/bundle/bambu_lab_signing/TEST" if consent is True else None)

    asyncio.run(check())
