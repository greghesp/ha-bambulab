"""Read-only client for Orca Cloud (cloud.orcaslicer.com) profile sync.

OrcaSlicer 2.4 stopped syncing user presets to Bambu Cloud and syncs them to
Orca Cloud instead, so LAN-mode users who slice with Orca have no other source
for their custom filament names. This mirrors the parts of OrcaSlicer's
OrcaCloudServiceAgent that are needed to read those presets:

* Auth is Supabase. Password sign-in is disabled, so we use the same OAuth
  PKCE flow as OrcaSlicer: the user signs in with their provider in a browser,
  which redirects to http://localhost:41172/callback?code=... The page there
  fails to load (nothing is listening), and the user pastes that URL back into
  Home Assistant so we can exchange the code for a session.
* Supabase rotates the refresh token on every use. The caller must persist the
  new token passed to `on_token_refreshed`, or the next start-up will fail.
* Profiles come from GET /api/v1/sync/pull. Each upsert's `content` is the same
  flat key/value preset map that Bambu Cloud stores.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from .const import LOGGER

ORCA_AUTH_URL = "https://auth.orcaslicer.com"
ORCA_API_URL = "https://api.orcaslicer.com"
# Public "publishable" client key that OrcaSlicer ships in its binary. It only
# identifies the client to Supabase; it grants nothing without a user session.
ORCA_PUBLISHABLE_KEY = "sb_publishable_lvVe_whOi80SU9BPSxM1kA_tbt9AbR_"
ORCA_REDIRECT_URI = "http://localhost:41172/callback"
ORCA_PROVIDERS = ("google", "github", "apple", "facebook")

_TOKEN_PATH = "/auth/v1/token"
_AUTHORIZE_PATH = "/auth/v1/authorize"
_SYNC_PULL_PATH = "/api/v1/sync/pull"
_REQUEST_TIMEOUT_S = 15
# Refresh a little before the access token actually expires.
_EXPIRY_SKEW_S = 60
_DEFAULT_EXPIRES_IN_S = 3600


class OrcaCloudError(Exception):
    """Orca Cloud could not be reached or returned an unexpected response."""


class OrcaCloudAuthError(OrcaCloudError):
    """Orca Cloud rejected the credentials; the user has to sign in again."""


@dataclass(frozen=True)
class PkceChallenge:
    verifier: str
    challenge: str


def create_pkce() -> PkceChallenge:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return PkceChallenge(verifier=verifier, challenge=challenge)


def build_authorize_url(provider: str, code_challenge: str) -> str:
    if provider not in ORCA_PROVIDERS:
        raise ValueError(f"Unsupported Orca Cloud sign-in provider: {provider}")
    query = urlencode({
        "provider": provider,
        "redirect_to": ORCA_REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "s256",
    })
    return f"{ORCA_AUTH_URL}{_AUTHORIZE_PATH}?{query}"


def extract_auth_code(pasted: str) -> str:
    """Pull the auth code out of the redirect URL the user pasted (or accept a bare code)."""
    text = (pasted or "").strip()
    if text == "":
        raise ValueError("Nothing was pasted")
    if "://" not in text and "?" not in text and "=" not in text:
        return text

    parsed = urlparse(text)
    # Accept a bare "code=...&state=..." query string as well as a full URL.
    params = parse_qs(parsed.query if "://" in text or "?" in text else text)
    # Some providers hand results back in the fragment instead of the query.
    params.update({k: v for k, v in parse_qs(parsed.fragment).items() if k not in params})
    if "error" in params:
        description = params.get("error_description", params["error"])[0]
        raise ValueError(f"Sign-in failed: {description}")
    code = params.get("code", [""])[0].strip()
    if code == "":
        raise ValueError("The pasted URL does not contain a sign-in code")
    return code


def _first(value: Any) -> Any:
    """Presets store per-extruder values as lists, JSON arrays or ';'/',' separated strings."""
    if isinstance(value, list):
        return _first(value[0]) if value else None
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith("["):
        try:
            return _first(json.loads(text))
        except ValueError:
            pass
    for separator in (";", ","):
        if separator in text:
            text = text.split(separator, 1)[0].strip()
            break
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text


def _as_str(value: Any) -> str:
    first = _first(value)
    return "" if first is None else str(first)


def _as_int(value: Any) -> int:
    try:
        return int(float(_first(value)))
    except (TypeError, ValueError):
        return 0


def parse_filament_profiles(upserts: list) -> dict[str, dict]:
    """Map filament_id -> filament details for every filament preset in a sync pull."""
    filaments: dict[str, dict] = {}
    for upsert in upserts or []:
        if not isinstance(upsert, dict):
            continue
        content = upsert.get("content")
        if not isinstance(content, dict):
            continue
        filament_id = _as_str(content.get("filament_id"))
        if filament_id == "":
            # Process and machine presets have no filament_id. Neither do some
            # filament presets, but the printer reports trays by id, so those
            # can't be matched to anything.
            continue
        name = _as_str(content.get("name")) or str(upsert.get("name") or filament_id)
        if " @" in name:
            name = name[:name.index(" @")]
        filaments[filament_id] = {
            "name": name,
            "filament_vendor": _as_str(content.get("filament_vendor")),
            "filament_type": _as_str(content.get("filament_type")),
            "nozzle_temperature_range_low": _as_int(content.get("nozzle_temperature_range_low")),
            "nozzle_temperature_range_high": _as_int(content.get("nozzle_temperature_range_high")),
        }
    return filaments


def _base_headers() -> dict[str, str]:
    return {"apikey": ORCA_PUBLISHABLE_KEY, "Content-Type": "application/json"}


def _post_token(session, grant_type: str, body: dict) -> dict:
    url = f"{ORCA_AUTH_URL}{_TOKEN_PATH}?grant_type={grant_type}"
    try:
        response = session.post(url, json=body, headers=_base_headers(), timeout=_REQUEST_TIMEOUT_S)
    except Exception as e:
        raise OrcaCloudError(f"Could not reach Orca Cloud: {e}") from e
    if response.status_code in (400, 401, 403):
        raise OrcaCloudAuthError(f"Orca Cloud rejected the sign-in ({response.status_code})")
    if response.status_code != 200:
        raise OrcaCloudError(f"Orca Cloud sign-in failed ({response.status_code})")
    try:
        payload = response.json()
    except ValueError as e:
        raise OrcaCloudError("Orca Cloud returned an invalid sign-in response") from e
    if not payload.get("access_token") or not payload.get("refresh_token"):
        raise OrcaCloudError("Orca Cloud sign-in response is missing tokens")
    return payload


# One client per config entry, kept across integration reloads. The refresh token
# is single-use, so two clients built from the same stored token would spend it
# twice, and the second would be rejected. Keyed by config entry id.
_SHARED_CLIENTS: dict[str, "OrcaCloud"] = {}
_SHARED_LOCK = threading.Lock()


def get_shared_client(key: str, refresh_token: str) -> "OrcaCloud | None":
    """Return the live client for `key`, creating it from `refresh_token` if needed."""
    if not refresh_token:
        drop_shared_client(key)
        return None
    with _SHARED_LOCK:
        client = _SHARED_CLIENTS.get(key)
        if client is None:
            client = OrcaCloud(refresh_token)
            _SHARED_CLIENTS[key] = client
        return client


def drop_shared_client(key: str) -> None:
    """Forget `key`'s client (unlink or re-link) so its late token rotations go nowhere."""
    with _SHARED_LOCK:
        client = _SHARED_CLIENTS.pop(key, None)
    if client is not None:
        client.set_token_listener(None)


class OrcaCloud:
    def __init__(
        self,
        refresh_token: str,
        on_token_refreshed: Callable[[str], None] | None = None,
        session=None,
    ):
        if not refresh_token:
            raise ValueError("An Orca Cloud refresh token is required")
        self._refresh_token = refresh_token
        self._on_token_refreshed = on_token_refreshed
        self._session = session or requests
        self._access_token = ""
        self._expires_at = 0.0
        # The token rotates on use; never let two threads spend the same one.
        self._lock = threading.Lock()

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    def set_token_listener(self, listener: Callable[[str], None] | None) -> None:
        self._on_token_refreshed = listener

    @staticmethod
    def exchange_code(auth_code: str, code_verifier: str, session=None) -> str:
        """Finish the PKCE sign-in and return the refresh token to store."""
        payload = _post_token(session or requests, "pkce", {"auth_code": auth_code, "code_verifier": code_verifier})
        return payload["refresh_token"]

    def get_profiles(self) -> list[dict]:
        """Return every profile upsert on the account (a full pull, no cursor)."""
        with self._lock:
            if not self._access_token or time.time() >= self._expires_at:
                self._refresh()
            response = self._pull()
            if response.status_code == 401:
                self._refresh()
                response = self._pull()

        if response.status_code == 401:
            raise OrcaCloudAuthError("Orca Cloud rejected the session")
        if response.status_code != 200:
            raise OrcaCloudError(f"Orca Cloud profile sync failed ({response.status_code})")
        try:
            payload = response.json()
        except ValueError as e:
            raise OrcaCloudError("Orca Cloud returned an invalid profile list") from e
        upserts = payload.get("upserts") if isinstance(payload, dict) else None
        return upserts if isinstance(upserts, list) else []

    def get_filament_profiles(self) -> dict[str, dict]:
        return parse_filament_profiles(self.get_profiles())

    def link(self) -> None:
        """Best-effort check of a freshly exchanged session.

        Only a rejected session is fatal. Any other failure is ignored because the
        sign-in code has already been spent, and the session is still worth keeping.
        """
        try:
            LOGGER.debug(f"Orca Cloud linked, {len(self.get_filament_profiles())} custom filaments found.")
        except OrcaCloudAuthError:
            raise
        except OrcaCloudError as e:
            LOGGER.warning(f"Orca Cloud linked but profiles could not be read yet: {e}")

    def _pull(self):
        headers = {**_base_headers(), "Authorization": f"Bearer {self._access_token}"}
        try:
            return self._session.get(f"{ORCA_API_URL}{_SYNC_PULL_PATH}", headers=headers, timeout=_REQUEST_TIMEOUT_S)
        except Exception as e:
            raise OrcaCloudError(f"Could not reach Orca Cloud: {e}") from e

    def _refresh(self) -> None:
        payload = _post_token(self._session, "refresh_token", {"refresh_token": self._refresh_token})
        self._access_token = payload["access_token"]
        expires_in = payload.get("expires_in") or _DEFAULT_EXPIRES_IN_S
        self._expires_at = time.time() + max(0, int(expires_in) - _EXPIRY_SKEW_S)
        self._refresh_token = payload["refresh_token"]
        if self._on_token_refreshed is not None:
            try:
                self._on_token_refreshed(self._refresh_token)
            except Exception as e:
                LOGGER.error(f"Failed to persist the rotated Orca Cloud token: {e}")
