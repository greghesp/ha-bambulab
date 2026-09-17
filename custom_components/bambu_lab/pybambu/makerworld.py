"""Parsing of the MakerWorld account responses.

Three endpoints feed one picture of the account - see BambuCloud for each one's
response shape: the public creator profile, the points ledger and the boost
token counts.
"""
from __future__ import annotations

from dataclasses import dataclass


def as_int(value) -> int | None:
    """Coerce an API value to int, treating anything unexpected as missing."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class MakerWorldProfile:
    """The subset of the MakerWorld profile response we surface as sensors."""

    uid: int | None = None
    name: str = ""
    handle: str = ""
    level: int | None = None
    followers: int | None = None
    following: int | None = None
    likes: int | None = None
    collections: int | None = None
    designs: int | None = None
    design_downloads: int | None = None
    instance_downloads: int | None = None
    design_prints: int | None = None
    instance_prints: int | None = None
    points_earned: int | None = None
    points_spent: int | None = None
    points_earned_exclusive: int | None = None
    points_spent_exclusive: int | None = None
    boost_tokens: int | None = None
    boosts_received: int | None = None
    boosts_used: int | None = None
    boosts_expired: int | None = None
    # What the profile reports as the balance outright. The ledger arithmetic
    # below is only used when this is missing (public profile fallback).
    points_reported: int | None = None
    points_reported_exclusive: int | None = None

    @classmethod
    def from_json(cls, data: dict, points: dict | None = None, boosts: dict | None = None) -> MakerWorldProfile:
        """Build the account picture.

        Only the profile is required. The points and boost calls need an
        authenticated token, so they are allowed to be missing - those sensors
        then report unavailable while the profile ones keep working."""
        counts = data.get('MWCount') or {}
        personal = data.get('personal') or {}
        user_level = personal.get('userLevel') or {}
        points = points or {}
        boosts = boosts or {}
        return cls(
            uid=as_int(data.get('uid')),
            name=data.get('name') or "",
            handle=data.get('handle') or "",
            level=as_int(user_level.get('level')),
            followers=as_int(data.get('fanCount')),
            following=as_int(data.get('followCount')),
            likes=as_int(data.get('likeCount')),
            collections=as_int(data.get('collectionCount')),
            designs=as_int(counts.get('designCount')),
            design_downloads=as_int(counts.get('myDesignDownloadCount')),
            instance_downloads=as_int(counts.get('myInstanceDownloadCount')),
            design_prints=as_int(counts.get('myDesignPrintCount')),
            instance_prints=as_int(counts.get('myInstancePrintCount')),
            points_earned=as_int(points.get('totalRegularIncome')),
            points_spent=as_int(points.get('totalRegularExpense')),
            points_earned_exclusive=as_int(points.get('totalExclusiveIncome')),
            points_spent_exclusive=as_int(points.get('totalExclusiveExpense')),
            boosts_received=as_int(data.get('boostGained')),
            points_reported=as_int(data.get('pointRegular')),
            points_reported_exclusive=as_int(data.get('pointExclusive')),
            # 'boost' on the profile and 'availableTotal' on the boost endpoint
            # are the same figure; take whichever answered.
            boost_tokens=as_int(boosts.get('availableTotal')) if boosts.get('availableTotal') is not None else as_int(data.get('boost')),
            boosts_used=as_int(boosts.get('usedTotal')),
            boosts_expired=as_int(boosts.get('expiredTotal')),
        )

    @staticmethod
    def _sum(*values) -> int | None:
        """Sum the parts, or None if none of them were present.

        A partial response is still worth reporting - a missing part counts as
        zero rather than voiding the whole total."""
        present = [value for value in values if value is not None]
        return sum(present) if present else None

    # Verified against a live profile: the page's download and print figures are
    # the design counts alone (e.g. 4200 -> "4.2 k"), NOT these sums. Nothing on
    # MakerWorld shows the combined number, so it is an extra, off by default.
    @property
    def total_downloads(self) -> int | None:
        """Design downloads plus print profile downloads."""
        return self._sum(self.design_downloads, self.instance_downloads)

    @property
    def total_prints(self) -> int | None:
        """Design prints plus print profile prints."""
        return self._sum(self.design_prints, self.instance_prints)

    @staticmethod
    def _balance(earned, spent) -> int | None:
        """A points balance, or None unless both halves are known.

        Unlike the download counts, half a balance is a wrong number rather than
        an incomplete one, so it is not reported at all."""
        if earned is None or spent is None:
            return None
        return earned - spent

    @property
    def points(self) -> int | None:
        """The balance MakerWorld shows as total points."""
        regular = self.points_regular
        exclusive = self.points_exclusive
        if regular is None:
            return exclusive
        return regular if exclusive is None else regular + exclusive

    @property
    def points_regular(self) -> int | None:
        if self.points_reported is not None:
            return self.points_reported
        return self._balance(self.points_earned, self.points_spent)

    @property
    def points_exclusive(self) -> int | None:
        if self.points_reported_exclusive is not None:
            return self.points_reported_exclusive
        return self._balance(self.points_earned_exclusive, self.points_spent_exclusive)

    @property
    def profile_url(self) -> str | None:
        if self.handle:
            return f"https://makerworld.com/en/@{self.handle}"
        if self.uid:
            return f"https://makerworld.com/en/u/{self.uid}"
        return None
