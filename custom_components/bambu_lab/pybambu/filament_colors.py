"""Names for the colors of Bambu Lab filaments.

The table comes from Bambu Studio, see scripts/fetch_filament_colors_github.py.
"""
import re

from pathlib import Path

from .const import load_dict

FILAMENT_COLORS = load_dict(Path(__file__).with_name('filament_colors.json'))

# tray_id_name as stored on the RFID tag: material id and color code, e.g. "A00-W1".
_TRAY_ID_NAME = re.compile(r"([A-Z]+\d+)-([A-Z]+\d+)")


def _color_key(colors: list[str]) -> tuple[str, ...]:
    return tuple(sorted(str(color).upper() for color in colors))


def _normalize_code(code: str) -> str:
    """Newer firmware zero-pads the number: "W1" and "W01" are the same color."""
    return re.sub(r"(?<=[A-Z])0+(?=\d)", "", code)


_NAME_BY_COLORS = {
    (filament_id, _color_key(entry["colors"])): entry["name"]
    for filament_id, entries in FILAMENT_COLORS.items() for entry in entries
}
_NAME_BY_CODE = {
    (filament_id, _normalize_code(entry["code"])): entry["name"]
    for filament_id, entries in FILAMENT_COLORS.items() for entry in entries
}


def get_filament_color_name(filament_id: str, colors: list[str], tray_id_name: str = "") -> str | None:
    """Return Bambu Lab's English name for a filament color, or None if it has none.

    Colors are RRGGBBAA. They are matched exactly first, as Bambu Studio does. Spools made
    before Bambu Lab revised a color carry the old value, so fall back to the color code
    from the RFID tag.
    """
    name = _NAME_BY_COLORS.get((filament_id, _color_key(colors)))
    if name is not None:
        return name

    match = _TRAY_ID_NAME.fullmatch(tray_id_name) if isinstance(tray_id_name, str) else None
    if match is None or filament_id != f"GF{match[1]}":
        return None
    return _NAME_BY_CODE.get((filament_id, _normalize_code(match[2])))
