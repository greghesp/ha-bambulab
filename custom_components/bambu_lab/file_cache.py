"""Where the per-printer file cache lives, and moving it out of www/.

The cache used to live under <config>/www/media/ha-bambulab/<serial>. Home
Assistant serves <config>/www at /local/ with no authentication, so cached
print files (.3mf models, slicer settings, thumbnails) and timelapses could be
downloaded by anyone who could reach HA (#2167). The cache now lives in the
local media directory, which is only reachable through authenticated APIs
(the integration's own /api/bambu_lab/file_cache view, or the media browser).

This module deliberately has no Home Assistant imports so it can be unit
tested without an HA install.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

LOGGER = logging.getLogger(__name__)

CACHE_DIR_NAME = "ha-bambulab"
LEGACY_RELATIVE_ROOT = Path("www") / "media" / CACHE_DIR_NAME


def cache_root(media_dir: str | None, config_dir: str) -> Path:
    """Root of the file cache: <local media dir>/ha-bambulab.

    Falls back to <config>/media when no "local" media dir is configured, which
    is also Home Assistant's own default for that media dir outside HAOS.
    """
    base = Path(media_dir) if media_dir else Path(config_dir) / "media"
    return base / CACHE_DIR_NAME


def legacy_cache_dir(config_dir: str, serial: str) -> Path:
    """The old, publicly served cache location for a printer."""
    return Path(config_dir) / LEGACY_RELATIVE_ROOT / serial


def migrate_legacy_cache(legacy_dir: Path, new_dir: Path) -> None:
    """Move a printer's cache out of www/ and delete the public copy.

    Files already present at the destination win, so a partial earlier
    migration never overwrites newer data. Anything that cannot be moved is
    still removed from www/, since leaving it there keeps it publicly readable
    and the integration re-downloads what it needs.
    """
    if not legacy_dir.is_dir():
        return

    LOGGER.info("Moving Bambu Lab file cache from '%s' to '%s'", legacy_dir, new_dir)
    for src in sorted(p for p in legacy_dir.rglob("*") if p.is_file()):
        dest = new_dir / src.relative_to(legacy_dir)
        if dest.exists():
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
        except OSError as err:
            LOGGER.warning("Could not move cached file '%s': %s", src, err)

    shutil.rmtree(legacy_dir, ignore_errors=True)
    if legacy_dir.exists():
        LOGGER.error(
            "Could not remove old Bambu Lab file cache '%s'. It is served publicly at "
            "/local/ and should be deleted manually.", legacy_dir)
        return

    # Tidy up the ha-bambulab folder we created once the last printer has moved.
    # www/ and www/media are left alone as the user may use them for other things.
    try:
        legacy_dir.parent.rmdir()
    except OSError:
        pass
