"""Work out and apply the oldest Home Assistant release this integration supports.

Policy: we support Home Assistant releases from the last SUPPORT_MONTHS months.
The minimum is the first release (YYYY.M.0) of the month SUPPORT_MONTHS before
today. It only ever moves forward. If hacs.json already names something newer
(raised by hand because the code needed it), that wins.

Release data comes from PyPI, so the version always exists and the matching
Python version is whatever that release declares in requires_python.

    python scripts/ha_min_version.py target            # the version policy says today
    python scripts/ha_min_version.py bump              # write it to hacs.json + pyproject.toml
    python scripts/ha_min_version.py ci-env minimum    # GitHub Actions outputs for the CI matrix
    python scripts/ha_min_version.py ci-env latest

Standard library only, so it runs on the runner's system Python before
setup-python.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

SUPPORT_MONTHS = 6

REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
HACS_JSON = os.path.join(REPO_ROOT, "hacs.json")
PYPROJECT = os.path.join(REPO_ROOT, "pyproject.toml")
PYPI_URL = "https://pypi.org/pypi/homeassistant/{}json"


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def pypi(version: str = "") -> dict:
    url = PYPI_URL.format(f"{version}/" if version else "")
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def stable_releases() -> list[str]:
    releases = pypi()["releases"]
    stable = [
        v for v in releases if re.fullmatch(r"\d{4}\.\d+\.\d+", v) and releases[v]
    ]
    return sorted(stable, key=parse)


def min_python(version: str) -> str:
    """Oldest Python minor version the given Home Assistant release installs on."""
    requires = pypi(version)["info"]["requires_python"] or ""
    match = re.search(r">=\s*(\d+)\.(\d+)", requires)
    if not match:
        sys.exit(f"Can't read requires_python {requires!r} for homeassistant {version}")
    return f"{match.group(1)}.{match.group(2)}"


def current_minimum() -> str:
    with open(HACS_JSON, encoding="utf-8") as f:
        return json.load(f)["homeassistant"]


def policy_target(today: datetime.date, releases: list[str]) -> str:
    months = today.year * 12 + (today.month - 1) - SUPPORT_MONTHS
    year, month = divmod(months, 12)
    month += 1
    first_of_month = f"{year}.{month}.0"
    if first_of_month in releases:
        return first_of_month
    # A month with no .0 (hasn't happened yet): take the next release after it.
    later = [v for v in releases if parse(v) >= (year, month, 0)]
    if not later:
        sys.exit(f"No Home Assistant release on PyPI from {year}.{month} onwards")
    return later[0]


def target(today: datetime.date) -> str:
    candidate = policy_target(today, stable_releases())
    current = current_minimum()
    return candidate if parse(candidate) > parse(current) else current


def write_hacs_json(version: str) -> None:
    with open(HACS_JSON, encoding="utf-8") as f:
        text = f.read()
    new_text, count = re.subn(
        r'("homeassistant":\s*")[^"]*(")', rf"\g<1>{version}\g<2>", text
    )
    if count != 1:
        sys.exit("Couldn't find the homeassistant key in hacs.json")
    with open(HACS_JSON, "w", encoding="utf-8") as f:
        f.write(new_text)


def write_pyproject(version: str, python: str) -> None:
    with open(PYPROJECT, encoding="utf-8") as f:
        text = f.read()
    year_month = ".".join(version.split(".")[:2])
    text, comments = re.subn(
        r"(# Oldest Python supported by the minimum Home Assistant in hacs\.json \()[^)]*(\)\.)",
        rf"\g<1>{year_month}\g<2>",
        text,
    )
    text, targets = re.subn(
        r'(target-version = ")py\d+(")', rf"\g<1>py{python.replace('.', '')}\g<2>", text
    )
    if comments != 1 or targets != 1:
        sys.exit(
            "Couldn't find the target-version line and its comment in pyproject.toml"
        )
    with open(PYPROJECT, "w", encoding="utf-8") as f:
        f.write(text)


def github_output(values: dict[str, str]) -> None:
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(lines)
    sys.stdout.write(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--date",
        type=datetime.date.fromisoformat,
        default=datetime.date.today(),
        help="pretend today is this date (YYYY-MM-DD)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("target", help="print the minimum the policy gives today")
    sub.add_parser(
        "bump", help="write the policy minimum to hacs.json and pyproject.toml"
    )
    ci = sub.add_parser(
        "ci-env", help="emit python/package outputs for the CI test matrix"
    )
    ci.add_argument("which", choices=["minimum", "latest"])
    args = parser.parse_args()

    if args.command == "target":
        print(target(args.date))
    elif args.command == "bump":
        old = current_minimum()
        new = target(args.date)
        python = min_python(new)
        write_hacs_json(new)
        write_pyproject(new, python)
        github_output(
            {
                "old": old,
                "new": new,
                "python": python,
                "changed": str(new != old).lower(),
            }
        )
    else:
        version = (
            current_minimum() if args.which == "minimum" else pypi()["info"]["version"]
        )
        github_output({"version": version, "python": min_python(version)})


if __name__ == "__main__":
    main()
