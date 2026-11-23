"""Issue #1627: the RTSP camera must reach go2rtc when its URL appears late.

Home Assistant only looks for a WebRTC provider (go2rtc) when a camera is added.
A printer with LAN Only Liveview off has no stream URL at that moment, so turning
it on later has to trigger another look.

Optional entity checks: run in a Home Assistant Python environment.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.camera.webrtc import DATA_WEBRTC_PROVIDERS

from custom_components.bambu_lab.camera import BambuLabRtspCamera

RTSP_URL = "rtsps://192.0.2.10:322/streaming/live/1"


class _Harness:
    """A camera attached to a stand-in hass that has one WebRTC provider."""

    def __init__(self, rtsp_url: str | None) -> None:
        self.provider = MagicMock()
        self.provider.async_is_supported.side_effect = (
            lambda source: source.startswith("rtsps:")
        )
        self.provider.async_register_camera = AsyncMock()
        self.provider.async_unregister_camera = AsyncMock()

        self.coordinator = MagicMock()
        self.coordinator.last_update_success = True
        self.model = self.coordinator.get_model()
        self.model.info.ip_address = "192.0.2.10"
        self.model.camera.rtsp_url = rtsp_url

        self.camera = BambuLabRtspCamera(
            self.coordinator,
            SimpleNamespace(
                data={"serial": "TESTSERIAL"}, options={"access_code": "code"}
            ),
        )
        self.tasks = []
        self.camera.hass = SimpleNamespace(
            data={DATA_WEBRTC_PROVIDERS: {self.provider: None}},
            async_create_task=self._create_task,
        )
        self.camera.async_write_ha_state = MagicMock()

    def _create_task(self, coro):
        task = asyncio.get_running_loop().create_task(coro)
        self.tasks.append(task)
        return task

    async def add(self) -> None:
        # What Camera.async_internal_added_to_hass does when the entity is added.
        await self.camera.async_refresh_providers(write_state=False)

    async def update(self, rtsp_url: str | None) -> None:
        self.model.camera.rtsp_url = rtsp_url
        self.camera._handle_coordinator_update()
        await asyncio.gather(*self.tasks)


@pytest.mark.parametrize("initial_url", [None, "disable"])
def test_provider_is_picked_up_when_live_view_is_turned_on(initial_url):
    async def run():
        harness = _Harness(initial_url)
        await harness.add()
        assert harness.camera._webrtc_provider is None

        await harness.update(RTSP_URL)

        assert harness.camera._webrtc_provider is harness.provider

    asyncio.run(run())


def test_provider_is_dropped_when_live_view_is_turned_off():
    async def run():
        harness = _Harness(RTSP_URL)
        await harness.add()
        await harness.update(RTSP_URL)
        assert harness.camera._webrtc_provider is harness.provider

        await harness.update("disable")
        assert harness.camera._webrtc_provider is None

        await harness.update(RTSP_URL)
        assert harness.camera._webrtc_provider is harness.provider

    asyncio.run(run())


def test_unchanged_url_does_not_look_for_a_provider_again():
    async def run():
        harness = _Harness(RTSP_URL)
        await harness.add()
        await harness.update(RTSP_URL)
        tasks = len(harness.tasks)

        for _ in range(3):
            await harness.update(RTSP_URL)

        assert len(harness.tasks) == tasks
        assert harness.camera._webrtc_provider is harness.provider

    asyncio.run(run())


def test_every_update_still_writes_the_entity_state():
    async def run():
        harness = _Harness(RTSP_URL)
        await harness.update(RTSP_URL)
        harness.camera.async_write_ha_state.reset_mock()

        await harness.update(RTSP_URL)

        harness.camera.async_write_ha_state.assert_called_once_with()

    asyncio.run(run())
