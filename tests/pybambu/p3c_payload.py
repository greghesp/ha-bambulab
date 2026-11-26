"""Synthetic P3C payloads.

No P3C capture exists yet. These take the H3C mock printer and change only what Bambu Studio
02.09.02.62 documents as different on the P3C (printer type N11, 7 PrintTools, 300°C hotends,
AMS 3P type 7 with module name "n11a", no chamber heater or circulation fan). The AMS unit id is
not documented, so nothing may rely on a particular one.
"""

import copy
import json
from pathlib import Path

import pybambu

H3C_MOCK = Path(pybambu.__file__).parent / "mock_data" / "MOCK-H3C.json"
H3C_AMS_INDEX = 32
TOOL_COUNT = 7
AMS_INDEX = 36
AMS_3P_INFO = "240002007"


def _version_modules(modules: list[dict]) -> list[dict]:
    result = []
    for module in modules:
        name = module["name"]
        if name == "ota":
            result.append({**module, "product_name": "Bambu Lab P3C", "sn": "TEST-P3C"})
        elif name == "n10a":
            # H3C firmware can leave the unit id out, and Bambu Studio never reads it
            without_id = {key: value for key, value in module.items() if key != "id"}
            result.append({**without_id, "name": "n11a", "module_name": "N11A", "hw_ver": "N11A05",
                           "product_name": "AMS 3P", "sn": "TEST-AMS3P"})
        elif not (name.startswith("he") and int(name[2:]) >= TOOL_COUNT):
            result.append(module)
    return result


def _nozzle(entry: dict) -> dict:
    snow = entry["snow"]
    if snow >> 8 == H3C_AMS_INDEX:
        snow = (AMS_INDEX << 8) | (snow & 0xFF)
    return {**entry, "tm": 300, "snow": snow}


def p3c_payload() -> tuple[dict, dict]:
    """Return (get_version info, push_status print)."""
    source = json.loads(H3C_MOCK.read_text(encoding="utf-8"))
    info = source["get_version"]["info"]
    version = {**info, "command": "get_version", "module": _version_modules(info["module"])}

    status = copy.deepcopy(source["pushall"]["print"])
    ams = status["ams"]["ams"][0]
    ams.update({
        "id": str(AMS_INDEX),
        "info": AMS_3P_INFO,
        "tray": ams["tray"][:TOOL_COUNT],
        "zone_info": [{**ams["zone_info"][1], "zone_id": 0, "zone_slots": list(range(TOOL_COUNT))}],
    })
    status["ams"].update({"ams_exist_bits": "4000", "tray_exist_bits": f"{0b11 << 37:x}"})

    nozzle = status["device"]["nozzle"]
    nozzle["exist"] = ((1 << TOOL_COUNT) - 1) << 16
    nozzle["info"] = [_nozzle(entry) for entry in nozzle["info"] if entry["addr_id"] < TOOL_COUNT]
    status["vir_slot"] = [slot for slot in status["vir_slot"] if int(slot["id"]) > 255 - TOOL_COUNT]

    airduct = status["device"]["airduct"]
    airduct["modeList"] = [{"ctrl": [16, 32, 160, 48], "modeId": mode, "off": []} for mode in (0, 1)]
    airduct["parts"] = [part for part in airduct["parts"] if part["id"] != 240]
    return version, status
