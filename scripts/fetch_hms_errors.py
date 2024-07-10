from __future__ import annotations

import json
import requests

"""
python3 scripts/fetch_hms_errors.py > custom_components/bambu_lab/pybambu/hms_errors.json
"""


def get_hms_errors() -> dict:
    url = 'https://e.bambulab.com/query.php?lang=en'
    response = requests.get(url, timeout=10)
    if not response.ok:
        raise ValueError(response.status_code)
    return response.json()["data"]["device_hms"]["en"]


def format_hms_error_code(code: str) -> str:
    return "_".join([code[::-1][i:i+4] for i in range(0, len(code), 4)])[::-1]


errors = get_hms_errors()
data = dict(map(lambda error: (format_hms_error_code(error["ecode"]), error["intro"]), errors))

print(json.dumps(data, indent=4))
