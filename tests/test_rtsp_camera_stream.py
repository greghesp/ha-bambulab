"""RTSP camera stream options.

P2S and X1 chamber cameras send a first packet with dts 0 and then a
timestamp hours ahead. Home Assistant's stream worker treats a gap over
30 seconds as fatal and closes the live view. The camera asks the stream
component to rewrite timestamps from packet arrival time.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

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
