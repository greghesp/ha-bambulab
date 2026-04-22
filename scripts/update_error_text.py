"""Update the HMS error texts from the Bambu servers."""

from __future__ import annotations
from collections import defaultdict, Counter

import gzip
import json
import logging
import re
import urllib.request
from html.parser import HTMLParser
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

# Map from printer model on https://wiki.bambulab.com/en/hms/home, to device name
# for cases where the name is different
_PRINTER_NAME_TO_MODEL = {
    "H2D Pro": "H2DPRO",
    "A1 Mini" : "A1MINI",
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

class HmsWikiParser(HTMLParser):

    table = str.maketrans("", "", "-_")
    url_re = re.compile("/en/.*/troubleshooting/hmscode/.*")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._wiki_urls = defaultdict(dict)
        self._current_url = None

    def get_wiki_urls(self) -> dict:
        return self._wiki_urls

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        attr_dict = dict(attrs)
        try:
            value = attr_dict["href"]
        except KeyError:
            return

        if value and HmsWikiParser.url_re.match(value):
            self._current_url = value

    def handle_endtag(self, tag):
        self._current_url = None

    def handle_data(self, data):
        if self._current_url:
            printers = [model.strip() for model in data.split("/")]
            printers = [_PRINTER_NAME_TO_MODEL.get(model, model) for model in printers]
            self._add_url(printers)

    def _add_url(self, printers) -> None:
        path_components = self._current_url.split("/")
        hms_code = path_components[-1].translate(HmsWikiParser.table)
        for printer in printers:
            self._wiki_urls[hms_code][printer] = self._current_url


def get_wiki_urls(hms_url) -> dict:
    req = urllib.request.Request(hms_url, headers={"User-Agent": "Magic Browser"})
    con = urllib.request.urlopen(req)
    
    parser = HmsWikiParser()
    parser.feed(con.read())
    return parser.get_wiki_urls()


def download_json(json_url) -> dict:
    """Download the JSON data from the given URL."""
    req = urllib.request.Request(json_url, headers={"User-Agent": "Magic Browser"})
    con = urllib.request.urlopen(req)
    return json.load(con)


def process_json(bambu_data: dict, language: str) -> dict[str, dict[str, str]]:
    """Process the JSON data and prep it for adding to the merged data."""
    error_data = {"device_hms": {}, "device_error": {}}

    # Identify the correct language key (case insensitive prefix match)
    data_language_keys = [
        key for key in bambu_data["data"]["device_hms"].keys()
        if key.lower().startswith(language.lower())
    ]
    if len(data_language_keys) != 1:
        logging.error("Unexpected language keys in HMS data: %s", bambu_data["data"]["device_hms"].keys())
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

def pack_msg_map(code_messages: dict) -> dict:
    """Packs a message map for space.

    source is a dict mapping a code to a map of model-specific messages, e.g.

        {"1234567890AB": {"H2D": "message", "A1": "message"}}

    The returned object has, for each code, mappings from message to list of models,
    except that the most common message has an empty list.
    """
    merged = {}
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

        merged[code] = dict(msg_to_models)

    return merged

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
        merged[category] = pack_msg_map(code_messages)

    return merged

def get_wiki_links() -> dict:
    parser = HmsWikiParser()

    hms_url = "https://wiki.bambulab.com/en/hms/home"
    req = urllib.request.Request(hms_url, headers={"User-Agent": "Magic Browser"})
    con = urllib.request.urlopen(req)

    parser.feed(con.read().decode())
    wiki_links = parser.get_wiki_urls()
    return pack_msg_map(wiki_links)

def write_json(data: dict, filename: str)-> None:
    """Writes JSON file.
    
    Write human-readable JSON to SCRIPT_DIR/hms_error_text and gzip files to
    PYBAMBU_DIR/hms_error_text.
    """    
    # Write human readable json for PR reviews to a sub-directory alongside the script.
    with open(SCRIPT_DIR / "hms_error_text" / filename, "w", encoding="utf-8") as file:
        json.dump(data, file, sort_keys=True, indent=2, ensure_ascii=False)

    # Write gzip files for minimum file size to the integration directories.
    with gzip.open(PYBAMBU_DIR / "hms_error_text" / f"{filename}.gz", "wt", encoding="utf-8") as gzfile:
        json.dump(data, gzfile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def main():
    """The true main function."""
    logging.basicConfig(level=logging.INFO)

    wiki_links = get_wiki_links()  
    write_json(wiki_links, "wiki_links.json")  

    for lang in get_languages():
        all_devices = {}
        for printer_type, serial_prefix in _DEVICE_TYPES.items():
            if lang == "zh_cn" or lang == "zh-Hans":
                all_devices[printer_type] = get_error_text("zh-cn", printer_type, serial_prefix)
                continue
            all_devices[printer_type] = get_error_text(lang, printer_type, serial_prefix)

        merged = merge_device_errors(all_devices)
        write_json(merged, f"hms_{lang}.json")

if __name__ == "__main__":
    main()
    exit(0)
