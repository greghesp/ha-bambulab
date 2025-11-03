"""Update the HMS error texts from the Bambu servers."""

from __future__ import annotations
from collections import defaultdict, Counter

import gzip
import json
import logging
import re
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
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


def get_error_text(language: str, printer_type: str, serial_prefix: str) -> None:
    """Fetch error text for the given language and printer type, and save it."""

    url = f"https://e.bambulab.com/query.php?lang={language}&d={serial_prefix}"

    error_data = download_json(url)
    if error_data.get("result") != 0 or not isinstance(error_data.get("data"), dict):
        logging.info(f"No HMS data for {printer_type=} {language=}, skipping")
        return

    logging.info(f"Processing HMS data for {printer_type=} {language=}")
    error_data = process_json(error_data, language)

    return error_data


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
        error_data["device_hms"][code] = value

    for error_entry in bambu_data["data"]["device_error"][data_language]:
        code = error_entry["ecode"].upper()
        value = error_entry["intro"].replace('"', "'")
        error_data["device_error"][code] = value

    return error_data

def collect_errors(all_devices, category):
    code_messages = defaultdict(set)
    for printer_type, device_data in all_devices.items():
        for code, msg in device_data.get(category, {}).items():
            code_messages[code].add(msg)
    return code_messages

def merge_device_errors(all_devices):
    merged = {"device_error": {}, "device_hms": {}}

    for category in ["device_error", "device_hms"]:
        # Collect messages per code
        code_messages = defaultdict(dict)  # code -> {device: message}
        for device_name, device_data in all_devices.items():
            if device_data is not None:
                for code, msg in device_data.get(category, {}).items():
                    code_messages[code][device_name] = msg

        # Build merged structure
        for code, device_msg_map in code_messages.items():
            # Count occurrences of each message
            msg_counter = Counter(device_msg_map.values())
            default_msg, _ = msg_counter.most_common(1)[0]

            # Map each message to its devices
            msg_to_models = defaultdict(list)
            for device, msg in device_msg_map.items():
                if msg == default_msg:
                    continue
                msg_to_models[msg].append(device)

            # Add default message with placeholder "_"
            msg_to_models[default_msg] = []

            merged[category][code] = dict(msg_to_models)

    return merged

def main():
    """The true main function."""
    logging.basicConfig(level=logging.INFO)

    for lang in get_languages():
        all_devices = {}
        for printer_type, serial_prefix in _DEVICE_TYPES.items():
            all_devices[printer_type] = get_error_text(lang, printer_type, serial_prefix)

        merged = merge_device_errors(all_devices)

        # Write human readable json for PR reviews to a sub-directory alongside the script.
        with open(SCRIPT_DIR / "hms_error_text" / f"hms_{lang}.json", "w", encoding="utf-8") as file:
            json.dump(merged, file, sort_keys=True, indent=2, ensure_ascii=False)

        # Write gzip files for minimum file size to the integration directories.
        with gzip.open(PYBAMBU_DIR / "hms_error_text" / f"hms_{lang}.json.gz", "wt", encoding="utf-8") as gzfile:
            json.dump(merged, gzfile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

if __name__ == "__main__":
    main()
    exit(0)
