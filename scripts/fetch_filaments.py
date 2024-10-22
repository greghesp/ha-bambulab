"""
python3 scripts/fetch_filaments.py > custom_components/bambu_lab/pybambu/filaments.json
"""

from __future__ import annotations

import json
import requests


def get_filaments() -> dict:
    url = 'https://api.bambulab.com/v1/iot-service/api/slicer/setting?version=undefined'
    response = requests.get(url, timeout=10)
    if not response.ok:
        raise ValueError(response.status_code)
    return response.json()["filament"]["public"]


filaments = get_filaments()
data = {f["filament_id"]: f["name"].split("@", 1)[0].strip() for f in get_filaments()}

print(json.dumps(data, indent=4, sort_keys=True))
