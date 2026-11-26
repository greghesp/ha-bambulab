import json
import time
import unittest
from unittest.mock import MagicMock, patch

from pybambu.bambu_client import BambuClient

CONN_LOST = 7
KEEPALIVE_TIMEOUT = 16
ACCESS_DENIED = 5
GRACE_PERIOD = 0.3


class TestOfflineGracePeriod(unittest.TestCase):
    """A connection that drops and comes straight back must not flip the printer offline (#1871)."""

    def setUp(self):
        self.client = BambuClient({
            'host': '192.0.2.10',
            'serial': 'TESTSERIAL123',
            'enable_camera': False,
        })
        self.client.client = MagicMock()
        self.client.client.publish.return_value.rc = 0
        self.client.slicer_settings = MagicMock()
        self.online_history = []
        self.client._callback = self._record_online
        patcher = patch("pybambu.bambu_client.OFFLINE_GRACE_PERIOD", GRACE_PERIOD)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._shut_down)
        self._receive({"print": {"msg": 1}})
        self.online_history.clear()

    def _shut_down(self):
        if self.client.client is not None:
            self.client.disconnect()

    def _record_online(self, event):
        online = self.client._device.info.online
        if not self.online_history or self.online_history[-1] != online:
            self.online_history.append(online)

    def _receive(self, payload):
        message = MagicMock()
        message.payload = json.dumps(payload).encode()
        self.client.on_message(None, None, message)

    def _drop(self, result_code=CONN_LOST):
        self.client.on_disconnect(client_=None, userdata=None, result_code=result_code)

    def _reconnect(self):
        self.client.on_connect(None, None, {}, 0)

    def _wait_past_grace_period(self):
        time.sleep(GRACE_PERIOD * 3)

    def _wait_until_offline(self):
        deadline = time.monotonic() + 5
        while self._online and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self._online)

    @property
    def _online(self):
        return self.client._device.info.online

    def test_quick_reconnect_never_reports_offline(self):
        for result_code in (CONN_LOST, KEEPALIVE_TIMEOUT):
            with self.subTest(result_code=result_code):
                self._drop(result_code)
                self._reconnect()
                self._receive({"print": {"msg": 1}})
                self._wait_past_grace_period()

                self.assertTrue(self._online)
                self.assertNotIn(False, self.online_history)

    def test_offline_once_the_grace_period_ends(self):
        self._drop()
        self.assertTrue(self._online)

        self._wait_until_offline()
        self.assertEqual(self.online_history, [False])

    def test_reconnecting_without_receiving_data_still_goes_offline(self):
        self._drop()
        self._reconnect()
        self._wait_until_offline()

    def test_repeated_drops_do_not_extend_the_grace_period(self):
        deadline = time.monotonic() + GRACE_PERIOD * 3
        while self._online and time.monotonic() < deadline:
            self._drop()
            time.sleep(GRACE_PERIOD / 4)

        self.assertFalse(self._online)

    def test_a_second_outage_gets_its_own_grace_period(self):
        self._drop()
        self._wait_until_offline()
        self._receive({"print": {"msg": 1}})
        self._drop()
        self.assertTrue(self._online)

        self._wait_until_offline()

    def test_access_denied_is_offline_immediately(self):
        self._drop(ACCESS_DENIED)

        self.assertFalse(self._online)

    def test_access_denied_during_the_grace_period_is_offline_immediately(self):
        self._drop()
        self._drop(ACCESS_DENIED)

        self.assertFalse(self._online)

    def test_clean_disconnect_is_offline_immediately(self):
        self._drop(0)

        self.assertFalse(self._online)

    def test_cloud_reporting_the_printer_gone_is_offline_immediately(self):
        self._receive({"event": {"event": "client.disconnected"}})

        self.assertFalse(self._online)

    def test_cloud_reporting_the_printer_back_gets_the_grace_period(self):
        # The cloud need not report the disconnect first, so a reconnect is handled as a drop too.
        self._receive({"event": {"event": "client.connected"}})
        self.assertTrue(self._online)

        self._receive({"print": {"msg": 1}})
        self._wait_past_grace_period()

        self.assertNotIn(False, self.online_history)

    def test_rack_state_is_invalidated_without_waiting(self):
        # Moving the hotend rack needs status received after the reconnect.
        rack = self.client._device.hotend_rack
        rack._holder_stat_known = True
        rack._print_state_known = True

        self._drop()

        self.assertFalse(rack._holder_stat_known)
        self.assertFalse(rack._print_state_known)

    def test_shutting_down_cancels_the_pending_offline_report(self):
        self._drop()
        self.client.disconnect()
        self.online_history.clear()

        self._wait_past_grace_period()

        self.assertEqual(self.online_history, [])

    def test_a_late_drop_after_shutting_down_is_not_reported(self):
        self.client.disconnect()
        self.online_history.clear()

        self._drop()
        self._wait_past_grace_period()

        self.assertEqual(self.online_history, [])


if __name__ == "__main__":
    unittest.main()
