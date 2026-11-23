"""Optional, user-configured shared camera relay (no printer credentials copied)."""

import asyncio
from collections.abc import Mapping
from time import monotonic
from urllib.parse import urlsplit

CONF_CAMERA_RELAY_STREAM = "camera_relay_stream"
CONF_CAMERA_RELAY_SNAPSHOT = "camera_relay_snapshot"
CAMERA_RELAY_MODE = "camera_relay"
MAX_SNAPSHOT_BYTES = 10 * 1024 * 1024
SNAPSHOT_TIMEOUT = 10


class InvalidRelayURL(ValueError):
    """Invalid relay option; the exception never includes a potentially secret URL."""

    def __init__(self, field: str):
        self.field = field
        super().__init__("Invalid camera relay URL")


def validate_relay_options(values: Mapping) -> dict[str, str]:
    """Validate optional URLs without contacting a relay or the printer."""
    result = {}
    for field, schemes in (
        (CONF_CAMERA_RELAY_STREAM, {"rtsp", "rtsps"}),
        (CONF_CAMERA_RELAY_SNAPSHOT, {"http", "https"}),
    ):
        value = values.get(field, "")
        if not isinstance(value, str):
            raise InvalidRelayURL(field)
        value = value.strip()
        if value:
            try:
                parsed = urlsplit(value)
                if (
                    parsed.scheme not in schemes
                    or not parsed.hostname
                    or parsed.fragment
                    or any(character.isspace() or ord(character) < 32 for character in value)
                ):
                    raise ValueError
                # Accessing port validates non-numeric and out-of-range values.
                parsed.port
            except ValueError:
                raise InvalidRelayURL(field) from None
        result[field] = value
    if result[CONF_CAMERA_RELAY_SNAPSHOT] and not result[CONF_CAMERA_RELAY_STREAM]:
        raise InvalidRelayURL(CONF_CAMERA_RELAY_STREAM)
    return result


def update_relay_options(current: Mapping, values: Mapping) -> dict:
    """Preserve unrelated options; empty URLs restore the original direct camera."""
    result = dict(current)
    for field, value in validate_relay_options(values).items():
        if value:
            result[field] = value
        else:
            result.pop(field, None)
    return result


class RelaySnapshotClient:
    """Coalesce simultaneous HA snapshot requests, keeping the shared upstream.

    The relay owns its upstream connection. Never silently fall back to opening
    another connection to the printer when a configured relay fails.
    """

    def __init__(self, session, url: str):
        self._session = session
        self._url = url
        self._lock = asyncio.Lock()
        self._image: bytes | None = None
        self._updated = float("-inf")

    async def async_get_image(self) -> bytes:
        async with self._lock:
            if self._image is not None and monotonic() - self._updated < 1:
                return self._image
            async with asyncio.timeout(SNAPSHOT_TIMEOUT):
                async with self._session.get(self._url, allow_redirects=False) as response:
                    # Reject redirects too: never forward relay credentials elsewhere.
                    if response.status != 200:
                        raise ValueError("Relay snapshot request failed")
                    if response.content_type not in {"image/jpeg", "image/jpg"}:
                        raise ValueError("Relay did not return a JPEG image")
                    image = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        image.extend(chunk)
                        if len(image) > MAX_SNAPSHOT_BYTES:
                            raise ValueError("Relay snapshot exceeds size limit")
            if not image.startswith(b"\xff\xd8") or not image.endswith(b"\xff\xd9"):
                raise ValueError("Relay returned an incomplete JPEG image")
            self._image = bytes(image)
            self._updated = monotonic()
            return self._image
