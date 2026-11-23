"""RTSP camera stream options.

P2S and X1 chamber cameras send a first packet with dts 0 and then a
timestamp hours ahead. Home Assistant's stream worker treats a gap over
30 seconds as fatal and closes the live view. The camera asks the stream
component to rewrite timestamps from packet arrival time.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.camera import Camera
from homeassistant.components.stream.const import CONF_USE_WALLCLOCK_AS_TIMESTAMPS

from custom_components.bambu_lab.camera import BambuLabRtspCamera


def test_rtsp_camera_rewrites_timestamps_from_arrival_time():
    coordinator = MagicMock()
    entry = SimpleNamespace(
        data={"serial": "TESTSERIAL"},
        options={"access_code": "code"},
    )
    camera = BambuLabRtspCamera(coordinator, entry)
    assert camera.stream_options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] is True


HOSTNAME_URL = "rtsps://bblp:code@x1c.example:322/streaming/live/1"
RESOLVE = "custom_components.bambu_lab.camera.async_resolve_ipv4"


def _camera(reported_url="rtsps://192.0.2.20:322/streaming/live/1"):
    coordinator = MagicMock()
    model = coordinator.get_model.return_value
    model.camera.rtsp_url = reported_url
    model.info.ip_address = "x1c.example"
    entry = SimpleNamespace(
        data={"serial": "TESTSERIAL"},
        options={"access_code": "code"},
    )
    return BambuLabRtspCamera(coordinator, entry)


def test_stream_source_uses_resolved_address():
    """go2rtc checks the certificate against a hostname, which Bambu's never matches (#1798)."""
    with patch(RESOLVE, AsyncMock(return_value="192.0.2.10")) as resolve:
        source = asyncio.run(_camera().stream_source())
    assert source == "rtsps://bblp:code@192.0.2.10:322/streaming/live/1"
    resolve.assert_awaited_once_with("x1c.example")


def test_stream_source_keeps_hostname_that_does_not_resolve():
    with patch(RESOLVE, AsyncMock(return_value="x1c.example")):
        assert asyncio.run(_camera().stream_source()) == HOSTNAME_URL


def test_stream_source_skips_lookup_while_liveview_is_off():
    with patch(RESOLVE, AsyncMock()) as resolve:
        assert asyncio.run(_camera("disable").stream_source()) is None
    resolve.assert_not_awaited()


def test_home_assistant_stream_keeps_hostname():
    """HA caches the Stream, so a resolved address would go stale when DHCP changes it."""
    stream = SimpleNamespace(source="rtsps://bblp:code@192.0.2.10:322/streaming/live/1")
    with patch.object(Camera, "async_create_stream", AsyncMock(return_value=stream)):
        assert asyncio.run(_camera().async_create_stream()) is stream
    assert stream.source == HOSTNAME_URL


def test_home_assistant_stream_may_be_unavailable():
    with patch.object(Camera, "async_create_stream", AsyncMock(return_value=None)):
        assert asyncio.run(_camera("disable").async_create_stream()) is None


def test_home_assistant_stream_keeps_source_while_liveview_is_off():
    stream = SimpleNamespace(source=HOSTNAME_URL)
    with patch.object(Camera, "async_create_stream", AsyncMock(return_value=stream)):
        asyncio.run(_camera("disable").async_create_stream())
    assert stream.source == HOSTNAME_URL
