"""Issue #2328: the P1S chamber image froze on one frame until the integration was reloaded.

Two ways the image thread could stop delivering frames for good while MQTT stayed up:
the printer going silent without closing the connection (the read loop waited forever,
logging nothing), and repeated connect failures (the thread exited after 12 attempts and
nothing restarted it).
"""
import ssl
import struct
import unittest
from unittest.mock import MagicMock, patch

from pybambu import bambu_client
from pybambu.bambu_client import ChamberImageThread
from pybambu.const import LOGGER

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 50 + b"\xff\xd9"
HEADER = struct.pack("<I", len(JPEG)) + bytes(12)
FRAME = [HEADER, JPEG]
MAX_SIMULATED_SECONDS = 3600


class _Clock:
    """Simulated time, also standing in for the thread's stop event so nothing really waits."""

    def __init__(self):
        self.now = 0.0
        self.stopped = False

    def monotonic(self):
        return self.now

    def set(self):
        self.stopped = True

    def is_set(self):
        return self.stopped

    def wait(self, timeout):
        self.sleep(timeout)
        return self.stopped

    def sleep(self, seconds):
        self.now += seconds
        if self.now > MAX_SIMULATED_SECONDS:
            self.stopped = True


class _FakeConnection:
    """A connected TLS socket: yields each scripted chunk, then stays open but silent."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.closed = False

    def write(self, data):
        pass

    def getsockopt(self, level, option):
        return 0

    def setblocking(self, blocking):
        pass

    def close(self):
        self.closed = True

    def recv(self, size):
        if not self._chunks:
            raise ssl.SSLWantReadError()
        chunk = self._chunks.pop(0)
        if isinstance(chunk, Exception):
            raise chunk
        return chunk


class TestChamberImageRecovery(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        self.client = MagicMock()
        self.client._access_code = "12345678"
        self.client._device.info.ip_address = "192.0.2.10"
        self.client._device.info.device_type = "P1S"
        self.thread = ChamberImageThread(self.client)
        self.thread._stop_event = self.clock
        self.connect_times = []
        self.open_at_connect = []

    def run_thread(self, outcomes):
        """Run until the outcomes are used up (or simulated time runs out).

        Each connect consumes one outcome: an exception to raise, or a connection to use."""
        remaining = list(outcomes)
        opened = []

        def connect(address, timeout=None):
            self.connect_times.append(self.clock.now)
            self.open_at_connect.append([c for c in opened if not c.closed])
            if not remaining:
                self.thread.stop()
                raise TimeoutError("test finished")
            outcome = remaining.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            opened.append(outcome)
            self.client.local_tls_context.wrap_socket.return_value = outcome
            return MagicMock()

        with patch.object(bambu_client.socket, "create_connection", side_effect=connect), \
                patch.object(bambu_client, "time", self.clock):
            self.thread.run()
        self.assertEqual(remaining, [], "the thread stopped trying to connect")

    @property
    def frames(self):
        return self.client.on_jpeg_received.call_count

    def test_reconnects_when_the_printer_goes_silent(self):
        self.run_thread([_FakeConnection(FRAME), _FakeConnection(FRAME)])

        self.assertEqual(self.frames, 2)

    def test_a_silent_connection_is_closed_before_reconnecting(self):
        # The printer limits how many clients can watch the camera at once.
        self.run_thread([_FakeConnection(FRAME), _FakeConnection(FRAME)])

        self.assertEqual(self.open_at_connect, [[], [], []])

    def test_a_stall_is_logged(self):
        with self.assertLogs(LOGGER, level="WARNING") as logs:
            self.run_thread([_FakeConnection(FRAME)])

        self.assertEqual(len(logs.output), 1)
        self.assertIn("reconnecting", logs.output[0])

    def test_short_gaps_between_frames_do_not_reconnect(self):
        gap = [ssl.SSLWantReadError()] * 20
        self.run_thread([_FakeConnection(FRAME + gap + FRAME + gap + FRAME)])

        self.assertEqual(self.frames, 3)

    def test_keeps_retrying_after_many_failed_connects(self):
        self.run_thread([TimeoutError("timed out")] * 30 + [_FakeConnection(FRAME)])

        self.assertEqual(self.frames, 1)

    def test_retries_slow_down_after_repeated_failures(self):
        self.run_thread([ConnectionRefusedError("refused")] * 30)

        gaps = [b - a for a, b in zip(self.connect_times, self.connect_times[1:])]
        self.assertLess(max(gaps[:10]), 5)
        self.assertGreaterEqual(min(gaps[-10:]), 60)

    def test_persistent_failures_stop_logging_errors(self):
        # Port 6000 refuses connections for as long as LAN Only Liveview is off.
        def error_count(attempts):
            self.setUp()
            with self.assertLogs(LOGGER, level="WARNING") as logs:
                self.run_thread([ConnectionRefusedError("refused")] * attempts)
            return len(logs.output)

        self.assertEqual(error_count(40), error_count(20))

    def test_persistent_rejections_stop_logging_errors(self):
        # A wrong access code: the printer accepts the connection and then closes it.
        def error_count(attempts):
            self.setUp()
            with self.assertLogs(LOGGER, level="WARNING") as logs:
                self.run_thread([_FakeConnection([b""]) for _ in range(attempts)])
            return len(logs.output)

        self.assertEqual(error_count(40), error_count(20))

    def test_a_frame_after_slow_retries_restores_fast_retries(self):
        self.run_thread(
            [TimeoutError("timed out")] * 20
            + [_FakeConnection(FRAME + [ConnectionResetError("reset")])]
            + [TimeoutError("timed out")]
        )

        self.assertLess(self.connect_times[-1] - self.connect_times[-2], 5)

    def test_stop_interrupts_the_slow_retry_wait(self):
        waits = []

        def wait(timeout):
            waits.append(timeout)
            self.clock.stopped = True
            return True

        self.clock.wait = wait
        attempts = []

        def connect(address, timeout=None):
            attempts.append(address)
            raise TimeoutError("timed out")

        with patch.object(bambu_client.socket, "create_connection", side_effect=connect), \
                patch.object(bambu_client, "time", self.clock):
            self.thread.run()

        self.assertEqual(len(waits), 1)
        self.assertEqual(len(attempts), 12)


if __name__ == "__main__":
    unittest.main()
