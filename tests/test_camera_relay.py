"""Shared relay settings and real HTTP snapshot requests, without HA or a printer."""

import asyncio
from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path

import aiohttp
from aiohttp import web
import pytest

_PATH = Path(__file__).resolve().parents[1] / "custom_components/bambu_lab/camera_relay.py"
_SPEC = importlib.util.spec_from_file_location("bambu_camera_relay", _PATH)
relay = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(relay)
STREAM = relay.CONF_CAMERA_RELAY_STREAM
SNAPSHOT = relay.CONF_CAMERA_RELAY_SNAPSHOT
JPEG = b"\xff\xd8example-frame\xff\xd9"


@pytest.mark.parametrize("source", [
    "rtsp://127.0.0.1:8554/printer",
    "rtsps://relay.example:322/shared?video=h264",
    "rtsp://[::1]:8554/shared",
    "rtsp://user:secret%40value@relay.example:8554/shared",
])
def test_relay_stream_urls(source):
    assert relay.validate_relay_options({STREAM: source})[STREAM] == source


@pytest.mark.parametrize("source", [
    "ffmpeg:rtsp://printer/live", "file:///etc/passwd", "http://relay/stream",
    "rtsp:///missing-host", "rtsp://relay:bad/stream", "rtsp://relay:70000/stream",
    "rtsp://relay/shared#exec=anything", "rtsp://relay/a b", "rtsp://re\nlay/stream", 42,
])
def test_invalid_stream_urls_do_not_echo_credentials(source):
    with pytest.raises(relay.InvalidRelayURL) as error:
        relay.validate_relay_options({STREAM: source})
    assert error.value.field == STREAM
    assert str(source) not in str(error.value)


@pytest.mark.parametrize("source", ["http://relay/frame.jpeg?src=shared", "https://relay/frame"])
def test_http_snapshot_urls(source):
    result = relay.validate_relay_options({STREAM: "rtsp://relay/shared", SNAPSHOT: source})
    assert result[SNAPSHOT] == source


def test_snapshot_requires_shared_stream():
    with pytest.raises(relay.InvalidRelayURL) as error:
        relay.validate_relay_options({SNAPSHOT: "http://relay/frame"})
    assert error.value.field == STREAM


@pytest.mark.parametrize("source", ["ftp://relay/frame", "http:///frame", "http://relay:bad/frame"])
def test_invalid_snapshot_url(source):
    with pytest.raises(relay.InvalidRelayURL) as error:
        relay.validate_relay_options({STREAM: "rtsp://relay/shared", SNAPSHOT: source})
    assert error.value.field == SNAPSHOT


def test_updates_preserve_printer_credentials_and_other_options():
    current = {"access_code": "original", "local_mqtt": True, "ams_heaters": {"AMS": "switch.plug"}}
    result = relay.update_relay_options(current, {STREAM: "  rtsp://relay/shared  "})
    assert result == {**current, STREAM: "rtsp://relay/shared"}
    assert STREAM not in current


def test_clearing_urls_restores_default_without_empty_overrides():
    result = relay.update_relay_options(
        {STREAM: "rtsp://relay/shared", SNAPSHOT: "http://relay/frame", "local_mqtt": True},
        {STREAM: " ", SNAPSHOT: ""},
    )
    assert result == {"local_mqtt": True}
    assert relay.update_relay_options({"local_mqtt": True}, {}) == result


@asynccontextmanager
async def snapshot_server(handler):
    app = web.Application()
    app.router.add_get("/frame", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        async with aiohttp.ClientSession() as session:
            yield session, f"http://127.0.0.1:{port}/frame"
    finally:
        await runner.cleanup()


def test_simultaneous_previews_share_one_request_and_cache_expires(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(relay, "monotonic", lambda: now[0])

    async def scenario():
        requests = []

        async def handler(request):
            requests.append(request)
            await asyncio.sleep(0.01)
            return web.Response(body=JPEG, content_type="image/jpeg")

        async with snapshot_server(handler) as (session, url):
            client = relay.RelaySnapshotClient(session, url)
            assert await asyncio.gather(*(client.async_get_image() for _ in range(5))) == [JPEG] * 5
            assert len(requests) == 1
            now[0] = 2
            assert await client.async_get_image() == JPEG
            assert len(requests) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("status,content_type,body", [
    (401, "text/plain", b"unauthorized"),
    (302, "text/plain", b"redirect"),
    (200, "text/html", b"<html>login</html>"),
    (200, "image/jpeg", b"truncated"),
])
def test_failed_snapshots_do_not_return_login_pages_or_cached_frames(status, content_type, body, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(relay, "monotonic", lambda: now[0])

    async def scenario():
        requests = []

        async def handler(request):
            requests.append(request)
            if len(requests) == 1:
                return web.Response(body=JPEG, content_type="image/jpeg")
            return web.Response(status=status, body=body, content_type=content_type,
                                headers={"Location": "/not-followed"})

        async with snapshot_server(handler) as (session, url):
            client = relay.RelaySnapshotClient(session, url)
            assert await client.async_get_image() == JPEG
            now[0] = 2
            with pytest.raises(ValueError) as error:
                await client.async_get_image()
            assert url not in str(error.value)
            assert len(requests) == 2

    asyncio.run(scenario())


def test_streamed_response_size_is_bounded(monkeypatch):
    monkeypatch.setattr(relay, "MAX_SNAPSHOT_BYTES", 8)

    async def scenario():
        async def handler(request):
            return web.Response(body=JPEG, content_type="image/jpeg")
        async with snapshot_server(handler) as (session, url):
            with pytest.raises(ValueError, match="size limit"):
                await relay.RelaySnapshotClient(session, url).async_get_image()
    asyncio.run(scenario())


def test_unresponsive_snapshot_times_out(monkeypatch):
    monkeypatch.setattr(relay, "SNAPSHOT_TIMEOUT", 0.01)

    async def scenario():
        async def handler(request):
            await asyncio.sleep(0.05)
            return web.Response(body=JPEG, content_type="image/jpeg")
        async with snapshot_server(handler) as (session, url):
            with pytest.raises(TimeoutError):
                await relay.RelaySnapshotClient(session, url).async_get_image()
    asyncio.run(scenario())
