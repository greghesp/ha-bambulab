from __future__ import annotations

import json
import requests

"""
python3 scripts/fetch_filaments.py > custom_components/bambu_lab/pybambu/filaments.json
"""


def get_filaments() -> dict:
    url = 'https://api.bambulab.com/v1/iot-service/api/slicer/setting?version=undefined'
    response = requests.get(url, timeout=10)
    if not response.ok:
        raise ValueError(response.status_code)
    return response.json()["filament"]["public"]


def format_filament_name(name: str) -> str:
    if " @" in name:
        return name[:name.index(" @")]
    return name


filaments = get_filaments()
data = dict(map(lambda filament: (filament["filament_id"], format_filament_name(filament["name"])), filaments))

print(json.dumps(data, indent=4))
