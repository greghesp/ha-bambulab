import unittest
from unittest.mock import MagicMock, call, patch

from pybambu.commands import GET_VERSION
from pybambu.models import Device


class TestAmsIdentitiesResolved(unittest.TestCase):
    """Registered AMS devices may only be judged stale once the printer has told us the
    serial of every AMS it reports. Otherwise a blank `sn` in the version payload removes a
    device that is still attached (#2089)."""

    AMS_PAYLOAD = {
        "command": "push_status",
        "msg": 0,
        "ams": {
            "ams": [{"id": "0", "humidity": "4", "temp": "25.0", "tray": []}],
            "tray_now": "255",
            "tray_tar": "255",
        },
    }

    def version(self, sn):
        return {
            "command": "get_version",
            "module": [{
                "name": "ams/0",
                "project_name": "",
                "sw_ver": "00.00.05.96",
                "hw_ver": "AMS08",
                "sn": sn,
            }],
        }

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client.slicer_settings.filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device

    def test_not_resolved_before_any_data(self):
        self.assertFalse(self.device.ams_identities_resolved)

    def test_not_resolved_when_version_has_a_blank_serial(self):
        self.device.print_update(self.AMS_PAYLOAD)
        self.device.info_update(self.version(""))

        self.assertTrue(self.device.has_full_printer_data)
        self.assertFalse(self.device.ams_identities_resolved)

    def test_not_resolved_when_push_all_has_no_ams_block(self):
        self.device.print_update({"command": "push_status", "msg": 0})
        self.device.info_update({"command": "get_version", "module": []})

        self.assertFalse(self.device.ams_identities_resolved)

    def test_resolved_once_the_serial_arrives(self):
        self.device.print_update(self.AMS_PAYLOAD)
        self.device.info_update(self.version(""))
        self.device.info_update(self.version("00600A000000000"))

        self.assertTrue(self.device.ams_identities_resolved)

    def test_not_resolved_when_version_reports_na_serial(self):
        self.device.print_update(self.AMS_PAYLOAD)
        self.device.info_update(self.version("N/A"))

        self.assertTrue(self.device.has_full_printer_data)
        self.assertEqual(self.device.ams.data[0].serial, "")
        self.assertFalse(self.device.ams_identities_resolved)

    def test_na_serial_does_not_replace_a_known_serial(self):
        self.device.print_update(self.AMS_PAYLOAD)
        self.device.info_update(self.version("00600A000000000"))
        self.device.info_update(self.version("N/A"))

        self.assertEqual(self.device.ams.data[0].serial, "00600A000000000")
        self.assertTrue(self.device.ams_identities_resolved)

    def test_units_reporting_na_do_not_share_a_serial(self):
        self.device.print_update({
            "command": "push_status",
            "msg": 0,
            "ams": {
                "ams": [
                    {"id": "0", "humidity": "4", "temp": "25.0", "tray": []},
                    {"id": "2", "humidity": "4", "temp": "25.0", "tray": []},
                ],
                "tray_now": "255",
                "tray_tar": "255",
            },
        })
        self.device.info_update({
            "command": "get_version",
            "module": [
                {"name": "n3f/0", "sw_ver": "00.00.07.10", "hw_ver": "N3F05", "sn": "N/A"},
                {"name": "n3f/2", "sw_ver": "00.00.07.10", "hw_ver": "N3F05", "sn": "N/A"},
            ],
        })

        self.assertNotIn("N/A", [ams.serial for ams in self.device.ams.data.values()])
        self.assertFalse(self.device.ams_identities_resolved)

    def test_resolved_when_the_printer_reports_no_ams(self):
        self.device.print_update({"command": "push_status", "msg": 0, "ams": {"ams": []}})
        self.device.info_update({"command": "get_version", "module": []})

        self.assertTrue(self.device.ams_identities_resolved)


class TestMissingAmsIdentityRequest(unittest.TestCase):
    """The printer only sends version info when asked. If an AMS had not been identified when
    the connection came up, its serial must be requested again or it never gets a device (#1831)."""

    @staticmethod
    def status(*indices):
        return {
            "command": "push_status",
            "msg": 0,
            "ams": {
                "ams": [{"id": str(index), "humidity": "4", "temp": "25.0", "tray": []} for index in indices],
                "tray_now": "255",
                "tray_tar": "255",
            },
        }

    @staticmethod
    def version(**serials):
        return {
            "command": "get_version",
            "module": [
                {"name": name.replace("_", "/"), "sw_ver": "03.00.21.29", "hw_ver": "N3F05", "sn": sn}
                for name, sn in serials.items()
            ],
        }

    def setUp(self):
        self.connect_new_device()
        patcher = patch("pybambu.models.time.monotonic", side_effect=lambda: self.now)
        self.now = 1000.0
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect_new_device(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device

    @property
    def request_count(self):
        return self.client.publish.call_args_list.count(call(GET_VERSION))

    def ready_count(self):
        return self.client.callback.call_args_list.count(call("event_printer_ready"))

    def test_requests_serial_when_ams_appears_after_version_info(self):
        self.device.info_update(self.version())
        self.device.print_update(self.status())
        self.assertEqual(self.request_count, 0)

        self.device.print_update(self.status(0))

        self.assertEqual(self.request_count, 1)

    def test_requests_serial_when_version_info_had_none(self):
        for serial in ("", "N/A"):
            with self.subTest(serial=serial):
                self.connect_new_device()
                self.device.print_update(self.status(0))
                self.device.info_update(self.version(n3f_0=serial))

                self.device.print_update(self.status(0))

                self.assertEqual(self.request_count, 1)

    def test_late_serial_reinitializes_entities(self):
        self.device.info_update(self.version())
        self.device.print_update(self.status())
        self.device.print_update(self.status(0))
        ready_before = self.ready_count()

        self.device.info_update(self.version(n3f_0="19C00A000000000"))

        self.assertEqual(self.device.ams.data[0].serial, "19C00A000000000")
        self.assertEqual(self.device.ams.data[0].model, "AMS 2 Pro")
        self.assertEqual(self.ready_count(), ready_before + 1)

    def test_no_request_before_the_first_version_info(self):
        # The request sent on connect is still outstanding.
        self.device.print_update(self.status(0))
        self.device.print_update(self.status(0))

        self.assertEqual(self.request_count, 0)

    def test_no_request_when_every_serial_is_known(self):
        self.device.print_update(self.status(0))
        self.device.info_update(self.version(n3f_0="19C00A000000000"))
        for _ in range(5):
            self.now += 600
            self.device.print_update(self.status(0))

        self.assertEqual(self.request_count, 0)

    def test_incremental_push_can_request_the_serial(self):
        self.device.info_update(self.version())
        self.device.print_update(self.status())

        self.device.print_update({**self.status(0), "msg": 1})

        self.assertEqual(self.request_count, 1)

    def test_requests_back_off_while_the_serial_stays_unknown(self):
        self.device.info_update(self.version(n3f_0="N/A"))
        self.device.print_update(self.status(0))
        start = self.now
        ready_before = self.ready_count()
        times = [0.0]
        for _ in range(3600):
            self.now += 1
            before = self.request_count
            self.device.print_update(self.status(0))
            self.device.info_update(self.version(n3f_0="N/A"))
            if self.request_count > before:
                times.append(self.now - start)

        gaps = [later - earlier for earlier, later in zip(times, times[1:])]
        self.assertEqual(gaps[:7], [5, 10, 20, 40, 80, 160, 300])
        self.assertTrue(all(gap == 300 for gap in gaps[7:]))
        self.assertGreater(len(gaps), 7)
        # Replies that change nothing must not set up the entities again.
        self.assertEqual(self.ready_count(), ready_before)

    def test_a_newly_attached_ams_is_requested_without_waiting(self):
        self.device.info_update(self.version(n3f_0="N/A"))
        for _ in range(3600):
            self.now += 1
            self.device.print_update(self.status(0))
        before = self.request_count

        self.device.print_update(self.status(0, 1))

        self.assertEqual(self.request_count, before + 1)

    def test_requests_stop_once_the_serial_arrives(self):
        self.device.info_update(self.version())
        self.device.print_update(self.status(0))
        self.device.info_update(self.version(n3f_0="19C00A000000000"))
        for _ in range(600):
            self.now += 1
            self.device.print_update(self.status(0))

        self.assertEqual(self.request_count, 1)
