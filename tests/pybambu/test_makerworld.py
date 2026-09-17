import unittest
from unittest.mock import MagicMock, patch

from pybambu.bambu_cloud import BambuCloud
from pybambu.const import BambuUrl
from pybambu.makerworld import MakerWorldProfile, as_int


# A real response from
# GET https://api.bambulab.com/v1/user-service/user/profile/<uid>,
# with the identifying values replaced.
PROFILE_RESPONSE = {
    "uid": 1234567890,
    "name": "Some Creator",
    "handle": "somecreator",
    "avatar": "https://public-cdn.bblmw.com/avatar/1234567890/avatar.jpeg",
    "fanCount": 150,
    "followCount": 8,
    "isFollowed": False,
    "likeCount": 1800,
    "collectionCount": 3400,
    "downloadCount": 12800,
    "setting": {"isLikeOpen": 1, "isFollowOpen": 1, "isFanOpen": 1},
    "personal": {
        "bio": "Design enthusiast.",
        "links": ["https://example.com/"],
        "backgroundUrl": "https://public-cdn.bblmw.com/default/background.png",
        "designsInfo": [{"id": 4711, "title": "A model", "status": 1, "nsfw": False}],
        "userLevel": {"level": 9, "gradeType": 1},
    },
    "favoritesCount": 0,
    "publicInstanceUploadCount": 0,
    "isDelete": False,
    "MWCount": {
        "myDesignDownloadCount": 4200,
        "myInstanceDownloadCount": 5100,
        "designCount": 12,
        "myDesignPrintCount": 3100,
        "myInstancePrintCount": 2900,
    },
    "certificated": False,
}


# A real response from GET /v1/point-service/point-bill/my, with a limit of 1.
# 'total' is the transaction count, not a points figure.
POINTS_RESPONSE = {
    "total": 640,
    "totalIncome": 15000,
    "totalExpense": 6600,
    "totalRegularIncome": 15000,
    "totalRegularExpense": 6600,
    "totalExclusiveIncome": 0,
    "totalExclusiveExpense": 0,
    "hits": [
        {
            "type": "instance_reward_v2",
            "pointChange": 5,
            "pointChangeRegular": 5,
            "pointChangeExclusive": 0,
            "pointTime": "2026-09-17T06:00:00Z",
        }
    ],
}

# A real response from GET /v1/point-service/boost/boostingright.
BOOSTS_RESPONSE = {
    "availableTotal": 2,
    "usedTotal": 40,
    "expiredTotal": 1,
    "total": 0,
    "hits": [],
}


# A real response from GET /v1/design-user-service/my/profile - the account's
# own profile, which carries the balance and the boosts outright.
MY_PROFILE_RESPONSE = dict(
    PROFILE_RESPONSE,
    point=8400,
    pointRegular=8400,
    pointExclusive=0,
    boost=2,
    boostGained=210,
)


class TestMakerWorldProfileParsing(unittest.TestCase):
    """The profile endpoint is undocumented, so parsing must not assume shape."""

    def test_parses_a_full_response(self):
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE)
        self.assertEqual(profile.uid, 1234567890)
        self.assertEqual(profile.name, "Some Creator")
        self.assertEqual(profile.handle, "somecreator")
        self.assertEqual(profile.level, 9)
        self.assertEqual(profile.followers, 150)
        self.assertEqual(profile.following, 8)
        self.assertEqual(profile.likes, 1800)
        self.assertEqual(profile.collections, 3400)
        self.assertEqual(profile.designs, 12)
        self.assertEqual(profile.design_downloads, 4200)
        self.assertEqual(profile.instance_downloads, 5100)
        self.assertEqual(profile.design_prints, 3100)
        self.assertEqual(profile.instance_prints, 2900)

    def test_design_counts_are_what_the_profile_page_shows(self):
        # Checked against a live profile: a profile whose myDesignDownloadCount
        # was 4200 printed "4.2 k", and myDesignPrintCount 3100 printed
        # "3.1 k" - the instance halves are not added in.
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE)
        self.assertEqual(profile.design_downloads, 4200)
        self.assertEqual(profile.design_prints, 3100)

    def test_totals_add_the_instance_halves(self):
        # Not a figure MakerWorld displays anywhere, which is why the sensors
        # built on it are off by default.
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE)
        self.assertEqual(profile.total_downloads, 4200 + 5100)
        self.assertEqual(profile.total_prints, 3100 + 2900)

    def test_top_level_download_count_is_not_used(self):
        # The top level downloadCount agrees with neither the design count nor
        # the sum (on one live profile: 12800 against 4200 and 9300).
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE)
        self.assertNotEqual(profile.design_downloads, 12800)
        self.assertNotEqual(profile.total_downloads, 12800)

    def test_missing_sections_do_not_raise(self):
        profile = MakerWorldProfile.from_json({"uid": 1})
        self.assertEqual(profile.uid, 1)
        self.assertIsNone(profile.level)
        self.assertIsNone(profile.design_downloads)
        self.assertIsNone(profile.total_downloads)
        self.assertIsNone(profile.total_prints)

    def test_null_sections_do_not_raise(self):
        # The API returns null rather than omitting a section for some accounts.
        profile = MakerWorldProfile.from_json(
            {"uid": 1, "MWCount": None, "personal": None}
        )
        self.assertIsNone(profile.level)
        self.assertIsNone(profile.designs)

    def test_partial_counts_still_produce_a_total(self):
        profile = MakerWorldProfile.from_json(
            {"uid": 1, "MWCount": {"myDesignDownloadCount": 10}}
        )
        self.assertEqual(profile.total_downloads, 10)

    def test_unexpected_types_are_treated_as_missing(self):
        self.assertIsNone(as_int("not a number"))
        self.assertIsNone(as_int(None))
        self.assertIsNone(as_int(True))
        self.assertEqual(as_int("42"), 42)

    def test_profile_url_prefers_the_handle(self):
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE)
        self.assertEqual(profile.profile_url, "https://makerworld.com/en/@somecreator")

    def test_profile_url_falls_back_to_the_uid(self):
        # Accounts that never picked a handle come back with an empty string.
        profile = MakerWorldProfile.from_json({"uid": 42, "handle": ""})
        self.assertEqual(profile.profile_url, "https://makerworld.com/en/u/42")


class TestMakerWorldPoints(unittest.TestCase):
    """Points and boosts come from two endpoints the profile knows nothing about."""

    def test_points_balance_is_income_minus_expense(self):
        # This is the figure MakerWorld prints as the account's total points;
        # Checked against a live profile page.
        profile = MakerWorldProfile.from_json(
            PROFILE_RESPONSE, points=POINTS_RESPONSE, boosts=BOOSTS_RESPONSE
        )
        self.assertEqual(profile.points, 8400)
        self.assertEqual(profile.points_regular, 8400)
        self.assertEqual(profile.points_exclusive, 0)
        self.assertEqual(profile.points_earned, 15000)
        self.assertEqual(profile.points_spent, 6600)

    def test_transaction_count_is_not_mistaken_for_points(self):
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE, points=POINTS_RESPONSE)
        self.assertNotEqual(profile.points, POINTS_RESPONSE['total'])

    def test_exclusive_points_add_to_the_balance(self):
        points = dict(POINTS_RESPONSE, totalExclusiveIncome=500, totalExclusiveExpense=200)
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE, points=points)
        self.assertEqual(profile.points_exclusive, 300)
        self.assertEqual(profile.points, 8400 + 300)

    def test_boost_tokens(self):
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE, boosts=BOOSTS_RESPONSE)
        self.assertEqual(profile.boost_tokens, 2)
        self.assertEqual(profile.boosts_used, 40)
        self.assertEqual(profile.boosts_expired, 1)

    def test_profile_survives_without_points_or_boosts(self):
        # The points call needs an authenticated token; if it fails, the public
        # profile figures must still be reported.
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE, points=None, boosts=None)
        self.assertEqual(profile.total_downloads, 4200 + 5100)
        self.assertIsNone(profile.points)
        self.assertIsNone(profile.boost_tokens)

    def test_half_a_balance_is_reported_as_unknown(self):
        # Unlike the download halves, half a balance is a wrong number.
        profile = MakerWorldProfile.from_json(
            PROFILE_RESPONSE, points={"totalRegularIncome": 15000}
        )
        self.assertIsNone(profile.points_regular)
        self.assertIsNone(profile.points)


class TestMakerWorldOwnProfile(unittest.TestCase):
    """The authenticated profile reports figures the public one does not."""

    def test_boosts_received(self):
        profile = MakerWorldProfile.from_json(MY_PROFILE_RESPONSE)
        self.assertEqual(profile.boosts_received, 210)

    def test_points_are_taken_from_the_profile_not_computed(self):
        # The ledger would say something else here; the profile's own figure wins.
        ledger = dict(POINTS_RESPONSE, totalRegularIncome=1, totalRegularExpense=0)
        profile = MakerWorldProfile.from_json(MY_PROFILE_RESPONSE, points=ledger)
        self.assertEqual(profile.points, 8400)

    def test_boost_tokens_fall_back_to_the_profile_field(self):
        # Without the boost endpoint, 'boost' on the profile is the same figure.
        profile = MakerWorldProfile.from_json(MY_PROFILE_RESPONSE, boosts=None)
        self.assertEqual(profile.boost_tokens, 2)

    def test_public_profile_still_computes_the_balance(self):
        # The fallback response has no 'point', so the ledger arithmetic applies.
        profile = MakerWorldProfile.from_json(PROFILE_RESPONSE, points=POINTS_RESPONSE)
        self.assertEqual(profile.points, 8400)
        self.assertIsNone(profile.boosts_received)


class TestMakerWorldCloudCalls(unittest.TestCase):

    def setUp(self):
        self.cloud = BambuCloud("", "", "u_1234567890", "token")

    def test_get_makerworld_profile_asks_for_the_own_profile_first(self):
        response = MagicMock()
        response.json.return_value = MY_PROFILE_RESPONSE
        with patch.object(BambuCloud, '_get', return_value=response) as mock_get:
            data = self.cloud.get_makerworld_profile("1234567890")
        mock_get.assert_called_once_with(BambuUrl.MY_PROFILE)
        self.assertEqual(data, MY_PROFILE_RESPONSE)

    def test_get_makerworld_profile_falls_back_to_the_public_one(self):
        public = MagicMock()
        public.json.return_value = PROFILE_RESPONSE

        def answer(urlenum, suffix=""):
            if urlenum == BambuUrl.MY_PROFILE:
                raise PermissionError(401, "nope")
            return public

        with patch.object(BambuCloud, '_get', side_effect=answer) as mock_get:
            data = self.cloud.get_makerworld_profile("1234567890")
        self.assertEqual(data, PROFILE_RESPONSE)
        mock_get.assert_called_with(BambuUrl.USER_PROFILE, suffix="/1234567890")

    def test_get_makerworld_profile_swallows_connection_failures(self):
        # A failed poll must never take the printer's coordinator down with it.
        with patch.object(BambuCloud, '_get', side_effect=PermissionError(403, "nope")):
            self.assertIsNone(self.cloud.get_makerworld_profile("1"))

    def test_get_makerworld_profile_without_a_uid_cannot_fall_back(self):
        with patch.object(BambuCloud, '_get', side_effect=PermissionError(401, "nope")) as mock_get:
            self.assertIsNone(self.cloud.get_makerworld_profile(None))
        self.assertEqual(mock_get.call_count, 1)

    def test_get_points_and_boosts_use_their_endpoints(self):
        response = MagicMock()
        response.json.return_value = POINTS_RESPONSE
        with patch.object(BambuCloud, '_get', return_value=response) as mock_get:
            self.assertEqual(self.cloud.get_makerworld_points(), POINTS_RESPONSE)
        mock_get.assert_called_once_with(BambuUrl.POINT_BILL)

        response.json.return_value = BOOSTS_RESPONSE
        with patch.object(BambuCloud, '_get', return_value=response) as mock_get:
            self.assertEqual(self.cloud.get_makerworld_boosts(), BOOSTS_RESPONSE)
        mock_get.assert_called_once_with(BambuUrl.BOOST_RIGHT)

    def test_points_and_boosts_swallow_failures(self):
        # These two need an authenticated token; a rejection must not take the
        # whole update down.
        with patch.object(BambuCloud, '_get', side_effect=PermissionError(401, "nope")):
            self.assertIsNone(self.cloud.get_makerworld_points())
            self.assertIsNone(self.cloud.get_makerworld_boosts())

    def test_get_uid_reads_the_mqtt_username(self):
        # The cloud login already stores the account id as 'u_<uid>', so no
        # extra request is needed.
        with patch.object(BambuCloud, '_get') as mock_get:
            self.assertEqual(self.cloud.get_uid(), "1234567890")
        mock_get.assert_not_called()

    def test_get_uid_falls_back_to_the_preference_api(self):
        cloud = BambuCloud("", "", "not-a-uid", "token")
        response = MagicMock()
        response.json.return_value = {"uid": 55, "name": "Some Creator"}
        with patch.object(BambuCloud, '_get', return_value=response) as mock_get:
            self.assertEqual(cloud.get_uid(), "55")
        mock_get.assert_called_once_with(BambuUrl.PREFERENCE)

    def test_get_uid_returns_none_when_unavailable(self):
        cloud = BambuCloud("", "", "", "token")
        with patch.object(BambuCloud, '_get', side_effect=PermissionError(403, "nope")):
            self.assertIsNone(cloud.get_uid())


if __name__ == '__main__':
    unittest.main()
