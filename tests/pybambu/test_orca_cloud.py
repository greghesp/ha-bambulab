import base64
import hashlib
import unittest
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from pybambu.orca_cloud import (
    ORCA_REDIRECT_URI,
    OrcaCloud,
    OrcaCloudAuthError,
    OrcaCloudError,
    build_authorize_url,
    create_pkce,
    drop_shared_client,
    extract_auth_code,
    get_shared_client,
    parse_filament_profiles,
)


def _response(status_code, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload if payload is not None else {}
    response.text = str(payload)
    return response


def _token_payload(access="access-1", refresh="refresh-2"):
    return {"access_token": access, "refresh_token": refresh, "expires_in": 3600}


class TestPkce(unittest.TestCase):
    def test_challenge_is_unpadded_base64url_sha256_of_verifier(self):
        pkce = create_pkce()
        expected = base64.urlsafe_b64encode(hashlib.sha256(pkce.verifier.encode()).digest()).decode().rstrip("=")
        self.assertEqual(pkce.challenge, expected)
        self.assertGreaterEqual(len(pkce.verifier), 43)

    def test_each_call_is_unique(self):
        self.assertNotEqual(create_pkce().verifier, create_pkce().verifier)


class TestAuthorizeUrl(unittest.TestCase):
    def test_url_carries_provider_redirect_and_challenge(self):
        url = urlparse(build_authorize_url("github", "the-challenge"))
        query = parse_qs(url.query)
        self.assertEqual(url.netloc, "auth.orcaslicer.com")
        self.assertEqual(url.path, "/auth/v1/authorize")
        self.assertEqual(query["provider"], ["github"])
        self.assertEqual(query["redirect_to"], [ORCA_REDIRECT_URI])
        self.assertEqual(query["code_challenge"], ["the-challenge"])
        self.assertEqual(query["code_challenge_method"], ["s256"])

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            build_authorize_url("myspace", "c")


class TestExtractAuthCode(unittest.TestCase):
    def test_full_redirect_url(self):
        self.assertEqual(extract_auth_code("http://localhost:41172/callback?code=abc-123&state=x"), "abc-123")

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(extract_auth_code("  http://localhost:41172/callback?code=abc  \n"), "abc")

    def test_bare_code(self):
        self.assertEqual(extract_auth_code("a1b2c3d4-e5f6"), "a1b2c3d4-e5f6")

    def test_bare_query_string(self):
        self.assertEqual(extract_auth_code("code=xyz&state=s"), "xyz")

    def test_url_without_code_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_auth_code("http://localhost:41172/callback?state=x")

    def test_provider_error_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_auth_code("http://localhost:41172/callback?error=access_denied&error_description=nope")

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_auth_code("   ")


class TestParseFilamentProfiles(unittest.TestCase):
    def test_filament_with_serialized_string_values(self):
        upserts = [{
            "id": "uuid-1",
            "name": "Sunlu PLA+ @Bambu Lab P1S 0.4 nozzle",
            "content": {
                "name": "Sunlu PLA+ @Bambu Lab P1S 0.4 nozzle",
                "filament_id": "P1234567",
                "filament_vendor": "\"Sunlu\"",
                "filament_type": "\"PLA\"",
                "nozzle_temperature_range_low": "190",
                "nozzle_temperature_range_high": "230",
            },
        }]
        result = parse_filament_profiles(upserts)
        self.assertEqual(result, {
            "P1234567": {
                "name": "Sunlu PLA+",
                "filament_vendor": "Sunlu",
                "filament_type": "PLA",
                "nozzle_temperature_range_low": 190,
                "nozzle_temperature_range_high": 230,
            }
        })

    def test_filament_with_list_values(self):
        upserts = [{"id": "u", "name": "Fancy PETG", "content": {
            "filament_id": "PABCDEF",
            "filament_vendor": ["Fancy"],
            "filament_type": ["PETG"],
            "nozzle_temperature_range_low": ["220"],
            "nozzle_temperature_range_high": [260],
        }}]
        info = parse_filament_profiles(upserts)["PABCDEF"]
        self.assertEqual(info["name"], "Fancy PETG")
        self.assertEqual(info["filament_type"], "PETG")
        self.assertEqual(info["nozzle_temperature_range_low"], 220)
        self.assertEqual(info["nozzle_temperature_range_high"], 260)

    def test_multi_extruder_serialized_values_use_first(self):
        upserts = [{"id": "u", "name": "Dual", "content": {
            "filament_id": "PDUAL",
            "filament_type": "\"PLA\";\"PLA\"",
            "nozzle_temperature_range_low": "200,205",
            "nozzle_temperature_range_high": "[\"240\", \"245\"]",
        }}]
        info = parse_filament_profiles(upserts)["PDUAL"]
        self.assertEqual(info["filament_type"], "PLA")
        self.assertEqual(info["nozzle_temperature_range_low"], 200)
        self.assertEqual(info["nozzle_temperature_range_high"], 240)

    def test_non_filament_profiles_are_skipped(self):
        upserts = [
            {"id": "p", "name": "0.20mm Standard", "content": {"layer_height": "0.2", "type": "process"}},
            {"id": "m", "name": "My P1S", "content": {"printer_model": "Bambu Lab P1S", "type": "machine"}},
        ]
        self.assertEqual(parse_filament_profiles(upserts), {})

    def test_filament_without_id_is_skipped(self):
        upserts = [{"id": "u", "name": "No id", "content": {"filament_type": "PLA", "filament_id": ""}}]
        self.assertEqual(parse_filament_profiles(upserts), {})

    def test_missing_fields_fall_back_to_defaults(self):
        upserts = [{"id": "u", "name": "Bare", "content": {"filament_id": "PBARE", "nozzle_temperature_range_low": "junk"}}]
        info = parse_filament_profiles(upserts)["PBARE"]
        self.assertEqual(info["filament_vendor"], "")
        self.assertEqual(info["filament_type"], "")
        self.assertEqual(info["nozzle_temperature_range_low"], 0)
        self.assertEqual(info["nozzle_temperature_range_high"], 0)

    def test_malformed_entries_are_ignored(self):
        self.assertEqual(parse_filament_profiles([None, "x", {"content": None}, {"content": "str"}]), {})


class TestOrcaCloudAuth(unittest.TestCase):
    def test_exchange_code_posts_pkce_body_and_returns_refresh_token(self):
        session = MagicMock()
        session.post.return_value = _response(200, _token_payload(refresh="new-refresh"))

        token = OrcaCloud.exchange_code("the-code", "the-verifier", session=session)

        self.assertEqual(token, "new-refresh")
        url = session.post.call_args.args[0]
        self.assertTrue(url.endswith("/auth/v1/token?grant_type=pkce"))
        self.assertEqual(session.post.call_args.kwargs["json"], {"auth_code": "the-code", "code_verifier": "the-verifier"})
        self.assertIn("apikey", session.post.call_args.kwargs["headers"])

    def test_exchange_code_rejected_raises_auth_error(self):
        session = MagicMock()
        session.post.return_value = _response(400, {"error": "invalid_grant"})
        with self.assertRaises(OrcaCloudAuthError):
            OrcaCloud.exchange_code("bad", "verifier", session=session)

    def test_exchange_code_server_error_raises_cloud_error(self):
        session = MagicMock()
        session.post.return_value = _response(503)
        with self.assertRaises(OrcaCloudError) as ctx:
            OrcaCloud.exchange_code("c", "v", session=session)
        self.assertNotIsInstance(ctx.exception, OrcaCloudAuthError)

    def test_constructor_requires_refresh_token(self):
        with self.assertRaises(ValueError):
            OrcaCloud("")


class TestOrcaCloudProfiles(unittest.TestCase):
    def _cloud(self, session, listener=None):
        return OrcaCloud("refresh-1", on_token_refreshed=listener, session=session)

    def test_fetch_refreshes_then_pulls_with_bearer_token(self):
        session = MagicMock()
        session.post.return_value = _response(200, _token_payload(access="acc", refresh="refresh-2"))
        session.get.return_value = _response(200, {"next_cursor": 5, "upserts": [{"id": "a"}], "deletes": []})
        listener = MagicMock()

        upserts = self._cloud(session, listener).get_profiles()

        self.assertEqual(upserts, [{"id": "a"}])
        self.assertEqual(session.post.call_args.kwargs["json"], {"refresh_token": "refresh-1"})
        listener.assert_called_once_with("refresh-2")
        get_kwargs = session.get.call_args.kwargs
        self.assertTrue(session.get.call_args.args[0].endswith("/api/v1/sync/pull"))
        self.assertEqual(get_kwargs["headers"]["Authorization"], "Bearer acc")
        self.assertIn("apikey", get_kwargs["headers"])

    def test_access_token_is_reused_while_valid(self):
        session = MagicMock()
        session.post.return_value = _response(200, _token_payload())
        session.get.return_value = _response(200, {"upserts": []})
        cloud = self._cloud(session)

        cloud.get_profiles()
        cloud.get_profiles()

        self.assertEqual(session.post.call_count, 1)

    def test_unauthorized_pull_refreshes_once_and_retries(self):
        session = MagicMock()
        session.post.side_effect = [
            _response(200, _token_payload(access="stale", refresh="r2")),
            _response(200, _token_payload(access="fresh", refresh="r3")),
        ]
        session.get.side_effect = [_response(401), _response(200, {"upserts": [{"id": "b"}]})]

        cloud = self._cloud(session)
        self.assertEqual(cloud.get_profiles(), [{"id": "b"}])
        self.assertEqual(session.get.call_args.kwargs["headers"]["Authorization"], "Bearer fresh")
        self.assertEqual(cloud.refresh_token, "r3")

    def test_rejected_refresh_token_raises_auth_error(self):
        session = MagicMock()
        session.post.return_value = _response(400, {"error": "refresh_token_already_used"})
        with self.assertRaises(OrcaCloudAuthError):
            self._cloud(session).get_profiles()
        session.get.assert_not_called()

    def test_server_error_on_pull_raises_cloud_error(self):
        session = MagicMock()
        session.post.return_value = _response(200, _token_payload())
        session.get.return_value = _response(500)
        with self.assertRaises(OrcaCloudError):
            self._cloud(session).get_profiles()

    def test_network_failure_raises_cloud_error(self):
        session = MagicMock()
        session.post.side_effect = OSError("no route")
        with self.assertRaises(OrcaCloudError):
            self._cloud(session).get_profiles()

    def test_listener_gets_each_rotation_in_order_through_401_retry(self):
        session = MagicMock()
        session.post.side_effect = [
            _response(200, _token_payload(access="stale", refresh="r2")),
            _response(200, _token_payload(access="fresh", refresh="r3")),
        ]
        session.get.side_effect = [_response(401), _response(200, {"upserts": []})]
        listener = MagicMock()

        self._cloud(session, listener).get_profiles()

        self.assertEqual([c.args[0] for c in listener.call_args_list], ["r2", "r3"])

    def test_rate_limited_refresh_is_not_an_auth_failure(self):
        session = MagicMock()
        session.post.return_value = _response(429)
        with self.assertRaises(OrcaCloudError) as ctx:
            self._cloud(session).get_profiles()
        self.assertNotIsInstance(ctx.exception, OrcaCloudAuthError)

    def test_link_tolerates_outage_but_not_rejection(self):
        session = MagicMock()
        session.post.return_value = _response(503)
        self._cloud(session).link()  # does not raise

        session.post.return_value = _response(400)
        with self.assertRaises(OrcaCloudAuthError):
            self._cloud(session).link()

    def test_listener_failure_does_not_break_fetch(self):
        session = MagicMock()
        session.post.return_value = _response(200, _token_payload())
        session.get.return_value = _response(200, {"upserts": []})
        listener = MagicMock(side_effect=RuntimeError("boom"))
        self.assertEqual(self._cloud(session, listener).get_profiles(), [])


class TestSharedClients(unittest.TestCase):
    def tearDown(self):
        drop_shared_client("entry")

    def test_same_entry_reuses_one_client_across_reloads(self):
        first = get_shared_client("entry", "t1")
        # After a rotation the stored option lags or changes, but the live client must be reused.
        self.assertIs(get_shared_client("entry", "t2"), first)
        self.assertEqual(first.refresh_token, "t1")

    def test_no_token_drops_client(self):
        get_shared_client("entry", "t1")
        self.assertIsNone(get_shared_client("entry", ""))
        self.assertEqual(get_shared_client("entry", "t9").refresh_token, "t9")

    def test_drop_detaches_listener_so_late_rotations_go_nowhere(self):
        listener = MagicMock()
        client = get_shared_client("entry", "t1")
        client.set_token_listener(listener)
        drop_shared_client("entry")

        session = MagicMock()
        session.post.return_value = _response(200, _token_payload())
        session.get.return_value = _response(200, {"upserts": []})
        client._session = session
        client.get_profiles()

        listener.assert_not_called()
        self.assertIsNot(get_shared_client("entry", "t1"), client)


if __name__ == "__main__":
    unittest.main()
