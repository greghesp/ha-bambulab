"""
Script to fetch Bambu Lab's filament color names from the BambuStudio GitHub repository
and save them to custom_components/bambu_lab/pybambu/filament_colors.json.
"""

import json
import urllib.request

from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/bambulab/BambuStudio/master/"
    "resources/profiles/BBL/filament/filaments_color_codes.json"
)
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "bambu_lab" / "pybambu" / "filament_colors.json"
)


def convert(source: dict) -> dict[str, list[dict]]:
    """Reduce Bambu Studio's table to the English name of each color, per filament id."""
    result = {}
    for entry in source["data"]:
        result.setdefault(entry["fila_id"], []).append({
            "code": entry["color_code"],
            "colors": [color.lstrip("#").upper() for color in entry["fila_color"]],
            "name": entry["fila_color_name"]["en"],
        })
    return {
        filament_id: sorted(entries, key=lambda entry: entry["code"])
        for filament_id, entries in sorted(result.items())
    }


def main() -> None:
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        source = json.load(response)
    colors = convert(source)
    with open(OUTPUT_PATH, "w", newline="\n") as file:
        json.dump(colors, file, indent=2)
        file.write("\n")
    print(f"Wrote {sum(len(entries) for entries in colors.values())} colors to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
