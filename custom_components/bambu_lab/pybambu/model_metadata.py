"""Bounded stored-model lookup when MQTT reports a title instead of a filename."""
from __future__ import annotations

import hashlib
import io
import json
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from .const import LOGGER
from .media_sources import RemoteMediaFile, Tcp6000MediaSource

MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_MODEL_CANDIDATES = 250
LOOKUP_SECONDS = 20
METADATA_MEMBERS = ("3D/3dmodel.model", "Metadata/slice_info.config")


def job_identity(job) -> tuple:
    return (job.task_id, job._subtask_name, job.gcode_file, job.plate_idx,
            tuple(getattr(job, "ams_mapping", ()) or ()),
            tuple(getattr(job, "_tray_mapping", ()) or ()))


def normalized_title(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


class _NoDoctype(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("Metadata DTDs are unsupported")


def _xml(data: bytes):
    return ET.fromstring(data, parser=ET.XMLParser(target=_NoDoctype()))


def _member(archive: ZipFile, name: str, limit=MAX_METADATA_BYTES) -> bytes:
    entries = [entry for entry in archive.infolist() if entry.filename == name]
    if len(entries) != 1 or entries[0].file_size > limit:
        raise ValueError("Missing, duplicate or oversized metadata member")
    return archive.read(entries[0])


def _identity(archive: ZipFile) -> tuple[str, dict[int, bytes]]:
    # A valid unsliced project is not a match, rather than a transient IO failure.
    if any(name not in archive.namelist() for name in METADATA_MEMBERS):
        return "", {}
    model = _xml(_member(archive, METADATA_MEMBERS[0]))
    titles = [node.text or "" for node in model
              if node.tag.rsplit("}", 1)[-1] == "metadata" and node.get("name") == "Title"]
    if not titles:
        return "", {}
    if len(titles) != 1:
        raise ValueError("Ambiguous model title")
    slices = _xml(_member(archive, METADATA_MEMBERS[1]))
    plates = {}
    for plate in slices.findall("plate"):
        indices = [node.get("value", "") for node in plate.findall("metadata")
                   if node.get("key") == "index"]
        if len(indices) != 1 or not indices[0].isdigit() or not 0 < int(indices[0]) <= 1000:
            raise ValueError("Invalid plate index")
        index = int(indices[0])
        if index in plates:
            raise ValueError("Duplicate plate index")
        plates[index] = ET.tostring(plate)
    return titles[0], plates


def read_identity(payload: bytes) -> tuple[str, tuple[int, ...]]:
    if len(payload) > MAX_METADATA_BYTES:
        raise ValueError("Metadata exceeds limit")
    with ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist()) > 32:
            raise ValueError("Too many metadata members")
        title, plates = _identity(archive)
        return title, tuple(plates)


def _fingerprint(archive: ZipFile, title: str, plate: int) -> tuple[str, str]:
    observed, plates = _identity(archive)
    if normalized_title(observed) != normalized_title(title) or plate not in plates:
        raise ValueError("Model title or plate changed")
    checksum = _member(archive, f"Metadata/plate_{plate}.gcode.md5", 64).decode("ascii").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", checksum):
        raise ValueError("Invalid plate program checksum")
    return checksum, hashlib.sha256(plates[plate]).hexdigest()


def read_fingerprint(payload: bytes, title: str, plate: int) -> tuple[str, str]:
    # Reuse the bounded archive checks before reading the selected program checksum.
    read_identity(payload)
    with ZipFile(io.BytesIO(payload)) as archive:
        return _fingerprint(archive, title, plate)


def file_identity(file: RemoteMediaFile) -> str:
    return json.dumps([file.storage, file.path, file.name, file.size, str(file.modified)])


@dataclass(frozen=True)
class StoredModelSelection:
    file: RemoteMediaFile
    job: tuple
    title: str
    plate: int
    fingerprint: tuple[str, str]

    def validate_archive(self, filename: str | Path) -> None:
        """Check the downloaded bytes, including the actual selected program."""
        with ZipFile(filename) as archive:
            if _fingerprint(archive, self.title, self.plate) != self.fingerprint:
                raise ValueError("Downloaded model metadata changed")
            entries = [entry for entry in archive.infolist()
                       if entry.filename == f"Metadata/plate_{self.plate}.gcode"]
            if len(entries) != 1 or entries[0].file_size > 512 * 1024 * 1024:
                raise ValueError("Missing, duplicate or oversized plate program")
            digest = hashlib.md5(usedforsecurity=False)
            with archive.open(entries[0]) as program:
                for chunk in iter(lambda: program.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != self.fingerprint[0]:
                raise ValueError("Downloaded plate program changed")


class StoredModelLookup:
    """Resume bounded lookups for one job; never expose this cache in diagnostics."""

    def __init__(self):
        self.job = None
        self.listing = None
        self.identities = {}
        self.fingerprints = {}
        self.started = 0

    def select(self, job, source: Tcp6000MediaSource) -> StoredModelSelection | None:
        stamp = job_identity(job)
        title, plate = normalized_title(job._subtask_name), job.plate_idx
        if (not title or type(plate) is not int or not 0 < plate <= 1000
                or job.gcode_file.lower().endswith(".3mf")):
            return None  # An explicit current filename must not be replaced by a title guess.
        deadline = time.monotonic() + LOOKUP_SECONDS
        try:
            files = source.list_files("model", [".3mf"], require_complete=True,
                                      timeout=max(0.1, deadline-time.monotonic()))
            if not files or len(files) > MAX_MODEL_CANDIDATES:
                return None
            listing = frozenset(file_identity(file) for file in files)
            if self.job != stamp or self.listing != listing or time.monotonic()-self.started > 60:
                self.job, self.listing = stamp, listing
                self.started = time.monotonic()
                self.identities.clear()
                self.fingerprints.clear()
            matches = []
            for file in files:
                key = file_identity(file)
                if key not in self.identities:
                    if time.monotonic() >= deadline:
                        return None
                    self.identities[key] = read_identity(source.model_metadata(
                        file, timeout=max(0.1, deadline-time.monotonic())))
                    self.started = time.monotonic()
                observed_title, plates = self.identities[key]
                if normalized_title(observed_title) != title or plate not in plates:
                    continue
                if key not in self.fingerprints:
                    if time.monotonic() >= deadline:
                        return None
                    self.fingerprints[key] = read_fingerprint(source.model_metadata(
                        file, plate, timeout=max(0.1, deadline-time.monotonic())), title, plate)
                    self.started = time.monotonic()
                matches.append(file)
            if not matches or len({self.fingerprints[file_identity(file)] for file in matches}) != 1:
                return None
            # A new file during the scan may introduce another same-title slice.
            if time.monotonic() >= deadline:
                return None
            refreshed = source.list_files("model", [".3mf"], require_complete=True,
                                          timeout=max(0.1, deadline-time.monotonic()))
            if listing != frozenset(file_identity(file) for file in refreshed) or stamp != job_identity(job):
                self.listing = None
                return None
            selected = matches[0]
            self.listing = None  # Never carry a completed lookup into another download attempt.
            return StoredModelSelection(selected, stamp, title, plate, self.fingerprints[file_identity(selected)])
        except Exception as error:
            LOGGER.debug("Stored model metadata lookup unavailable: %s", type(error).__name__)
            return None
