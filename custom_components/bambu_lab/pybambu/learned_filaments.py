"""Custom filament details learned from print files.

In LAN mode there is no Bambu cloud to ask for the user's custom filament
presets, so AMS trays holding a custom filament only report an opaque
tray_info_idx (e.g. "P9816594"). Every 3mf the slicer sends to the printer
embeds Metadata/project_settings.config, which lists each filament's id
alongside its preset name, vendor and type. We record those as prints are
observed and persist them so the names survive restarts.

One store exists per file path and is shared by every printer in the process,
so a filament learned from a print on one printer names trays on all of them.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from zipfile import ZipFile

from .const import FILAMENT_NAMES, LOGGER

PROJECT_SETTINGS_ENTRY = "Metadata/project_settings.config"
_STORE_VERSION = 1


@dataclass(frozen=True)
class FilamentInfo:
    name: str
    filament_vendor: str
    filament_type: str
    filament_density: float
    nozzle_temperature: int
    nozzle_temperature_range_high: int
    nozzle_temperature_range_low: int


def _strip_printer_suffix(name: str) -> str:
    # Presets are named "<filament> @<printer> <nozzle>"; only the filament part is useful.
    return name.split(" @", 1)[0].strip()


def _item(settings: dict, key: str, index: int) -> str:
    values = settings.get(key)
    if not isinstance(values, list) or index >= len(values):
        return ""
    value = values[index]
    return value.strip() if isinstance(value, str) else ""


def _number(value: str, cast, default=0):
    try:
        return cast(float(value))
    except (TypeError, ValueError):
        return default


def parse_project_settings(payload: bytes) -> dict[str, FilamentInfo]:
    """Return {filament_id: FilamentInfo} for the custom filaments in a project_settings.config."""
    try:
        settings = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        LOGGER.debug("project_settings.config is not valid JSON")
        return {}
    if not isinstance(settings, dict):
        return {}

    ids = settings.get("filament_ids")
    if not isinstance(ids, list):
        return {}

    result = {}
    for index, filament_id in enumerate(ids):
        if not isinstance(filament_id, str) or not filament_id or filament_id in FILAMENT_NAMES:
            # Bambu's own filaments already have names; only custom ones need learning.
            continue
        name = _strip_printer_suffix(_item(settings, "filament_settings_id", index))
        if not name:
            continue
        result[filament_id] = FilamentInfo(
            name=name,
            filament_vendor=_item(settings, "filament_vendor", index),
            filament_type=_item(settings, "filament_type", index),
            filament_density=_number(_item(settings, "filament_density", index), float),
            nozzle_temperature=0,
            nozzle_temperature_range_high=_number(_item(settings, "nozzle_temperature_range_high", index), int),
            nozzle_temperature_range_low=_number(_item(settings, "nozzle_temperature_range_low", index), int),
        )
    return result


class LearnedFilamentStore:
    """Thread-safe, optionally file-backed map of filament id -> FilamentInfo."""

    def __init__(self, path: str | None):
        self._path = path
        self._lock = threading.Lock()
        self._filaments: dict[str, FilamentInfo] = self._read_file()

    @property
    def filaments(self) -> dict[str, FilamentInfo]:
        with self._lock:
            return dict(self._filaments)

    def learn_from_3mf(self, archive: ZipFile) -> bool:
        if PROJECT_SETTINGS_ENTRY not in archive.namelist():
            LOGGER.debug("3mf has no project_settings.config; no filaments to learn")
            return False
        return self.learn_from_project_settings(archive.read(PROJECT_SETTINGS_ENTRY))

    def learn_from_project_settings(self, payload: bytes) -> bool:
        """Record custom filaments from a project_settings.config. Returns True if anything changed."""
        learned = parse_project_settings(payload)
        with self._lock:
            # Re-read so entries saved by another HA instance sharing the file are kept.
            current = {**self._filaments, **self._read_file()}
            merged = {**current, **learned}
            if merged == self._filaments:
                return False
            self._filaments = merged
            self._write_file(merged)
        LOGGER.debug(f"Learned custom filaments: {sorted(learned)}")
        return True

    def _read_file(self) -> dict[str, FilamentInfo]:
        if not self._path or not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            return {
                filament_id: FilamentInfo(**fields)
                for filament_id, fields in data.get("filaments", {}).items()
            }
        except (OSError, ValueError, TypeError, AttributeError) as e:
            LOGGER.warning(f"Ignoring unreadable learned filament file {self._path}: {e}")
            return {}

    def _write_file(self, filaments: dict[str, FilamentInfo]) -> None:
        if not self._path:
            return
        payload = {
            "version": _STORE_VERSION,
            "filaments": {filament_id: asdict(info) for filament_id, info in sorted(filaments.items())},
        }
        directory = os.path.dirname(self._path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            # Write then rename so a crash or concurrent reader never sees a partial file.
            fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".learned_filaments.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                os.replace(tmp_path, self._path)
            except BaseException:
                os.unlink(tmp_path)
                raise
        except OSError as e:
            LOGGER.error(f"Failed to save learned filaments to {self._path}: {e}")


_stores: dict[str, LearnedFilamentStore] = {}
_stores_lock = threading.Lock()


def get_learned_filament_store(path: str | None) -> LearnedFilamentStore:
    """Return the store shared by every client using `path`; a private in-memory one when path is None."""
    if not path:
        return LearnedFilamentStore(None)
    key = os.path.abspath(path)
    with _stores_lock:
        if key not in _stores:
            _stores[key] = LearnedFilamentStore(key)
        return _stores[key]
