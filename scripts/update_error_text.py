"""Update the HMS error texts from the Bambu servers."""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from pathlib import Path

INTEGRATION_DIR = Path(__file__).parent.parent.joinpath("custom_components", "bambu_lab")
TRANSLATIONS_DIR = INTEGRATION_DIR / "translations"
PYBAMBU_DIR = INTEGRATION_DIR / "pybambu"

# Map from Printers enum name to serial number prefix
_DEVICE_TYPES = {
    "X1": "00M",
    "X1C": "00M",
    "X1E": "03W",
    "A1": "039",
    "A1MINI": "030",
    "P1P": "01S",
    "P1S": "01P",
    "P2S": "22E",
    "H2S": "093",
    "H2D": "094",
}


def get_bambu_languages() -> set[str]:
    """Return a set of languages supported by Bambu Studio."""
    i18n_dir = download_json(
        "https://api.github.com/repos/bambulab/BambuStudio/contents/bbl/i18n"
    )
    return {
        item["name"].lower()
        for item in i18n_dir
        if item["type"] == "dir"
        and re.match(r"^[a-zA-Z]{2}(_[a-zA-Z]{2})?$", item["name"])
    }


def get_local_languages() -> set[str]:
    """Return a set of local languages from the existing error text files."""
    return {path.stem for path in TRANSLATIONS_DIR.glob("*.json")}


def get_languages() -> list[str]:
    """Return a list of all languages to try downloading."""
    return sorted(get_local_languages() | get_bambu_languages())


def update_error_text(language: str, printer_type: str, serial_prefix: str) -> None:
    """Fetch error text for the given language and printer type, and save it."""

    url = f"https://e.bambulab.com/query.php?lang={language}&d={serial_prefix}"

    error_data = download_json(url)
    if error_data.get("result") != 0 or not isinstance(error_data.get("data"), dict):
        logging.info(f"No HMS data for {printer_type=} {language=}, skipping")
        return

    logging.info(f"Processing HMS data for {printer_type=} {language=}")
    error_data = process_json(error_data, language)

    with open(PYBAMBU_DIR / "hms_error_text" / f"hms_{printer_type}_{language}.json", "w") as file:
        json.dump(error_data, file, indent=2, sort_keys=True)


def download_json(json_url) -> dict:
    """Download the JSON data from the given URL."""
    req = urllib.request.Request(json_url, headers={"User-Agent": "Magic Browser"})
    con = urllib.request.urlopen(req)
    return json.load(con)


def process_json(bambu_data: dict, language: str) -> dict[str, dict[str, str]]:
    """Process the JSON data and prep it for adding to the merged data."""
    error_data = {"device_hms": {}, "device_error": {}}

    # Identify the correct language key (case insensitive match)
    data_language_keys = [
        key for key in bambu_data["data"]["device_hms"].keys() if language.lower() == key.lower()
    ]
    if len(data_language_keys) != 1:
        logging.error("Unexpected language keys in HMS data")
        exit(1)
    data_language = data_language_keys[0]

    for error_entry in bambu_data["data"]["device_hms"][data_language]:
        code = error_entry["ecode"].upper()
        value = (
            error_entry["intro"].replace('"', "'").replace("\n", "").replace("  ", " ")
        )
        if value == "":
            value = "unknown"
        error_data["device_hms"][code] = value

    for error_entry in bambu_data["data"]["device_error"][data_language]:
        code = error_entry["ecode"].upper()
        value = error_entry["intro"].replace('"', "'")
        if value == "":
            value = "unknown"
        error_data["device_error"][code] = value

    return error_data


def main():
    """The true main function."""
    logging.basicConfig(level=logging.INFO)

    for lang in get_languages():
        for printer_type, serial_prefix in _DEVICE_TYPES.items():
            update_error_text(lang, printer_type, serial_prefix)


if __name__ == "__main__":
    main()
    exit(0)
