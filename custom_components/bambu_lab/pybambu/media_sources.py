from __future__ import annotations

import ftplib
import hashlib
import json
import os
import random
import re
import socket
import ssl
import struct
import time

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .const import LOGGER


ProgressCallback = Callable[[int], None]
TCP6000_PROBE_TTL_SECONDS = 300
INTERNAL_STORAGES = {"internal", "emmc"}
EXTERNAL_STORAGES = {"", "external", "udisk", "sdcard", "usb"}


class RemoteMediaError(Exception):
    """Raised when a remote media source cannot complete an operation."""


@dataclass(frozen=True)
class RemoteMediaFile:
    name: str
    path: str
    size: int
    media_type: str
    source: str
    storage: str = ""
    modified: datetime | None = None

    @property
    def sort_time(self) -> datetime:
        return self.modified or datetime.fromtimestamp(0, timezone.utc)

    @property
    def basename(self) -> str:
        if self.name:
            return self.name
        normalized = self.path.replace("\\", "/").rstrip("/")
        return normalized.rsplit("/", 1)[-1]


def ordered_unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def canonical_storage(storage: str) -> str:
    normalized = (storage or "").lower()
    if normalized in INTERNAL_STORAGES:
        return "internal"
    if normalized in EXTERNAL_STORAGES:
        return "external"
    return normalized


def storage_cache_segment(storage: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", canonical_storage(storage))


def source_priority(source: str) -> int:
    if source == Tcp6000MediaSource.name:
        return 2
    if source == Ftps990MediaSource.name:
        return 1
    return 0


def dedupe_remote_files(files: Iterable[RemoteMediaFile]) -> list[RemoteMediaFile]:
    """Deduplicate path aliases while preserving distinct storage volumes."""
    by_key: dict[tuple[str, str, int, str], RemoteMediaFile] = {}
    for file in files:
        normalized_path = file.path.replace("\\", "/").strip("/").lower()
        key = (
            canonical_storage(file.storage),
            normalized_path or file.basename.lower(),
            file.size,
            file.media_type,
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = file
            continue

        file_priority = source_priority(file.source)
        existing_priority = source_priority(existing.source)
        if file_priority > existing_priority:
            by_key[key] = file
        elif file_priority == existing_priority and file.sort_time > existing.sort_time:
            by_key[key] = file

    return list(by_key.values())


def sort_newest_first(files: Iterable[RemoteMediaFile]) -> list[RemoteMediaFile]:
    return sorted(
        files,
        key=lambda file: (file.sort_time, source_priority(file.source), file.size),
        reverse=True,
    )


class RemoteMediaSource:
    name = "remote"

    def list_files(
        self,
        media_type: str,
        extensions: list[str],
        search_paths: list[str] | None = None,
    ) -> list[RemoteMediaFile]:
        raise NotImplementedError

    def download_file(
        self,
        remote_file: RemoteMediaFile,
        local_path: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> int:
        raise NotImplementedError

    def close(self) -> None:
        pass


def _parse_ftp_timestamp(timestamp_str: str, has_year: bool) -> datetime:
    if has_year:
        timestamp = datetime.strptime(timestamp_str, "%b %d %Y")
        return timestamp.replace(tzinfo=timezone.utc)

    timestamp = datetime.strptime(timestamp_str, "%b %d %H:%M")
    timestamp = timestamp.replace(tzinfo=timezone.utc)
    utc_time_now = datetime.now().astimezone(timezone.utc)
    timestamp = timestamp.replace(year=utc_time_now.year)

    delta = timestamp - utc_time_now
    six_months = timedelta(days=190)
    if delta > six_months:
        timestamp = timestamp.replace(year=utc_time_now.year - 1)
    elif delta < -six_months:
        timestamp = timestamp.replace(year=utc_time_now.year + 1)
    return timestamp


def _join_ftp_path(path: str, filename: str) -> str:
    if path == "/":
        return f"/{filename}"
    return f"{path.rstrip('/')}/{filename}"


def _parse_ftp_list_line(
    media_type: str,
    path: str,
    line: str,
    extensions: list[str],
) -> RemoteMediaFile | None:
    pattern_with_time = r"^\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\S+\s+\d+\s+\d+:\d+)\s+(.+)$"
    pattern_with_year = r"^\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\S+\s+\d+\s+\d+)\s+(.+)$"

    for pattern, has_year in ((pattern_with_time, False), (pattern_with_year, True)):
        match = re.match(pattern, line)
        if not match:
            continue
        size_str, timestamp_str, filename = match.groups()
        extension = os.path.splitext(filename)[1].lower()
        if extension not in extensions:
            return None
        return RemoteMediaFile(
            name=filename,
            path=_join_ftp_path(path, filename),
            size=int(size_str),
            media_type=media_type,
            source=Ftps990MediaSource.name,
            storage="external",
            modified=_parse_ftp_timestamp(timestamp_str, has_year),
        )

    LOGGER.debug(f"UNEXPECTED FTP LIST LINE FORMAT: '{line}'")
    return None


class Ftps990MediaSource(RemoteMediaSource):
    name = "ftps990"

    def __init__(self, client):
        self._client = client
        self._ftp: ftplib.FTP | None = None

    def _connection(self):
        if self._ftp is None:
            self._ftp = self._client.ftp_connection()
        return self._ftp

    def list_files(
        self,
        media_type: str,
        extensions: list[str],
        search_paths: list[str] | None = None,
    ) -> list[RemoteMediaFile]:
        if not self._client.ftp_enabled:
            return []

        paths = search_paths
        if paths is None:
            if media_type == "timelapse":
                paths = ["/timelapse"]
            elif media_type == "model":
                paths = ["/cache/", "/"]
            else:
                paths = ["/"]

        ftp = self._connection()
        files: list[RemoteMediaFile] = []
        for path in paths:
            try:
                LOGGER.debug(f"FTPS list {media_type} in {path}")
                ftp.retrlines(
                    f"LIST {path}",
                    lambda line: files.append(file)
                    if (file := _parse_ftp_list_line(media_type, path, line, extensions)) is not None
                    else None,
                )
            except Exception as e:
                LOGGER.debug(f"FTPS list failed for {path}: {type(e)} Args: {e}")
        return files

    def download_file(
        self,
        remote_file: RemoteMediaFile,
        local_path: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> int:
        ftp = self._connection()
        expected_size = int(remote_file.size or ftp.size(remote_file.path))
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        total_downloaded = 0
        last_percentage = -1

        with open(target, "wb") as file:
            def write_with_progress(data: bytes) -> None:
                nonlocal total_downloaded, last_percentage
                file.write(data)
                total_downloaded += len(data)
                if expected_size > 0 and progress_callback:
                    percentage = int((total_downloaded / expected_size) * 100)
                    if percentage != last_percentage:
                        progress_callback(percentage)
                        last_percentage = percentage

            ftp.retrbinary(f"RETR {remote_file.path}", write_with_progress)
            file.flush()

        local_size = target.stat().st_size
        if expected_size > 0 and local_size != expected_size:
            raise RemoteMediaError(
                f"FTPS download size mismatch for {remote_file.path}: {local_size} != {expected_size}"
            )
        return local_size

    def close(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.quit()
            except Exception:
                pass
            self._ftp = None


MAGIC_LOGIN = 0x0101013F
MAGIC_CTRL = 0x0102013F
MTYPE_CTRL_SETUP = 12291
MTYPE_CTRL_JSON = 12289
RESULT_CONTINUE = 1
RESULT_OK = 0


def _build_frame_header(payload_len: int, magic: int, seq: int) -> bytes:
    header = bytearray(16)
    struct.pack_into("<I", header, 0, payload_len)
    struct.pack_into("<I", header, 4, magic)
    struct.pack_into("<I", header, 8, seq)
    return bytes(header)


def _build_login_payload(username: str, access_code: str) -> bytes:
    user = username.encode("ascii", errors="replace")[:8].ljust(8, b"\0")
    code = access_code.encode("ascii", errors="replace")[:8].ljust(8, b"\0")
    return user + code


def _build_ctrl_setup_json(pid: str) -> bytes:
    payload = {
        "sequence": 0,
        "mtype": MTYPE_CTRL_SETUP,
        "req": {
            "t_av": 1,
            "mtype": MTYPE_CTRL_JSON,
            "peer_t": 3,
            "pid": pid,
            "ver": "02.03.00.00",
        },
    }
    return json.dumps(payload, separators=(",", ":")).encode("ascii")


def _wrap_ctrl_json(obj: dict[str, Any]) -> bytes:
    if "mtype" not in obj:
        obj = {"mtype": MTYPE_CTRL_JSON, **obj}
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def _json_prefix_end(data: bytes) -> int | None:
    if not data.startswith(b"{"):
        return None

    depth = 0
    in_str = False
    escaped = False
    for idx, byte in enumerate(data):
        if in_str:
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                in_str = False
            continue
        if byte == ord('"'):
            in_str = True
        elif byte == ord("{"):
            depth += 1
        elif byte == ord("}"):
            depth -= 1
            if depth == 0:
                return idx + 1
    return None


def _split_json_and_binary(data: bytes) -> tuple[dict[str, Any] | None, bytes]:
    json_end = _json_prefix_end(data)
    if json_end is None:
        return None, data

    try:
        payload = json.loads(data[:json_end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, data

    binary_start = json_end
    if data[binary_start:binary_start + 2] == b"\n\n":
        binary_start += 2
    elif data[binary_start:binary_start + 4] == b"\r\n\r\n":
        binary_start += 4

    if not isinstance(payload, dict):
        return None, data[binary_start:]
    return payload, data[binary_start:]


def _parse_tcp6000_modified(item: dict[str, Any]) -> datetime | None:
    timestamp = item.get("time")
    try:
        if timestamp:
            return datetime.fromtimestamp(int(timestamp), timezone.utc)
    except (TypeError, ValueError, OSError):
        pass

    date_value = item.get("date")
    if isinstance(date_value, str) and date_value:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(date_value[:19], fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    filename = str(item.get("name") or item.get("file") or item.get("filename") or item.get("path") or "")
    match = re.search(
        r"(\d{4})[-_](\d{2})[-_](\d{2})[ _-](\d{2})[-_](\d{2})[-_](\d{2})",
        filename,
    )
    if match:
        try:
            year, month, day, hour, minute, second = (int(value) for value in match.groups())
            return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


class Tcp6000MediaSource(RemoteMediaSource):
    name = "tcp6000"

    def __init__(self, client, connect_timeout: float = 5.0, command_timeout: float = 20.0):
        self._client = client
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._ssl: ssl.SSLSocket | None = None
        self._frame_seq = random.randint(1, 0x7FFFFFFF)
        self._cmd_seq = 1
        client_storages = getattr(client, "tcp6000_media_storages", None)
        if client_storages:
            self._ability_storages = list(client_storages)
        elif getattr(client, "tcp6000_media_supported", None) is True:
            self._ability_storages = []
        else:
            self._ability_storages: list[str] | None = None

    def _next_frame_seq(self) -> int:
        seq = self._frame_seq
        self._frame_seq += 1
        return seq

    def _next_cmd_seq(self) -> int:
        seq = self._cmd_seq
        self._cmd_seq += 1
        return seq

    @property
    def _pid(self) -> str:
        return f"{self._frame_seq & 0xFFFFFFFF:08x}"

    def _connect(self) -> None:
        if self._ssl is not None:
            return
        if not self._client.ftp_enabled:
            raise RemoteMediaError("TCP 6000 media is disabled because no printer host is configured")
        if self._client._access_code == "":
            raise RemoteMediaError("TCP 6000 media requires an access code")

        host = self._client._device.info.ip_address
        raw = socket.create_connection((host, 6000), timeout=self._connect_timeout)
        try:
            self._ssl = self._client.local_tls_context.wrap_socket(
                raw,
                server_hostname=self._client._serial or host,
            )
            self._ssl.settimeout(self._command_timeout)
            self._handshake()
        except Exception:
            if self._ssl is not None:
                try:
                    self._ssl.close()
                except Exception:
                    pass
            try:
                raw.close()
            except Exception:
                pass
            self._ssl = None
            raise

    def _send_frame(self, magic: int, payload: bytes) -> None:
        if self._ssl is None:
            raise RemoteMediaError("TCP 6000 session is not connected")
        self._ssl.sendall(_build_frame_header(len(payload), magic, self._next_frame_seq()))
        if payload:
            self._ssl.sendall(payload)

    def _read_exact(self, length: int, timeout: float | None = None) -> bytes:
        if self._ssl is None:
            raise RemoteMediaError("TCP 6000 session is not connected")

        original_timeout = self._ssl.gettimeout()
        if timeout is not None:
            self._ssl.settimeout(timeout)
        try:
            data = bytearray()
            while len(data) < length:
                chunk = self._ssl.recv(length - len(data))
                if not chunk:
                    raise RemoteMediaError("TCP 6000 connection closed by printer")
                data.extend(chunk)
            return bytes(data)
        finally:
            if timeout is not None:
                self._ssl.settimeout(original_timeout)

    def _read_frame(self, timeout: float | None = None) -> tuple[int, int, bytes]:
        header = self._read_exact(16, timeout)
        payload_len = struct.unpack_from("<I", header, 0)[0]
        magic = struct.unpack_from("<I", header, 4)[0]
        sequence = struct.unpack_from("<I", header, 8)[0]
        payload = self._read_exact(payload_len, timeout) if payload_len else b""
        return magic, sequence, payload

    def _handshake(self) -> None:
        self._send_frame(MAGIC_LOGIN, _build_login_payload("bblp", self._client._access_code))
        try:
            self._read_frame(timeout=2.0)
        except Exception as e:
            raise RemoteMediaError(f"TCP 6000 login failed: {e}") from e

        self._send_frame(MAGIC_CTRL, _build_ctrl_setup_json(self._pid))
        try:
            _magic, _seq, payload = self._read_frame(timeout=3.0)
            reply, _binary = _split_json_and_binary(payload)
        except Exception as e:
            raise RemoteMediaError(f"TCP 6000 setup failed: {e}") from e

        if not reply or int(reply.get("result", -1)) != RESULT_OK:
            raise RemoteMediaError(f"TCP 6000 setup failed with reply {reply}")

    def _send_ctrl_request(self, cmdtype: int, req: dict[str, Any]) -> int:
        self._connect()
        sequence = self._next_cmd_seq()
        self._send_frame(
            MAGIC_CTRL,
            _wrap_ctrl_json({"cmdtype": cmdtype, "sequence": sequence, "req": req}),
        )
        return sequence

    def _read_matching_reply(
        self,
        cmdtype: int,
        sequence: int,
        timeout: float | None = None,
    ) -> tuple[dict[str, Any], bytes]:
        deadline = time.monotonic() + (timeout if timeout is not None else self._command_timeout)
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            _magic, _seq, payload = self._read_frame(timeout=remaining)
            reply, binary = _split_json_and_binary(payload)
            if not reply:
                continue
            if int(reply.get("sequence", -1)) != sequence:
                LOGGER.debug(f"Skipping stale TCP 6000 frame for sequence {reply.get('sequence')}")
                continue
            if int(reply.get("cmdtype", cmdtype)) != cmdtype:
                LOGGER.debug(f"Skipping stale TCP 6000 frame for cmdtype {reply.get('cmdtype')}")
                continue
            return reply, binary
        raise RemoteMediaError(f"TCP 6000 timed out waiting for cmdtype={cmdtype} sequence={sequence}")

    def probe(self) -> list[str]:
        self._connect()
        try:
            self._ability_storages = self.media_ability()
        except Exception as e:
            LOGGER.debug(f"TCP 6000 media ability failed after setup, using storage fallbacks: {e}")
            self._ability_storages = []
        return self._ability_storages

    def media_ability(self) -> list[str]:
        sequence = self._send_ctrl_request(
            7,
            {"peer": "studio", "api_version": 2},
        )
        reply, _binary = self._read_matching_reply(7, sequence, timeout=8.0)
        if int(reply.get("result", -1)) != RESULT_OK:
            raise RemoteMediaError(f"TCP 6000 media ability failed with result={reply.get('result')}")

        reply_body = reply.get("reply")
        storages: list[str] = []
        if isinstance(reply_body, list):
            storages = [str(item) for item in reply_body]
        elif isinstance(reply_body, dict):
            for key in ("upload_storage", "storage", "storage_list", "storages"):
                value = reply_body.get(key)
                if isinstance(value, list):
                    storages = [str(item) for item in value]
                    break
            if not storages and isinstance(reply_body.get("ability"), dict):
                ability = reply_body["ability"]
                for key in ("upload_storage", "storage", "storage_list", "storages"):
                    value = ability.get(key)
                    if isinstance(value, list):
                        storages = [str(item) for item in value]
                        break

        self._ability_storages = ordered_unique(storages)
        LOGGER.debug(f"TCP 6000 media ability storages: {self._ability_storages}")
        return self._ability_storages

    def _storage_candidates(self, media_type: str) -> list[str]:
        ability = self._ability_storages
        if ability is None:
            try:
                ability = self.media_ability()
            except Exception as e:
                LOGGER.debug(f"TCP 6000 media ability probe failed, using storage fallbacks: {e}")
                ability = []

        candidates: list[str] = []
        for storage in ability:
            storage = (storage or "").lower()
            if storage in INTERNAL_STORAGES:
                candidates.extend(["internal", "emmc"] if media_type != "model" else ["emmc", "internal"])
            elif storage in EXTERNAL_STORAGES:
                candidates.extend(["udisk", "sdcard", "usb", "external", ""])
            else:
                candidates.append(storage)

        if media_type == "model":
            candidates.extend(["emmc", "internal", "udisk", "sdcard", "usb", "external", ""])
        else:
            candidates.extend(["internal", "emmc", "udisk", "sdcard", "usb", "external", ""])
        return ordered_unique(candidates)

    def list_files(
        self,
        media_type: str,
        extensions: list[str],
        search_paths: list[str] | None = None,
    ) -> list[RemoteMediaFile]:
        files: list[RemoteMediaFile] = []
        for storage in self._storage_candidates(media_type):
            req: dict[str, Any] = {
                "type": media_type,
                "api_version": 2,
                "notify": "DETAIL",
            }
            if storage:
                req["storage"] = storage

            try:
                sequence = self._send_ctrl_request(1, req)
                reply, _binary = self._read_matching_reply(1, sequence, timeout=15.0)
                result = int(reply.get("result", -1))
                if result != RESULT_OK:
                    LOGGER.debug(f"TCP 6000 LIST_INFO failed for {media_type}/{storage}: result={result}")
                    continue
                raw_files = (reply.get("reply") or {}).get("file_lists", [])
                if not isinstance(raw_files, list):
                    continue

                for item in raw_files:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or item.get("file") or item.get("filename") or "")
                    path = str(item.get("path") or "")
                    basename = name or path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
                    extension = os.path.splitext(basename)[1].lower()
                    if extension not in extensions:
                        continue
                    item_storage = str(item.get("storage") or "")
                    files.append(
                        RemoteMediaFile(
                            name=basename,
                            path=path or basename,
                            size=int(item.get("size") or 0),
                            media_type=media_type,
                            source=self.name,
                            storage=item_storage or storage or "external",
                            modified=_parse_tcp6000_modified(item),
                        )
                    )
            except Exception as e:
                LOGGER.debug(f"TCP 6000 list failed for {media_type}/{storage}: {type(e)} Args: {e}")

        return dedupe_remote_files(files)

    @staticmethod
    def _download_request(remote_file: RemoteMediaFile) -> dict[str, Any]:
        normalized_path = remote_file.path.replace("\\", "/")
        if normalized_path and (
            normalized_path.startswith("/")
            or normalized_path.startswith("mem:")
            or "/" in normalized_path
            or normalized_path != remote_file.basename
        ):
            return {"path": normalized_path, "offset": 0}
        return {"file": remote_file.basename, "offset": 0}

    def download_file(
        self,
        remote_file: RemoteMediaFile,
        local_path: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> int:
        sequence = self._send_ctrl_request(4, self._download_request(remote_file))
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        md5 = hashlib.md5()
        bytes_written = 0
        expected_total = int(remote_file.size or 0)
        expected_md5 = ""
        last_percentage = -1

        with open(target, "wb") as file:
            while True:
                reply, chunk = self._read_matching_reply(4, sequence, timeout=120.0)
                response = reply.get("reply") or {}
                if chunk and not response.get("mem_dl_param_size"):
                    file.write(chunk)
                    md5.update(chunk)
                    bytes_written += len(chunk)

                total = int(response.get("total") or expected_total or 0)
                if total > 0 and progress_callback:
                    percentage = int((bytes_written / total) * 100)
                    if percentage != last_percentage:
                        progress_callback(min(100, percentage))
                        last_percentage = percentage

                result = int(reply.get("result", -1))
                if result == RESULT_CONTINUE:
                    continue
                if result != RESULT_OK:
                    raise RemoteMediaError(
                        f"TCP 6000 download failed for {remote_file.path}: result={result}"
                    )

                expected_total = int(response.get("total") or expected_total or bytes_written)
                expected_md5 = str(response.get("file_md5") or "").lower()
                break
            file.flush()

        if expected_total > 0 and bytes_written != expected_total:
            raise RemoteMediaError(
                f"TCP 6000 download size mismatch for {remote_file.path}: "
                f"{bytes_written} != {expected_total}"
            )
        if remote_file.size > 0 and bytes_written != remote_file.size:
            raise RemoteMediaError(
                f"TCP 6000 download remote size mismatch for {remote_file.path}: "
                f"{bytes_written} != {remote_file.size}"
            )
        if expected_md5 and md5.hexdigest().lower() != expected_md5:
            raise RemoteMediaError(
                f"TCP 6000 download md5 mismatch for {remote_file.path}: "
                f"{md5.hexdigest().lower()} != {expected_md5}"
            )
        return bytes_written

    def close(self) -> None:
        if self._ssl is not None:
            try:
                self._ssl.close()
            except Exception:
                pass
            self._ssl = None
