"""
python3 scripts/fetch_filaments.py > custom_components/bambu_lab/pybambu/filaments.json
"""

from __future__ import annotations

import cloudscraper
import json
import os

def get_filaments() -> dict:
    url = 'https://api.bambulab.com/v1/iot-service/api/slicer/setting?version=1.10.0.89'
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url, timeout=10)
    if not response.ok:
        if 'cloudflare' in response.text:
            print("CLOUDFLARED")
        raise ValueError(response.status_code)
    return response.json()["filament"]["public"]


filaments = get_filaments()
data = {f["filament_id"]: f["name"].split("@", 1)[0].strip() for f in get_filaments()}

output = json.dumps(data, indent=4, sort_keys=True)

script_path = os.path.dirname(__file__)
with open(f'{script_path}/../custom_components/bambu_lab/pybambu/filaments_detail.json', 'w') as file:
    file.write(output)